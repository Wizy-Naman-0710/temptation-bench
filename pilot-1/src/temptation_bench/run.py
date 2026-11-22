"""Paid runner: the only way a paid (or gateway) eval is launched (spec §7.2, §7.3).

    uv run python -m temptation_bench.run --step gfree --estimate 0 --token-limit 800000

Order: refuse an unbuilt step (no network) -> `budget.check` (fails closed) -> print the
plan -> (stop here with `--dry-run`) -> `inspect_ai.eval(...)` -> `budget.record` (always,
even if the eval raised, because money may have been spent).

- Per-sample `cost_limit` = `--sample-cost-limit`, else 2 x the measured smoke cost per run
  from the ledger (spec D9); the smoke and the steps before it use \\$1.00, lowered so the
  worst case fits the step cap (the smoke: \\$0.50).
- Worst-case exposure (R25-2): runs x sample cost limit x (1 + retries). A paid step refuses
  if it is over the step cap, if the step's earlier ledger spend + exposure is over the step
  cap (F-7: every paid step; not gfree, whose cap is \\$0 and which is bounded in tokens),
  if spent + exposure is over the stop line, or if it is unknown
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
- `--step route_check` (Task 30): 2 Haiku calls + 1 people-model call (`harness/route_check.py`),
  no automatic rerun, Inspect's local response cache off (`--reuse-cache`: on, one fixed
  scope). Its exposure is its own token worst case from spec prices (`worst_case`), not
  runs x limit x attempts. After `record`, the PASS/FAIL table is printed from the log; a
  FAIL exits 1 with the §7.2 note "route fallback needs a fresh owner OK" and never tries
  another route.
- `--estimate-smoke` (Task 30): DD §13.3 arithmetic from `--from-log` and/or `--turns`,
  `--mean-input`, `--mean-output`, `--hit-share` (`estimate.py`). Local only: no guard,
  no network, no ledger line.
- `--step pregen` (Task 31): one eval of the Task 26 `pregen_people` task for seeds
  1001-1003 with the people model (`PEOPLE`, both the eval model and the `people` role),
  writing `configs/people_prose/seed_<n>.json`. It covers the D1-D10 exogenous texts only
  (planned arrivals' purposes, T1's D8 email, V1's C3 note): enough for window mode. A
  full_run (D11-D30 arrivals) needs a longer pregen first. No automatic rerun, local
  response cache off, a small `max_tokens`; exposure = samples x (2 x the longest prompt's
  local tokens x the highest input price + max_tokens x output price) x (1 + max_retries)
  (`pregen_people.worst_case`). After `record`, the per-file ok / rejected / missing counts
  are printed; a missing seed file exits 1. Read every file by hand before committing.
- `--step mini_batch` (Task 31): Haiku, then Luna, one eval each (X-1), each with its own
  guard call and ledger line (`runs` = 6, its own cells), logs in
  `logs/paid/mini_batch-<stamp>/<model>/`. Window, people=prose, doses {0, 3_000_000} x seeds
  1001-1003, `max_samples=2`. The worst case of all evals to run (12 runs x cost limit x 2
  attempts) plus what earlier mini_batch lines spent must fit the \\$5.00 cap and the stop
  line; it is re-checked before Luna with what Haiku spent. An eval that raises stops the
  step. `--model <slug>` runs just one of the two. Each line's `estimate` is the step
  estimate's share by runs. people=prose refuses (no network) until the pregen files exist.
- `--step full_run` (Task 34): Haiku, variant `full` (D1-D30), seed 1001, dose 3_000_000,
  people = the variant's (template), one eval like the smoke (per-cell cache on, logs in
  `logs/paid/full_run-<stamp>/`, ledger `runs` = 1). Its own defaults (controller rulings):
  per-sample cost limit \\$0.50 (1 run x \\$0.50 x 2 attempts = \\$1.00 <= the \\$1.50 cap)
  and token limit 2,605,728 = 2 x 3 x the smoke's 434,288 tokens per run (the window's
  2 x smoke mean would stop a 30-day run early). That limit is a fixed design value set
  from the Task 30 smoke (a literal, not read from the ledger; PROGRESS §8): re-derive it
  for another model or a prose arm. Both flags override; exposure is still
  checked, and earlier full_run spend counts against its cap. The time limit (10800 s) and
  the turn caps (600 per run, 40 per day) come from `configs/variants/full.toml`.

Runbook: rerunning a deterministic harness error (Task 31; nothing new built for it).
- What exists: `retry_on_error=1` (one automatic same-seed rerun inside the eval) and the
  per-cell output cache (`settings.cell_scope`). A rerun of a cell replays its cached
  outputs, so a harness error that is deterministic given those outputs fails again, at
  \\$0 for the replayed turns.
- Fix the harness first (a mockllm test that reproduces it), then rerun the same step
  through this runner, for mini_batch with `--model <slug>` for the affected model only.
  The replayed turns before the failure point are free; once the fixed harness changes an
  input, the cache misses and the rest is fresh (paid). Completed cells of that eval
  replay fully cached, also \\$0. The report keeps one run per cell: labelled, without a
  sample error, fresh before cached; the errored copy is listed with its error text.
- If the cached outputs themselves must be dropped (the failure is in what the model
  said), the existing ways are: (a) `cell_scope(..., retry=k)` gives `...|retry<k>`, but it
  is not wired to any task or CLI parameter (`harness/agent.py` never passes `retry`), so
  using it needs a controller-approved code change; (b) a fresh, empty `INSPECT_CACHE_DIR`
  for the rerun process (Inspect `model/_cache.py` `_cache_root`), which makes every cell
  of that eval a fresh paid run: re-estimate first.
- Inspect's `eval_retry` / `inspect eval-retry <log>` exists (`_eval/eval.py`) and reruns
  only the failed samples of a log, but it bypasses this runner (no `budget.guard`, no
  ledger line), so it must not be used for a paid rerun. It also keeps the same cell
  scope, so it would replay into the same deterministic error.
- The eval process itself loads `.env` (Inspect does this). Nothing here exports it."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
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
NEEDS_SMOKE = {"mini_batch"}  # its per-sample limit comes from the smoke
# Earlier ledger lines of the step count against its cap too (F-7: every paid step, so a
# rerun cannot exceed the step cap). Not gfree: its cap is $0 and the ledger already holds
# its $0.0038 at list price, so a cumulative check would refuse it forever; its bound is
# the free-tier token count (check_exposure).
STEP_SPEND_COUNTS = {"smoke", "route_check", "pregen", "mini_batch", "full_run"}


class RunnerError(RuntimeError):
    """The runner refuses (unbuilt step, missing smoke measurement). Nothing was launched."""


class CheckFailed(RuntimeError):
    """A step ran (and was recorded) but its own check failed (the route check)."""


def _count(csv: str) -> int:
    return len([x for x in csv.split(",") if x.strip()])


def _ints(csv: str) -> list[int]:
    return [int(x) for x in csv.replace(" ", "").split(",") if x]


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
    aux_models: tuple[str, ...] = ()  # other models the step calls (route check: people)
    samples: int | None = None  # set: the eval's sample count (pregen: one per text)
    uses_token_limit: bool = True  # False: the step's task takes no token limit (pregen)
    sample_cost_limit: float | None = None  # the step's default per-sample $ limit (full_run)
    token_note: str = ""  # where the step's default token limit comes from (dry-run line)

    @property
    def attempts(self) -> int:
        """Worst-case runs of one sample: the attempt plus its automatic reruns."""
        return 1 + self.retry_on_error

    @property
    def runs(self) -> int:
        if self.samples is not None:
            return len(self.models) * self.samples
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
    split_models: bool = False  # one eval per plan model, in turn, each recorded (mini_batch)

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


def launch_pregen(ctx: Ctx) -> None:
    """The people pregen (Task 26 task, Task 31 launch): one `inspect_ai.eval` of
    `pregen_people` for the plan's seeds. The people model is both the eval's model (never
    called by the solver) and the `people` role. No automatic rerun: a sample that fails
    leaves its key out, so the engine uses the template and logs `people_fallback`."""
    from .harness.pregen_people import pregen_people
    from .harness.routes import model_args_for

    p = ctx.plan
    model = one_model(p, ctx.model)
    kw: dict[str, Any] = {}
    if ctx.display is not None:
        kw["display"] = ctx.display
    inspect_eval(
        pregen_people(seeds=p.seeds),
        model=model,
        model_roles={"people": model},
        model_args=model_args_for(str(model)) if isinstance(model, str) else {},
        log_dir=str(ctx.log_dir),
        max_samples=p.max_samples,
        retry_on_error=p.retry_on_error,
        cost_limit=ctx.sample_cost_limit,
        **kw,
    )


def pregen_exposure() -> tuple[float, str]:
    from .harness import pregen_people as pg

    plan = STEPS["pregen"].plan
    assert plan is not None
    return pg.worst_case(plan.seeds, plan.models[0])


def verify_pregen(ctx: Ctx, paths: list[Path]) -> None:
    """Print, per seed file, how many texts are ok / rejected / missing (the template is
    used for the last two). A missing seed file raises `CheckFailed` (a prose run would
    refuse it). Read every file by hand before committing it (spec §5)."""
    from .engine.config import load_config, people_prose_dir
    from .engine.people import entry_key, prose_jobs, prose_path
    from .harness.pregen_people import PREGEN_DAYS

    cfg = load_config("window")
    missing_files = []
    for seed in _ints(ctx.plan.seeds):
        path = prose_path(seed, people_prose_dir())
        want = {entry_key(j.person, j.msg_key) for j in prose_jobs(cfg, seed, PREGEN_DAYS)}
        if not path.exists():
            missing_files.append(path.name)
            print(f"pregen: {path.name}: MISSING ({len(want)} texts expected)")
            continue
        texts = json.loads(path.read_text()).get("texts", {})
        ok = sum(1 for k in want if texts.get(k, {}).get("ok") is True)
        rejected = sum(1 for k in want if k in texts and texts[k].get("ok") is not True)
        print(
            f"pregen: {path.name}: {len(want)} texts, {ok} ok, {rejected} rejected, "
            f"{len(want - set(texts))} missing (template used for rejected and missing); "
            f"{path}"
        )
    if missing_files:
        raise CheckFailed(f"pregen wrote no file for {', '.join(missing_files)}")


HAIKU = "anthropic/claude-haiku-5-5"
# the people role (harness/routes.py PEOPLE_MODEL; spec D4 named qwen3.7-flash, swapped
# after the gateway 403, PROGRESS §8)
PEOPLE = "openai-api/xpl/mistral-small-3.2-24b-instruct"
FREE_TIER = 1_000_000  # Luna free tier: 1M tokens/day (spec §6 G-free)
GFREE_TOKEN_LIMIT = 800_000  # spec §6 G-free
LUNA = "openai-api/xpl/gpt-6-luna"
# full_run (Task 34 controller rulings): 1 run x $0.50 x 2 attempts = $1.00 <= the $1.50 cap.
# Token limit: a fixed design value from the Task 30 smoke (PROGRESS §8), not read from the
# ledger: 2 x (3 x that smoke's measured tokens per run), since full mode has ~3x the
# window's turns; the window's "2 x smoke mean" default (868,576) would cut it short. It
# fits Haiku, template people; re-derive it for another model or a prose arm.
FULL_SAMPLE_COST_LIMIT = 0.50
SMOKE_TOKENS_PER_RUN = 434_288  # the smoke ledger line's total_tokens / runs (Task 30)
FULL_TOKEN_LIMIT = 2 * 3 * SMOKE_TOKENS_PER_RUN  # 2,605,728


def _pregen_samples(seeds: str) -> int:
    """One pregen sample per (seed, person, msg_key) of the D1-D10 exogenous texts."""
    from .engine.config import load_config
    from .engine.people import prose_jobs
    from .harness.pregen_people import PREGEN_DAYS

    cfg = load_config("window")
    return sum(len(prose_jobs(cfg, seed, PREGEN_DAYS)) for seed in _ints(seeds))


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
    # Task 30: 2 Haiku calls (same >= 5k-token prefix, one tool) + 1 people call; no rerun
    "route_check": Step(
        Plan((HAIKU,), "route_check", "-", "-", "-", retry_on_error=0, aux_models=(PEOPLE,)),
        launch_route_check,
        exposure=route_check_exposure,
        verify=verify_route_check,
    ),
    # Task 30: Haiku, decision window, seed 1001, dose $30k
    "smoke": Step(Plan((HAIKU,), "window", "1001", "3000000", max_samples=1), launch_task_eval),
    # Task 31: the people model rewrites the D1-D10 exogenous texts of seeds 1001-1003
    "pregen": Step(
        Plan(
            (PEOPLE,),
            "pregen",
            "1001,1002,1003",
            "-",
            "-",
            max_samples=2,
            retry_on_error=0,
            samples=_pregen_samples("1001,1002,1003"),
            uses_token_limit=False,
        ),
        launch_pregen,
        exposure=pregen_exposure,
        verify=verify_pregen,
    ),
    # Task 31: Haiku, then Luna (one eval each, X-1) x doses {0, $30k} x seeds 1001-1003
    "mini_batch": Step(
        Plan((HAIKU, LUNA), "window", "1001,1002,1003", "0,3000000", "prose", max_samples=2),
        launch_task_eval,
        split_models=True,
    ),
    # Task 34: Haiku, full horizon (D1-D30), seed 1001, dose $30k (spec §7.2 full-horizon look)
    "full_run": Step(
        Plan(
            (HAIKU,),
            "full",
            "1001",
            "3000000",
            max_samples=1,
            sample_cost_limit=FULL_SAMPLE_COST_LIMIT,
            token_limit=FULL_TOKEN_LIMIT,
            token_note=f"2 x 3 x the smoke's {SMOKE_TOKENS_PER_RUN} tokens per run, full mode",
        ),
        launch_task_eval,
    ),
}


def default_sample_cost_limit(step: str, ledger_path: Path | None = None) -> float:
    """2 x the latest smoke's actual cost per run (spec D9). For the smoke and earlier: $1,
    lowered to cap / (runs x attempts) so the worst case fits the step cap (smoke: $0.50).
    A free-tier step keeps $1: its bound is the free-tier token count. A step with its own
    `Plan.sample_cost_limit` (full_run: $0.50, controller ruling) uses that."""
    spec = STEPS.get(step)
    plan = spec.plan if spec is not None else None
    if plan is not None and plan.sample_cost_limit is not None:
        return plan.sample_cost_limit
    if step not in NEEDS_SMOKE:
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


def step_spent(step: str, ledger_path: Path | None = None) -> float:
    """Σ `actual` of the ledger lines of `step` (its earlier evals count against its cap)."""
    return float(
        sum(
            e["actual"]
            for e in budget.ledger_entries(ledger_path=ledger_path)
            if e.get("step") == step
        )
    )


def check_exposure(
    step: str,
    plan: Plan,
    sample_cost_limit: float | None,
    token_limit: int | None,
    spent: float,
    prior: float = 0.0,
) -> str:
    """Refuse (BudgetError) a worst case the step cap or the stop line cannot hold (R25-2).
    `prior` = what earlier evals of this step already spent (`step_spent`; every step in
    STEP_SPEND_COUNTS): it counts against the step cap too. Returns the exposure line."""
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
    if prior + e > cap:
        raise BudgetError(
            f"{step} already spent ${prior:.4f} + worst-case exposure ${e:.4f} ({how}) is over "
            f"the {step} cap ${cap:.2f} (needs owner OK)"
        )
    if spent + e > STOP_LINE:
        raise BudgetError(
            f"spent ${spent:.4f} + worst-case exposure ${e:.4f} ({how}) is over the "
            f"${STOP_LINE:.2f} stop line"
        )
    return f"${e:.4f} ({how})"


def check_dollar_exposure(step: str, e: float, how: str, spent: float, prior: float = 0.0) -> str:
    """A step's own $ worst case must fit its cap and the stop line (R25-2). `prior` = what
    earlier evals of this step already spent (`step_spent`): it counts against the cap."""
    cap = STEP_CAPS[step]
    if not math.isfinite(e) or e < 0:
        raise BudgetError(f"{step} worst-case exposure is unknown")
    if e > cap:
        raise BudgetError(
            f"{step} worst-case exposure ${e:.4f} ({how}) is over the {step} cap ${cap:.2f}"
        )
    if prior + e > cap:
        raise BudgetError(
            f"{step} already spent ${prior:.4f} + worst-case exposure ${e:.4f} ({how}) is over "
            f"the {step} cap ${cap:.2f} (needs owner OK)"
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
    cost_source: str = "",
) -> str:
    p = ctx.plan
    models = [str(one_model(p, ctx.model)), *(f"{m} (people)" for m in p.aux_models)]
    token = f"{ctx.token_limit} ({token_source})" if ctx.token_limit is not None else "none"
    if p.samples is not None:  # pregen: the people model is the eval's only model
        models = [f"{m} (people)" for m in p.models]
        cells = [
            f"samples:           {p.runs} (D1-D10 exogenous texts of seeds {p.seeds}; "
            "window mode only)",
        ]
    else:
        cells = [
            f"variant:           {p.variant} (people={p.people})",
            *_variant_lines(step, p),
            f"seeds x doses:     {p.seeds} x {p.doses} = {p.runs} cells",
            f"runs:              {p.runs}",
        ]
    if not p.uses_token_limit:
        token = "none (not used by this step)"
    lines = [
        f"step:              {step}",
        f"models:            {', '.join(models)}",
        *cells,
        f"max_samples:       {p.max_samples}",
        f"retry_on_error:    {p.retry_on_error} "
        + (
            "(same seed and dose; failure kept in the log)"
            if p.retry_on_error
            else "(no automatic rerun)"
        ),
        f"sample cost_limit: ${ctx.sample_cost_limit:.4f}"
        + (f" ({cost_source})" if cost_source else ""),
        f"token_limit:       {token}",
        *_harness_lines(step, p),
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
    if step == "pregen":
        from .engine.config import people_prose_dir

        lines.append("local cache:       off (every call asks the model)")
        lines.append(f"writes:            {people_prose_dir()}/seed_<n>.json")
    return "\n".join(lines)


def _is_task_eval(step: str) -> bool:
    spec = STEPS.get(step)
    return spec is not None and spec.launch is launch_task_eval


def _variant_lines(step: str, p: Plan) -> list[str]:
    """The days a `temptation_bench` eval covers, and (prose past D10) the template note."""
    if not _is_task_eval(step):
        return []
    from .engine.config import load_config
    from .harness.pregen_people import PREGEN_DAYS

    last = int(load_config(p.variant).last_day)
    lines = [f"days:              D1-D{last}"]
    if p.people == "prose" and last > PREGEN_DAYS:
        lines.append(
            f"people note:       prose covers D1-D{PREGEN_DAYS} only; the "
            f"D{PREGEN_DAYS + 1}-D{last} people messages use the template"
        )
    return lines


def _harness_lines(step: str, p: Plan) -> list[str]:
    """The variant's harness limits and the cache mode of a `temptation_bench` eval."""
    if not _is_task_eval(step):
        return []
    from .engine.config import load_config

    h = load_config(p.variant).harness
    return [
        f"time_limit:        {int(h['time_limit_s'])} s (variant {p.variant})",
        f"turn caps:         {int(h['turn_cap'])} per run, {int(h['day_turn_cap'])} per day "
        f"(variant {p.variant})",
        "local cache:       on, per-cell scope (as the smoke)",
    ]


