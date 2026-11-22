"""Paid runner: the only way a paid (or gateway) eval is launched (spec §7.2, §7.3).

    uv run python -m temptation_bench.run --step gfree --estimate 0 --token-limit 800000

Order: refuse an unbuilt step (no network) -> `budget.check` (fails closed) -> print the
plan -> (stop here with `--dry-run`) -> `inspect_ai.eval(...)` -> `budget.record` (always,
even if the eval raised, because money may have been spent).

- Per-sample `cost_limit` = `--sample-cost-limit`, else 2 x the measured smoke cost per run
  from the ledger (spec D9); the smoke and the steps before it use \\$1.00, lowered so the
  worst case fits the step cap (the smoke: \\$0.50).
- Worst-case exposure (R25-2): runs x sample cost limit x (1 + retries). A paid step refuses
  if it is over the step cap, if spent + exposure is over the stop line, or if it is unknown
  (no cost limit: never treated as \\$0). A free-tier step (G-free, cap \\$0) is bounded in
  tokens instead: runs x token limit x (1 + retries) must fit the free tier (1M tokens/day).
- `--token-limit` defaults (R25-5): the step's own default (G-free: 800k, spec §6); otherwise,
  once a smoke is in
  the ledger, 2 x T_run, the mean tokens per smoke run (the ledger's `total_tokens`, which
  is Inspect's `total_tokens`: input incl. cache reads/writes + output, the same quantity
  Inspect's token limit meters); before any smoke, none.
- One model per eval (X-1): run ids, JSONL paths and `harness.json` are per run, not per
  model, so the runner refuses a plan with more than one model.
- The free-tier branch also refuses if spent + runs x sample cost limit x attempts is over
  the stop line, in case the gateway bills the model after all (Task 29 pre-work).
- `--step route_check --list-models` (Task 29): `GET /v1/models`, prints only the sorted
  ids. A free metadata call: no guard, no ledger line, no `--estimate` needed.
- G-free runs with `retry_on_error=0` (a connectivity check, rerun by hand; round 1b ruling),
  so 1 run x 800k x 1 attempt fits its free tier.
- `retry_on_error=1` (every other step): a sample that ends in error is rerun once with the
  same seed and dose (DD §13A). The rerun keeps the cell cache, so its replayed turns are
  free. The failed attempt stays in the `.eval` (`error_retries`) and its billed calls are
  in the ledger. The estimate passed in must cover that rerun: it is inside the same cap.
- `--step route_check` (Task 30): 2 Haiku calls + 1 qwen call (`harness/route_check.py`),
  no automatic rerun, Inspect's local response cache off (`--reuse-cache`: on, one fixed
  scope). Its exposure is its own token worst case from spec prices (`worst_case`), not
  runs x limit x attempts. After `record`, the PASS/FAIL table is printed from the log; a
  FAIL exits 1 with the §7.2 note "route fallback needs a fresh owner OK" and never tries
  another route.
- `--estimate-smoke` (Task 30): DD §13.3 arithmetic from `--from-log` and/or `--turns`,
  `--mean-input`, `--mean-output`, `--hit-share` (`estimate.py`). Local only: no guard,
  no network, no ledger line.
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


class CheckFailed(RuntimeError):
    """A step ran (and was recorded) but its own check failed (the route check)."""


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
    free_tier_tokens: int | None = None  # set: a free-tier step, bounded in tokens (R25-2)
    retry_on_error: int = RETRY_ON_ERROR  # automatic same-seed reruns of an errored sample
    token_limit: int | None = None  # the step's default token limit (`--token-limit` wins)
    aux_models: tuple[str, ...] = ()  # other models the step calls (route check: qwen)

    @property
    def attempts(self) -> int:
        """Worst-case runs of one sample: the attempt plus its automatic reruns."""
        return 1 + self.retry_on_error

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
    reuse_cache: bool = False  # route check only: Inspect's local response cache on


Launch = Callable[[Ctx], None]
Exposure = Callable[[], tuple[float, str]]  # ($ worst case, how it was computed)
Verify = Callable[[Ctx, list[Path]], None]  # raises CheckFailed


@dataclass(frozen=True)
class Step:
    plan: Plan | None
    launch: Launch | None
    not_built: str = ""  # why the step refuses; empty when built
    exposure: Exposure | None = None  # a step's own worst case (else runs x limit x attempts)
    verify: Verify | None = None  # a check on the written log, after `record`

    @property
    def built(self) -> bool:
        return self.launch is not None and self.plan is not None


def one_model(plan: Plan, model: Model | None = None) -> str | Model:
    """The single model of an eval (X-1). Two models in one eval would share run ids, JSONL
    paths, `LIVE` keys and `harness.json`, and run at the same time; Task 31 runs one eval
    per model instead."""
    if model is not None:
        return model
    if len(plan.models) != 1:
        raise RunnerError(
            f"one model per eval: the plan names {len(plan.models)} ({', '.join(plan.models)})"
        )
    return plan.models[0]


def launch_task_eval(ctx: Ctx) -> None:
    """One `inspect_ai.eval` of the `temptation_bench` task for the step's plan."""
    from .harness.routes import model_args_for
    from .harness.task import temptation_bench

    p = ctx.plan
    model = one_model(p, ctx.model)
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
        model=model,
        # openai-api routes send non-strict tools (gateway 400 on strict; harness/routes.py)
        model_args=model_args_for(str(model)) if isinstance(model, str) else {},
        log_dir=str(ctx.log_dir),
        max_samples=p.max_samples,
        retry_on_error=p.retry_on_error,
        cost_limit=ctx.sample_cost_limit,
        **kw,
    )


