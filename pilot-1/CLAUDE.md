# Pilot-1 (Temptation-Bench World 1)

**Start every session by reading [`PROGRESS.md`](PROGRESS.md).** It says what is done, what is next, which skills to load, and the spend so far.

## Loading skills and research is mandatory

- **At session start:** follow PROGRESS.md **§3.0 "Load these first"** step by step. It checks the tools are installed, invokes `superpowers:using-superpowers` and the execution skill, and sets up Context7 for Inspect.
- **Before each task:** invoke every skill on that task's **Skills:** line in PROGRESS.md §2 (exact Skill-tool names; details in §3b), and read its **Read:** notes (sections in §3a). Do this before you write any code for the task. Log it in §7.
- Use exact names. Trail of Bits skills are plugin skills: `modern-python:modern-python`, `property-based-testing:property-based-testing`, `dimensional-analysis:dimensional-analysis`, `mutation-testing:mutation-testing`.
- **If a skill or Context7 is missing or disabled: stop and ask the owner.** Never install, enable or update tools yourself.
- Inspect docs: Context7 library `/websites/inspect_aisi_uk`, or a page from `../claude-tooling/inspect-ai-context.md`. The installed `inspect-ai==0.3.291` wins over any doc.
- The spec wins over research and over skills. Out-of-scope notes are background only.

## Rules

- Plan: [`docs/plan.md`](docs/plan.md) (fixed; tick boxes in PROGRESS.md, not here)
- Spec: [`docs/spec.md`](docs/spec.md) (approved 2026-11-22)
- Run everything with `uv run` from this folder. `modern-python` shims intercept `python script.py` and `pip`.
- Never export or source `ANTHROPIC_*` / `XPL_*` variables in a shell. Never print or commit `.env`.
- Paid model calls only via `uv run python -m temptation_bench.run` (budget guard; \$9.50 stop line). Never set `OPENROUTER_API_KEY` / `PARALLEL_API_KEY` (paid `literature-review` scripts).
- Don't write outside `pilot-1/`. The one exception is the single pointer line in `../claude-tooling/README.md` (Task 2).
- End every session by updating PROGRESS.md and committing on branch `pilot-1`.
