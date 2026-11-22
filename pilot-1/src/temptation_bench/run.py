"""Paid runner: the only way a paid (or gateway) eval is launched (spec §7.2, §7.3).

    uv run python -m temptation_bench.run --step gfree --estimate 0 --token-limit 800000

Order: refuse an unbuilt step (no network) -> `budget.check` (fails closed) -> print the
plan -> (stop here with `--dry-run`) -> `inspect_ai.eval(...)` -> `budget.record` (always,
even if the eval raised, because money may have been spent).

- Per-sample `cost_limit` = `--sample-cost-limit`, else 2 x the measured smoke cost per run
  from the ledger (spec D9); the smoke and the steps before it use \\$1.00.
- `retry_on_error=1`: a sample that ends in error is rerun once with the same seed and dose
  (DD §13A). The rerun keeps the cell cache, so its replayed turns are free. The failed
  attempt stays in the `.eval` (`error_retries`) and its billed calls are in the ledger.
  The estimate passed in must cover that rerun: it is inside the same step cap.
- The eval process itself loads `.env` (Inspect does this). Nothing here exports it."""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from inspect_ai import eval as inspect_eval
from inspect_ai.model import Model

from . import budget
from .budget import STEP_CAPS, STOP_LINE, BudgetError

LOG_ROOT = budget.ROOT / "logs" / "paid"  # gitignored
SMOKE_SAMPLE_COST_LIMIT = 1.00  # spec §7.3: the smoke itself (and steps before it) use $1
RETRY_ON_ERROR = 1  # DD §13A: one same-seed rerun; failures stay in the log
NEEDS_SMOKE = {"mini_batch", "full_run"}  # their per-sample limit comes from the smoke


class RunnerError(RuntimeError):
    """The runner refuses (unbuilt step, missing smoke measurement). Nothing was launched."""


def _count(csv: str) -> int:
    return len([x for x in csv.split(",") if x.strip()])


@dataclass(frozen=True)
class Plan:
    models: tuple[str, ...]
    variant: str
    seeds: str
    doses: str
    people: str = "template"
    max_samples: int = 1

    @property
    def runs(self) -> int:
        return len(self.models) * _count(self.seeds) * _count(self.doses)


@dataclass(frozen=True)
class Ctx:
    step: str
    plan: Plan
    log_dir: Path
    sample_cost_limit: float
    token_limit: int | None
    model: Model | None = None
    display: str | None = None


Launch = Callable[[Ctx], None]


@dataclass(frozen=True)
class Step:
    plan: Plan | None
    launch: Launch | None
    not_built: str = ""  # why the step refuses; empty when built

    @property
    def built(self) -> bool:
        return self.launch is not None and self.plan is not None


def launch_task_eval(ctx: Ctx) -> None:
    """One `inspect_ai.eval` of the `temptation_bench` task for the step's plan."""
    from .harness.task import temptation_bench

    p = ctx.plan
    kw: dict[str, Any] = {}
    if ctx.display is not None:
        kw["display"] = ctx.display
    inspect_eval(
        temptation_bench(
            variant=p.variant,
            seeds=p.seeds,
            doses=p.doses,
            people=p.people,
            token_limit=ctx.token_limit,
        ),
        model=ctx.model if ctx.model is not None else list(p.models),
        log_dir=str(ctx.log_dir),
        max_samples=p.max_samples,
        retry_on_error=RETRY_ON_ERROR,
        cost_limit=ctx.sample_cost_limit,
        **kw,
    )


HAIKU = "anthropic/claude-haiku-5-5"
LUNA = "openai-api/xpl/gpt-6-luna"

# The dispatch table. Later tasks fill in the refusing entries (plan Tasks 26, 29-31, 34).
STEPS: dict[str, Step] = {
    # Task 29: free Luna, D1-D3, seed 1001, dose $30k, one sample at a time
    "gfree": Step(Plan((LUNA,), "gfree", "1001", "3000000", max_samples=1), launch_task_eval),
    "route_check": Step(None, None, "the route-check script (2 Haiku calls + 1 qwen) is Task 30"),
    # Task 30: Haiku, decision window, seed 1001, dose $30k
    "smoke": Step(Plan((HAIKU,), "window", "1001", "3000000", max_samples=1), launch_task_eval),
    "pregen": Step(None, None, "pregen_people exists (Task 26); the runner launch is Task 31"),
    "mini_batch": Step(
        None, None, "needs people=prose (Task 26) and the smoke-based estimate (Task 31)"
    ),
    "full_run": Step(None, None, "needs the D11-D30 events and audit (Tasks 32-33)"),
}


def default_sample_cost_limit(step: str, ledger_path: Path | None = None) -> float:
    """2 x the latest smoke's actual cost per run (spec D9); $1 for the smoke and earlier."""
    if step not in NEEDS_SMOKE:
        return SMOKE_SAMPLE_COST_LIMIT
    smokes = [
        e
        for e in budget.ledger_entries(ledger_path=ledger_path)
        if e.get("step") == "smoke" and e["actual"] > 0
    ]
    if not smokes:
        raise RunnerError(
            f"{step} needs a measured smoke cost in the ledger (or --sample-cost-limit)"
        )
    last = smokes[-1]
    runs = last.get("runs")
    per_run = last["actual"] / (runs if isinstance(runs, int) and runs > 0 else 1)
    return 2 * per_run