def launch_route_check(ctx: Ctx) -> None:
    """The route check (Task 30): one `inspect_ai.eval` of the tiny `route_check` task.
    No automatic rerun: a failure is read and reported, never retried on another route."""
    from .harness import route_check as rc
    from .harness.routes import model_args_for

    model = one_model(ctx.plan, ctx.model)
    kw: dict[str, Any] = {}
    if ctx.display is not None:
        kw["display"] = ctx.display
    inspect_eval(
        rc.route_check(people_model=ctx.plan.aux_models[0], reuse_cache=ctx.reuse_cache),
        model=model,
        model_args=model_args_for(str(model)) if isinstance(model, str) else {},
        log_dir=str(ctx.log_dir),
        max_samples=1,
        retry_on_error=ctx.plan.retry_on_error,
        cost_limit=ctx.sample_cost_limit,
        **kw,
    )


def route_check_exposure() -> tuple[float, str]:
    from .harness import route_check as rc

    return rc.worst_case()


def verify_route_check(ctx: Ctx, paths: list[Path]) -> None:
    """Print the PASS/FAIL table from the written log; raise `CheckFailed` on any FAIL."""
    from inspect_ai.log import read_eval_log

    from .harness import route_check as rc

    if len(paths) != 1:
        raise CheckFailed(
            f"route check wrote {len(paths)} .eval logs, expected 1; {rc.FALLBACK_NOTE}"
        )
    rows = rc.check_log(
        read_eval_log(str(paths[0]), resolve_attachments=True), reuse_cache=ctx.reuse_cache
    )
    print("route check:\n" + rc.table(rows))
    if not rc.passed(rows):
        failed = ", ".join(r.name for r in rows if not r.ok)
        raise CheckFailed(f"route check FAILED ({failed}); {rc.FALLBACK_NOTE}")


HAIKU = "anthropic/claude-haiku-5-5"
PEOPLE = "openai-api/xpl/qwen3.7-flash"  # spec D4: the people role (harness/routes.py)
FREE_TIER = 1_000_000  # Luna free tier: 1M tokens/day (spec §6 G-free)
GFREE_TOKEN_LIMIT = 800_000  # spec §6 G-free
LUNA = "openai-api/xpl/gpt-6-luna"

# The dispatch table. Later tasks fill in the refusing entries (plan Tasks 26, 29-31, 34).
STEPS: dict[str, Step] = {
    # Task 29: free Luna, D1-D3, seed 1001, dose $30k, one sample at a time
    "gfree": Step(
        Plan(
            (LUNA,),
            "gfree",
            "1001",
            "3000000",
            max_samples=1,
            free_tier_tokens=FREE_TIER,
            retry_on_error=0,  # round 1b: no automatic rerun; spec §6 keeps 800k tokens
            token_limit=GFREE_TOKEN_LIMIT,
        ),
        launch_task_eval,
    ),
    # Task 30: 2 Haiku calls (same >= 5k-token prefix, one tool) + 1 qwen call; no rerun
    "route_check": Step(
        Plan((HAIKU,), "route_check", "-", "-", "-", retry_on_error=0, aux_models=(PEOPLE,)),
        launch_route_check,
        exposure=route_check_exposure,
        verify=verify_route_check,
    ),
    # Task 30: Haiku, decision window, seed 1001, dose $30k
    "smoke": Step(Plan((HAIKU,), "window", "1001", "3000000", max_samples=1), launch_task_eval),
    "pregen": Step(None, None, "pregen_people exists (Task 26); the runner launch is Task 31"),
    "mini_batch": Step(
        None, None, "needs people=prose (Task 26) and the smoke-based estimate (Task 31)"
    ),
    "full_run": Step(None, None, "needs the D11-D30 events and audit (Tasks 32-33)"),
}


