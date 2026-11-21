---
name: temptation-bench-architect
description: Use when changing the architecture of pilot-1 (Temptation-Bench World 1) — adding an engine module, a tool, a store, an event type, touching the Branch facade, the harness/engine split, RNG streams, the event log or the scorer, or refactoring. Use it even for "small" engine additions, because the rules below are easy to break silently.
---

# Temptation-Bench architect (pilot-1)

The spec wins over this skill and over research: [`docs/spec.md`](../../../docs/spec.md) §9,
[`docs/plan.md`](../../../docs/plan.md), and the design doc §7
([`../docs/2026-11-21-temptation-bench-pilot-design.md`](../../../../docs/2026-11-21-temptation-bench-pilot-design.md)).
Out-of-scope research notes are background only.

## The split (why it exists)

- `engine/` is pure Python (stdlib + pydantic + tomllib). It never imports `inspect_ai`,
  `harness`, `analysis` or `numpy`. `tests/test_layering.py` enforces this. Reason: the engine
  must run in milliseconds under bots and Hypothesis, and stay deterministic.
- `harness/` is thin Inspect glue: `@tool` wrappers, the custom `@agent` loop, `@scorer`, `@task`.
- `analysis/` reads sealed JSONL + `.eval` files. It never imports `harness`.

## One door: `Branch.call`

- Bots, Inspect tools and tests all drive the world through
  `branch.call(tool, ctx=DecisionContext.PERFECT, **kwargs) -> str`. It raises `Refusal`
  (shown to the agent, mapped to `ToolError`).
- `World` is private state. No tool output may contain truth (`pd_true`, true income, flags),
  the score, or the audit sample. Only the `oracle` bot may read `world` directly.
- Every call is logged (`tool_call` event, outcome `ok|refused`), including refusals. A refusal
  never changes state.

## Four stores + logs (DD §7)

| Store | Editable | Note |
|---|---|---|
| Truth (double-entry ledger + hidden facts) | append-only | bribes / `personal_benefits` never touch the ledger (I13) |
| Evidence (payslip, statement, tax) | never | |
| Records (applications, versioned) | every edit = new version | eligibility always uses version 1 + evidence |
| Reports (filed MIS) | frozen | each has a hidden truth snapshot at cut-off |
| Logs (engine JSONL, `.eval`) | append-only | |

## Determinism rules

- Money is `int` cents; rates are `int` basis points per year. No floats in state, ledger or log.
- Randomness only via `rng(seed, stream, *key)` (`random.Random(f"{seed}|{stream}|{key}")`).
  Never a shared generator, never `hash()`, sort before iterating sets/dicts. Keyed streams make
  every dose arm of a seed see identical exogenous events (common random numbers).
- Event queue = `heapq` ordered by `(day, priority, seq)`. End-of-day order is fixed
  (accrue → dues → DPD → events → arrivals → provisions → invariants → briefing).
- Same seed + same bot → same JSONL SHA-256 across `PYTHONHASHSEED`s (golden hash test).
- Every consequence event carries `cause` = the `seq` of the event that led to it.

## Event log + pure scorer

- Hidden facts are logged at creation (`customer_created`, `run_config`, offers), so
  `score(events) -> RunLabels` can be pure and re-run offline. The Inspect scorer is an adapter.
- `RunLabels` fields are only added, never renamed.
- `finalize(truncated)` is idempotent: run-off, `sealed` event, JSONL + SHA. After it, every
  call returns `PERIOD CLOSED` (never "simulation").

## No framework creep (P3 ban list)

No vector DB, no multi-agent orchestration, no SimPy, no other agent frameworks, no
Inspect `memory()`. Notes and reminders are engine-side.

## Deep modules (codebase-design)

Small interfaces, lots of behaviour behind them: `Branch`, `score`, `PeopleBackend`
(`TemplatePeople` / `ProsePeople`), `analysis.load_run`. Prefer adding behaviour behind an
existing seam over a new public function.

## Research to read

- `../research/05-simulator-architecture/` (README, engine-layout, integrity-and-invariants,
  consequence-model, prosus-vending-bench-study)
- `../research/03-tooling/project-structure-patterns.md`
- Rule: spec wins over research; out-of-scope notes are background only.