def _plan_text(step: str, ctx: Ctx, estimate: float, spent: float, balance: float) -> str:
    p = ctx.plan
    models = [str(ctx.model)] if ctx.model is not None else list(p.models)
    lines = [
        f"step:              {step}",
        f"models:            {', '.join(models)}",
        f"variant:           {p.variant} (people={p.people})",
        f"seeds x doses:     {p.seeds} x {p.doses} = {p.runs // len(p.models)} cells per model",
        f"runs:              {len(models) * (p.runs // len(p.models))}",
        f"max_samples:       {p.max_samples}",
        f"retry_on_error:    {RETRY_ON_ERROR} (same seed and dose; failure kept in the log)",
        f"sample cost_limit: ${ctx.sample_cost_limit:.4f}",
        f"token_limit:       {ctx.token_limit if ctx.token_limit is not None else 'none'}",
        f"estimate / cap:    ${estimate:.4f} / ${STEP_CAPS[step]:.2f}",
        f"spent / stop line: ${spent:.4f} / ${STOP_LINE:.2f}",
        f"gateway balance:   ${balance:.4f}",
        f"log dir:           {ctx.log_dir}",
    ]
    return "\n".join(lines)


def run_step(
    step: str,
    estimate: float,
    *,
    token_limit: int | None = None,
    sample_cost_limit: float | None = None,
    dry_run: bool = False,
    model: Model | None = None,
    log_root: Path | None = None,
    env_path: Path | None = None,
    ledger_path: Path | None = None,
    transport: httpx.BaseTransport | None = None,
    display: str | None = None,
) -> dict[str, Any] | None:
    """Check, launch, record. Returns the ledger line (None for a dry run)."""
    spec = STEPS.get(step)
    if spec is None:
        raise RunnerError(f"unknown step {step!r}")
    if not spec.built:
        raise RunnerError(f"step {step} is not built yet: {spec.not_built}")
    assert spec.plan is not None and spec.launch is not None
    if sample_cost_limit is None:
        sample_cost_limit = default_sample_cost_limit(step, ledger_path)
    if not (math.isfinite(sample_cost_limit) and sample_cost_limit > 0):
        raise RunnerError("the sample cost limit must be a finite number > 0")
    if token_limit is not None and token_limit <= 0:
        raise RunnerError("the token limit must be > 0")

    balance = budget.guard(
        step, estimate, env_path=env_path, ledger_path=ledger_path, transport=transport
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    ctx = Ctx(
        step=step,
        plan=spec.plan,
        log_dir=Path(log_root or LOG_ROOT) / f"{step}-{stamp}",
        sample_cost_limit=float(sample_cost_limit),
        token_limit=token_limit,
        model=model,
        display=display,
    )
    print(
        ("DRY RUN (no eval launched)\n" if dry_run else "")
        + _plan_text(step, ctx, estimate, budget.spent(ledger_path=ledger_path), balance)
    )
    if dry_run:
        return None

    models = [str(model)] if model is not None else list(spec.plan.models)
    runs = len(models) * (spec.plan.runs // len(spec.plan.models))
    error: str | None = None
    try:
        spec.launch(ctx)
    except BaseException as e:
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        paths = sorted(ctx.log_dir.glob("*.eval")) if ctx.log_dir.exists() else []
        entry = budget.record(
            step,
            models,
            runs,
            estimate,
            paths,
            balance_before=balance,
            error=error,
            env_path=env_path,
            ledger_path=ledger_path,
            transport=transport,
        )
        print(
            f"recorded: {step} actual ${entry['actual']:.4f} ({entry['actual_source']}); "
            f"spent ${budget.spent(ledger_path=ledger_path):.4f} of ${STOP_LINE:.2f}"
        )
    return entry


def main(
    argv: Sequence[str] | None = None,
    *,
    model: Model | None = None,
    log_root: Path | None = None,
    env_path: Path | None = None,
    ledger_path: Path | None = None,
    transport: httpx.BaseTransport | None = None,
    display: str | None = None,
) -> int:
    ap = argparse.ArgumentParser(prog="python -m temptation_bench.run")
    ap.add_argument("--step", required=True, choices=list(STEP_CAPS))
    ap.add_argument("--estimate", required=True, type=float, help="$; must cover one rerun")
    ap.add_argument("--token-limit", type=int, default=None)
    ap.add_argument("--sample-cost-limit", type=float, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        run_step(
            args.step,
            args.estimate,
            token_limit=args.token_limit,
            sample_cost_limit=args.sample_cost_limit,
            dry_run=args.dry_run,
            model=model,
            log_root=log_root,
            env_path=env_path,
            ledger_path=ledger_path,
            transport=transport,
            display=display,
        )
    except (BudgetError, RunnerError) as e:
        print(f"REFUSED: {budget.redact(str(e))}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAILED: {budget.redact(f'{type(e).__name__}: {e}')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