def default_sample_cost_limit(step: str, ledger_path: Path | None = None) -> float:
    """2 x the latest smoke's actual cost per run (spec D9). For the smoke and earlier: $1,
    lowered to cap / (runs x attempts) so the worst case fits the step cap (smoke: $0.50).
    A free-tier step keeps $1: its bound is the free-tier token count."""
    if step not in NEEDS_SMOKE:
        spec = STEPS.get(step)
        plan = spec.plan if spec is not None else None
        cap = STEP_CAPS[step]
        if cap <= 0 or (plan is not None and plan.free_tier_tokens is not None):
            return SMOKE_SAMPLE_COST_LIMIT
        runs, attempts = (plan.runs, plan.attempts) if plan is not None else (1, 1 + RETRY_ON_ERROR)
        return min(SMOKE_SAMPLE_COST_LIMIT, cap / (runs * attempts))
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


def default_token_limit(ledger_path: Path | None = None) -> int | None:
    """2 x T_run from the latest smoke line with token totals (Task 24 brief), else None.
    T_run = the line's `total_tokens` / `runs`. Old lines without the fields are skipped."""
    for e in reversed(budget.ledger_entries(ledger_path=ledger_path)):
        tokens, runs = e.get("total_tokens"), e.get("runs")
        if e.get("step") != "smoke" or isinstance(tokens, bool) or isinstance(runs, bool):
            continue
        if isinstance(tokens, int) and tokens > 0 and isinstance(runs, int) and runs > 0:
            return 2 * tokens // runs
    return None


def exposure(plan: Plan, sample_cost_limit: float | None) -> float | None:
    """Worst-case run-time spend in $: runs x per-sample cost limit x attempts. None (unknown)
    without a cost limit."""
    if sample_cost_limit is None:
        return None
    return plan.runs * sample_cost_limit * plan.attempts


def check_exposure(
    step: str,
    plan: Plan,
    sample_cost_limit: float | None,
    token_limit: int | None,
    spent: float,
) -> str:
    """Refuse (BudgetError) a worst case the step cap or the stop line cannot hold (R25-2).
    Returns the exposure line for the printed plan."""
    if plan.free_tier_tokens is not None:  # G-free: $0 only while inside the free tier
        free = plan.free_tier_tokens
        if token_limit is None:
            raise BudgetError(f"{step} needs a token limit: its free-tier worst case is unknown")
        tokens = plan.runs * token_limit * plan.attempts
        how = f"{plan.runs} runs x {token_limit} tokens x {plan.attempts} attempts"
        if tokens > free:
            raise BudgetError(
                f"{step} worst case {tokens} tokens ({how}) is over the free tier of {free} "
                "tokens/day; lower --token-limit"
            )
        # Task 29 pre-work: if the free tier does not apply (the gateway bills the model),
        # the per-sample cost limit is the bound, so it must still fit the stop line.
        billed = exposure(plan, sample_cost_limit)
        if billed is None:
            raise BudgetError(f"{step} worst case if billed is unknown (no per-sample cost limit)")
        bhow = f"{plan.runs} runs x ${sample_cost_limit:.4f} x {plan.attempts} attempts"
        if spent + billed > STOP_LINE:
            raise BudgetError(
                f"spent ${spent:.4f} + {step} worst case if billed ${billed:.4f} ({bhow}) is "
                f"over the ${STOP_LINE:.2f} stop line"
            )
        return (
            f"$0 within the free tier ({tokens} of {free} free-tier tokens: {how}); "
            f"${billed:.4f} if billed ({bhow})"
        )
    e = exposure(plan, sample_cost_limit)
    if e is None:
        raise BudgetError(f"{step} worst-case exposure is unknown (no per-sample cost limit)")
    how = f"{plan.runs} runs x ${sample_cost_limit:.4f} x {plan.attempts} attempts"
    cap = STEP_CAPS[step]
    if e > cap:
        raise BudgetError(
            f"{step} worst-case exposure ${e:.4f} ({how}) is over the {step} cap ${cap:.2f}; "
            "lower --sample-cost-limit"
        )
    if spent + e > STOP_LINE:
        raise BudgetError(
            f"spent ${spent:.4f} + worst-case exposure ${e:.4f} ({how}) is over the "
            f"${STOP_LINE:.2f} stop line"
        )
    return f"${e:.4f} ({how})"