def check_prose(plan: Plan) -> None:
    """A `people=prose` plan needs every seed's pregen file (local; before any network)."""
    if plan.people != "prose":
        return
    from .engine.people import make_people

    for seed in _ints(plan.seeds):
        try:
            make_people("prose", seed)
        except (OSError, ValueError) as e:
            raise RunnerError(
                f"people=prose needs the pregen file for seed {seed}; run --step pregen "
                f"first ({type(e).__name__}: {e})"
            ) from None


def _model_tag(model: str) -> str:
    return str(model).rsplit("/", 1)[-1]


def run_step(
    step: str,
    estimate: float,
    *,
    token_limit: int | None = None,
    sample_cost_limit: float | None = None,
    dry_run: bool = False,
    model: Model | None = None,
    select_model: str | None = None,
    log_root: Path | None = None,
    env_path: Path | None = None,
    ledger_path: Path | None = None,
    transport: httpx.BaseTransport | None = None,
    display: str | None = None,
    reuse_cache: bool = False,
) -> dict[str, Any] | None:
    """Check, launch, record, then the step's own check (route check, pregen). Returns the
    (last) ledger line (None for a dry run).

    A `split_models` step (mini_batch) runs one eval per plan model, in turn (X-1), each with
    its own guard call and ledger line (`runs` = that eval's cells). `select_model` (CLI
    `--model`) runs only that model's eval. The worst case of every eval to run is checked
    up front, and again (with the money spent so far) before each later eval; an eval that
    raises stops the step. Each ledger line's `estimate` is the step estimate's share by
    runs. `model` (tests) replaces the model of every eval."""
    spec = STEPS.get(step)
    if spec is None:
        raise RunnerError(f"unknown step {step!r}")
    if not spec.built:
        raise RunnerError(f"step {step} is not built yet: {spec.not_built}")
    if reuse_cache and step != "route_check":
        raise RunnerError("--reuse-cache runs only with --step route_check")
    assert spec.plan is not None and spec.launch is not None
    plan = spec.plan
    if select_model is not None:
        if not spec.split_models:
            raise RunnerError(
                f"--model works only with a step that runs one eval per model, not {step}"
            )
        if select_model not in plan.models:
            raise RunnerError(f"{select_model} is not a model of {step} ({', '.join(plan.models)})")
        plan = replace(plan, models=(select_model,))
    evals = [replace(plan, models=(m,)) for m in plan.models] if spec.split_models else [plan]
    for p in evals:
        one_model(p, model)  # X-1: refuse before any network call or ledger line
    check_prose(plan)
    cost_source = "--sample-cost-limit"
    if sample_cost_limit is None:
        sample_cost_limit = default_sample_cost_limit(step, ledger_path)
        cost_source = (
            "step default"
            if plan.sample_cost_limit is not None
            else "2 x smoke cost per run"
            if step in NEEDS_SMOKE
            else "default"
        )
    if not (math.isfinite(sample_cost_limit) and sample_cost_limit > 0):
        raise RunnerError("the sample cost limit must be a finite number > 0")
    if token_limit is not None and token_limit <= 0:
        raise RunnerError("the token limit must be > 0")
    if token_limit is not None and not plan.uses_token_limit:
        raise RunnerError(f"--token-limit is not used by step {step}")
    token_source = "--token-limit"
    if not plan.uses_token_limit:
        token_limit = None
    elif token_limit is None and plan.token_limit is not None:
        token_limit = plan.token_limit
        token_source = f"step default: {plan.token_note}" if plan.token_note else "step default"
    elif token_limit is None:
        token_limit = default_token_limit(ledger_path)
        token_source = "2 x smoke mean"
    total_runs = sum(p.runs for p in evals)

    def check(todo: Plan) -> str:  # local: the step cap and the stop line (R25-2)
        spent = budget.spent(ledger_path=ledger_path)  # refuses on a missing/bad ledger
        prior = step_spent(step, ledger_path) if step in STEP_SPEND_COUNTS else 0.0
        if spec.exposure is not None:
            return check_dollar_exposure(step, *spec.exposure(), spent, prior)
        return check_exposure(step, todo, sample_cost_limit, token_limit, spent, prior)

    exposure_line = check(plan)
    balance = budget.guard(
        step, estimate, env_path=env_path, ledger_path=ledger_path, transport=transport
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    step_dir = Path(log_root or LOG_ROOT) / f"{step}-{stamp}"

    def ctx_for(p: Plan) -> Ctx:
        tag = _model_tag(p.models[0]) if spec.split_models else ""  # the plan's model
        return Ctx(
            step=step,
            plan=p,
            log_dir=step_dir / tag if tag else step_dir,
            sample_cost_limit=float(sample_cost_limit),
            token_limit=token_limit,
            model=model,
            display=display,
            reuse_cache=reuse_cache,
        )

    def text(p: Plan, line: str) -> str:
        return _plan_text(
            step,
            ctx_for(p),
            estimate * p.runs / total_runs,
            budget.spent(ledger_path=ledger_path),
            balance,
            line,
            token_source,
            cost_source,
        )

    head = "DRY RUN (no eval launched)\n" if dry_run else ""
    if spec.split_models:
        print(
            f"{head}step {step}: {len(evals)} evals, one per model, in turn\n"
            f"exposure:          {exposure_line}\n"
            f"estimate / cap:    ${estimate:.4f} / ${STEP_CAPS[step]:.2f}"
        )
        head = ""
    entry: dict[str, Any] | None = None
    for i, p in enumerate(evals):
        line = exposure_line
        if spec.split_models:
            if i > 0:  # re-check the rest with what the earlier evals spent
                rest = replace(plan, models=tuple(q.models[0] for q in evals[i:]))
                check(rest)
                left = estimate * rest.runs / total_runs
                balance = budget.guard(
                    step, left, env_path=env_path, ledger_path=ledger_path, transport=transport
                )
            line = check_exposure(step, p, sample_cost_limit, token_limit, 0.0)
            print(f"\neval {i + 1} of {len(evals)}: {one_model(p, model)}")
        print(head + text(p, line))
        if dry_run:
            continue
        entry = _launch_and_record(
            spec,
            ctx_for(p),
            estimate * p.runs / total_runs,
            balance,
            env_path=env_path,
            ledger_path=ledger_path,
            transport=transport,
        )
    return entry


def _launch_and_record(
    spec: Step,
    ctx: Ctx,
    estimate: float,
    balance: float,
    *,
    env_path: Path | None,
    ledger_path: Path | None,
    transport: httpx.BaseTransport | None,
) -> dict[str, Any]:
    """One eval: launch, `record` (always, even if the eval raised), then the step's check."""
    assert spec.launch is not None
    step, p = ctx.step, ctx.plan
    models = [str(one_model(p, ctx.model)), *p.aux_models]
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
            p.runs,
            estimate,
            paths,
            balance_before=balance,
            error=error,
            env_path=env_path,
            ledger_path=ledger_path,
            transport=transport,
        )
        print(
            f"recorded: {step} {models[0]} actual ${entry['actual']:.4f} "
            f"({entry['actual_source']}); "
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
        "--model",
        default=None,
        help="mini_batch only: run just this model's eval (default: every model, in turn)",
    )
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
            select_model=args.model,
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
