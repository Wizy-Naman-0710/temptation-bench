# Pilot-1 (Temptation-Bench World 1)

**Start every session by reading [`PROGRESS.md`](PROGRESS.md).** It says what is done, what is next, which skills to load, and the spend so far.

- Plan: [`docs/plan.md`](docs/plan.md) (fixed; tick boxes in PROGRESS.md, not here)
- Spec: [`docs/spec.md`](docs/spec.md) (approved 2026-11-22)
- Run everything with `uv run` from this folder.
- Never export or source `ANTHROPIC_*` / `XPL_*` variables in a shell. Never print or commit `.env`.
- Paid model calls only via `uv run python -m temptation_bench.run` (budget guard; \$9.50 stop line).
- Don't write outside `pilot-1/`. The one exception is the single pointer line in `../claude-tooling/README.md` (Task 2).
- End every session by updating PROGRESS.md and committing on branch `pilot-1`.