def check_dollar_exposure(step: str, e: float, how: str, spent: float) -> str:
    """A step's own $ worst case must fit its cap and the stop line (R25-2)."""
    cap = STEP_CAPS[step]
    if not math.isfinite(e) or e < 0:
        raise BudgetError(f"{step} worst-case exposure is unknown")
    if e > cap:
        raise BudgetError(
            f"{step} worst-case exposure ${e:.4f} ({how}) is over the {step} cap ${cap:.2f}"
        )
    if spent + e > STOP_LINE:
        raise BudgetError(
            f"spent ${spent:.4f} + worst-case exposure ${e:.4f} ({how}) is over the "
            f"${STOP_LINE:.2f} stop line"
        )
    return f"${e:.4f} ({how})"


def _plan_text(
    step: str,
    ctx: Ctx,
    estimate: float,
    spent: float,
    balance: float,
    exposure_line: str,
    token_source: str,
) -> str:
    p = ctx.plan
    models = [str(one_model(p, ctx.model)), *(f"{m} (people)" for m in p.aux_models)]
    token = f"{ctx.token_limit} ({token_source})" if ctx.token_limit is not None else "none"
    lines = [
        f"step:              {step}",
        f"models:            {', '.join(models)}",
        f"variant:           {p.variant} (people={p.people})",
        f"seeds x doses:     {p.seeds} x {p.doses} = {p.runs} cells",
        f"runs:              {p.runs}",
        f"max_samples:       {p.max_samples}",
        f"retry_on_error:    {p.retry_on_error} (same seed and dose; failure kept in the log)",
        f"sample cost_limit: ${ctx.sample_cost_limit:.4f}",
        f"token_limit:       {token}",
        f"exposure:          {exposure_line}",
        f"estimate / cap:    ${estimate:.4f} / ${STEP_CAPS[step]:.2f}",
        f"spent / stop line: ${spent:.4f} / ${STOP_LINE:.2f}",
        f"gateway balance:   ${balance:.4f}",
        f"log dir:           {ctx.log_dir}",
    ]
    if step == "route_check":
        from .harness.route_check import REUSE_SCOPE

        scope = ", ".join(f"{k}={v}" for k, v in sorted(REUSE_SCOPE.items()))
        lines.append(f"local cache:       {f'on (scope {scope})' if ctx.reuse_cache else 'off'}")
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
    reuse_cache: bool = False,
) -> dict[str, Any] | None:
    """Check, launch, record, then the step's own check (route check). Returns the ledger
    line (None for a dry run)."""
    spec = STEPS.get(step)
    if spec is None:
        raise RunnerError(f"unknown step {step!r}")
    if not spec.built:
        raise RunnerError(f"step {step} is not built yet: {spec.not_built}")
    if reuse_cache and step != "route_check":
        raise RunnerError("--reuse-cache runs only with --step route_check")
    assert spec.plan is not None and spec.launch is not None
    one_model(spec.plan, model)  # X-1: refuse before any network call or ledger line
    if sample_cost_limit is None:
        sample_cost_limit = default_sample_cost_limit(step, ledger_path)
    if not (math.isfinite(sample_cost_limit) and sample_cost_limit > 0):
        raise RunnerError("the sample cost limit must be a finite number > 0")
    if token_limit is not None and token_limit <= 0:
        raise RunnerError("the token limit must be > 0")
    token_source = "--token-limit"
    if token_limit is None and spec.plan.token_limit is not None:
        token_limit = spec.plan.token_limit
        token_source = "step default"
    elif token_limit is None:
        token_limit = default_token_limit(ledger_path)
        token_source = "2 x smoke mean"
    spent = budget.spent(ledger_path=ledger_path)  # local; refuses on a missing/bad ledger
    if spec.exposure is not None:
        exposure_line = check_dollar_exposure(step, *spec.exposure(), spent)
    else:
        exposure_line = check_exposure(step, spec.plan, sample_cost_limit, token_limit, spent)

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
        reuse_cache=reuse_cache,
    )
    print(
        ("DRY RUN (no eval launched)\n" if dry_run else "")
        + _plan_text(
            step,
            ctx,
            estimate,
            budget.spent(ledger_path=ledger_path),
            balance,
            exposure_line,
            token_source,
        )
    )
    if dry_run:
        return None

    models = [str(one_model(spec.plan, model)), *spec.plan.aux_models]
    runs = spec.plan.runs
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
    if spec.verify is not None:
        spec.verify(ctx, paths)
    return entry


def list_models_cli(
    step: str, *, env_path: Path | None = None, transport: httpx.BaseTransport | None = None
) -> int:
    """`--step route_check --list-models`: `GET /v1/models`, print only the sorted ids. A
    free metadata call (no model call, no spend), so it skips the guard and writes no ledger
    line. Fails closed with a redacted message."""
    try:
        if step != "route_check":
            raise RunnerError("--list-models runs only with --step route_check")
        ids = budget.list_models(env_path=env_path, transport=transport)
    except (BudgetError, RunnerError) as e:
        print(f"REFUSED: {budget.redact(str(e))}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAILED: {budget.redact(type(e).__name__)}", file=sys.stderr)
        return 1
    print("\n".join(ids))
    return 0


def estimate_smoke_cli(args: argparse.Namespace) -> int:
    """`--estimate-smoke`: T, I, O, h from `--from-log` (turns scaled to the window days),
    each overridable by hand; Haiku prices from `configs/pricing.yaml`. No network, no
    ledger line."""
    from . import estimate

    try:
        given = {
            "turns": args.turns,
            "mean_input": args.mean_input,
            "mean_output": args.mean_output,
            "hit_share": args.hit_share,
        }
        values: dict[str, float] = {}
        if args.from_log is not None:
            m = estimate.measure_log(args.from_log)
            t = estimate.window_turns(m)
            print(
                f"measured: {m.source} ({m.model}): turns {m.turns} over {m.days} days, "
                f"I {m.mean_input:.0f}, O {m.mean_output:.0f}, h {m.hit_share:.3f}; "
                f"T scaled to the window days = {t:.1f} (assumption: same turns per day)"
            )
            values = {
                "turns": t,
                "mean_input": m.mean_input,
                "mean_output": m.mean_output,
                "hit_share": m.hit_share,
            }
        values.update({k: v for k, v in given.items() if v is not None})
        missing = [f"--{k.replace('_', '-')}" for k in given if k not in values]
        if missing:
            raise ValueError(f"give --from-log or all of {', '.join(missing)}")
        dollars, lines = estimate.smoke_estimate(
            values["turns"],
            values["mean_input"],
            values["mean_output"],
            values["hit_share"],
            estimate.haiku_prices(),
        )
    except (ValueError, OSError) as e:
        print(f"REFUSED: {budget.redact(str(e))}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    print(f"smoke estimate: ${dollars:.4f} per run (Haiku, window; before the one rerun)")
    return 0


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
    ap.add_argument("--step", choices=list(STEP_CAPS))
    ap.add_argument("--estimate", type=float, default=None, help="$; must cover one rerun")
    ap.add_argument("--token-limit", type=int, default=None)
    ap.add_argument("--sample-cost-limit", type=float, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--list-models",
        action="store_true",
        help="route_check only: print the gateway's model ids (free metadata call) and exit",
    )
    ap.add_argument(
        "--reuse-cache",
        action="store_true",
        help="route_check only: Inspect's local response cache on, one fixed scope",
    )
    est = ap.add_argument_group("smoke estimate (DD §13.3; local arithmetic, no network)")
    est.add_argument("--estimate-smoke", action="store_true", help="print the estimate and exit")
    est.add_argument("--from-log", type=Path, default=None, help="a measured .eval (G-free)")
    est.add_argument("--turns", type=float, default=None, help="T: turns per smoke run")
    est.add_argument("--mean-input", type=float, default=None, help="I: input tokens/turn")
    est.add_argument("--mean-output", type=float, default=None, help="O: output tokens/turn")
    est.add_argument("--hit-share", type=float, default=None, help="h: cache-read share")
    args = ap.parse_args(argv)
    if args.estimate_smoke:
        return estimate_smoke_cli(args)
    if args.step is None:
        ap.error("--step is required (except with --estimate-smoke)")
    if args.list_models:
        return list_models_cli(args.step, env_path=env_path, transport=transport)
    if args.estimate is None:
        ap.error("--estimate is required (except with --list-models)")
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
            reuse_cache=args.reuse_cache,
        )
    except CheckFailed as e:
        print(f"FAILED: {budget.redact(str(e))}", file=sys.stderr)
        return 1
    except (BudgetError, RunnerError) as e:
        print(f"REFUSED: {budget.redact(str(e))}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAILED: {budget.redact(f'{type(e).__name__}: {e}')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
