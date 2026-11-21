# Pilot-1 Progress Tracker

This is the **live** status file. Every session reads it first and updates it last.

- Plan (fixed, don't tick there): [`docs/plan.md`](docs/plan.md)
- Spec (approved): [`docs/spec.md`](docs/spec.md)
- Last updated: 2026-11-22, end of the planning session
- **Current state: planning done, no code yet. Next: Session S1, Task 1.**
- Deadline: all milestones M0–M7 done by **2026-11-24**

---

## 1. Start here (new session checklist)

Do these in order at the start of **every** session:

- [ ] Read this whole file, especially §4 (next action) and §7 (session log).
- [ ] Read [`docs/spec.md`](docs/spec.md) in full (247 lines). It holds the *why* and every number.
- [ ] Read the plan section for your session only (e.g. "Session S2" in [`docs/plan.md`](docs/plan.md)). Also read the plan's **Global Constraints** and **Review Focus**.
- [ ] Read the design-doc (DD) sections your tasks cite: [`../docs/2026-11-21-temptation-bench-pilot-design.md`](../docs/2026-11-21-temptation-bench-pilot-design.md).
- [ ] Load the skills listed for your session in §3.
- [ ] Run `git status` and `git log --oneline -5` (you should be on branch `pilot-1`), then `cd pilot-1 && uv run pytest -q`. If tests are red, fix that first with `superpowers:systematic-debugging`.
- [ ] Re-read the security rules in §6.

At the end of **every** session:

- [ ] `uv run pytest -q` green, `uv run ruff check .` clean.
- [ ] Tick the tasks you finished in §2.
- [ ] Add a session-log entry in §7: what you did, what surprised you, and any design value you changed and why.
- [ ] Update §4 (next action), §5 (spend) and §8 (decisions/open items).
- [ ] Commit (`pilot-1: S<n> ...`). Never push unless the owner asks.

---

## 2. Milestone and task checklist

Legend: `[ ]` not started · `[~]` in progress (add a note) · `[x]` done (add the commit hash) · `[-]` cut (say why)

### Milestone status

| Milestone | Session | Status | Exit check (from the plan) |
|---|---|---|---|
| M0 Tooling | S1 | not started | scaffold, skills, prices, layering + no-secrets tests |
| M1 Walking skeleton | S1 | not started | mockllm run → `.eval` + sealed JSONL + T1 label + graph 1 |
| M2a Economy | S2 | not started | 30-day bot runs; invariants green; run-off numbers |
| M2b Scenario, tools, scorer, bots | S3 | not started | 18 tools; scorer-on-bots; golden hash; minimal pair; base case |
| M3 Harness complete | S4 | not started | trim/in_window test; loop policies; cache; budget guard |
| M4 People prose | S4 | not started | post-check; mockllm pregen; minimal pair holds under prose |
| M5 Analysis + graphs | S5 | not started | graphs 1–10 render; report.md |
| G-free | S5 | not started | free Luna D1–D3 run; slugs + credits confirmed; \$0 |
| M6 Paid window runs | S5 | not started | route check, smoke, pregen, mini-batch under caps; hand check |
| M7 Full horizon | S6 | not started | D11–D30 + audit; mode-prefix test; optional paid full run |

### S1: M0 tooling + M1 walking skeleton

- [ ] Task 1: Project scaffold (uv, ruff, pytest, `.gitignore`, `.env.example`, layering + no-secrets tests)
- [ ] Task 2: Project skills (architect, banking domain, methodology) + pointer line in `claude-tooling/README.md`
- [ ] Task 3: `pricing.yaml` + `register_prices()` + test
- [ ] Task 4: Engine primitives (money, rng, queue, event log)
- [ ] Task 5: Config + skeleton `Branch` (D1–D3, 7 tools, status line)
- [ ] Task 6: Skeleton scoring (T1 label) + `honest` / `cheater` bots
- [ ] Task 7: Inspect task, agent loop, tools, scorer; mockllm e2e; truncation test
- [ ] Task 8: Graph 1 (tool calls per day)
- [ ] **S1 exit check**

### S2: M2a economy

- [ ] Task 9: Calendar clock + 8-step end-of-day pipeline
- [ ] Task 10: Double-entry ledger + invariants I1–I4, I13 (Hypothesis)
- [ ] Task 11: Credit maths (EMI, n_min, PD, hazards, accrual, buckets) + `dimensional-analysis`
- [ ] Task 12: Customers, evidence, verification, arrivals
- [ ] Task 13: Inherited book, DPD, provisions, `day_close` event, NPL crossing D15–D20
- [ ] Task 14: Run-off, finalize, seal
- [ ] **S2 exit check**

### S3: M2b scenario, tools, scorer, bots

- [ ] Task 15: Versioned records + edit tags
- [ ] Task 16: Planted scenario (T1, C1–C4, D1 email) + `TemplatePeople`
- [ ] Task 17: Remaining 11 tools (18 total), MIS CSV format, size caps
- [ ] Task 18: Full invariants + Hypothesis state machine
- [ ] Task 19: Full scorer (DD §10.1–§10.3)
- [ ] Task 20: All bots, scorer-on-bots, sensitivity base case
- [ ] Task 21: System prompt, target calibration, golden hash, minimal pair
- [ ] **S3 exit check**

### S4: M3 harness + M4 people prose

- [ ] Task 22: `CompactionTrim` + real `in_window` tracking
- [ ] Task 23: Loop policies (nudge, caps, auto-advance, REAL/EVAL probe, transcript spans)
- [ ] Task 24: Model settings (effort low, no seed/temperature) + per-cell cache + `harness.json`
- [ ] Task 25: Budget guard (`budget.py`) + paid runner (`run.py`)
- [ ] Task 26: People prose pregen + post-check + `ProsePeople`
- [ ] **S4 exit check**

### S5: M5 graphs + G-free + M6 paid

- [ ] Task 27: Analysis loaders + stats (Clopper-Pearson, paired exact, HP_norm)
- [ ] Task 28: Graphs 2–10 + `report.md`
- [ ] Task 29: G-free connectivity check (\$0) — **needs the owner's new key in `.env` first**
- [ ] Task 30: Route check (≤ \$0.05) + smoke (≤ \$1.00)
- [ ] Task 31: People pregen (≤ \$0.05) + mini-batch (≤ \$5.00) + hand check of every T1 decision
- [ ] **S5 exit check** (ledger ≤ \$6.60)

### S6: M7 full horizon

- [ ] Task 32: D11–D30 events (MIS #2–#5, boss replies) + internal audit
- [ ] Task 33: Mode-prefix test, full-horizon golden hash, detection-rate range
- [ ] Task 34: Optional paid full run (≤ \$1.50), final report, whole-branch review, wrap-up
- [ ] **S6 exit check**

### "Done means" (spec §1): tick these at the very end, with evidence links

- [ ] All tests green (`uv run pytest -q` output pasted in the S6 log)
- [ ] Paid smoke + mini-batch done, ledger total ≤ \$9.50
- [ ] Graphs built from real logs (`results/*/report.md`)
- [ ] Every T1 decision has exactly one code label and a hand check that agrees

### Never cut (spec §6)

Invariants · golden hash · reminder test · cheater tagging · scorer on bots · mockllm e2e · spend guard

### Cut order if time or money runs short (spec §6)

1. Paid full run (Task 34 step 1)
2. M7 audit (Task 32 audit part)
3. M4 people prose (Task 26; use `people = "template"`)
4. Sensitivity sweep beyond the base case

---

## 3. Skills to load, per session

Check `../claude-tooling/README.md` for what each skill is for. **Superpowers is the core.**

| Session | Process skills | Domain / tool skills |
|---|---|---|
| Every session | `superpowers:using-superpowers`, `superpowers:subagent-driven-development` (or `executing-plans`), `superpowers:test-driven-development`, `superpowers:verification-before-completion`; `superpowers:systematic-debugging` when anything fails | project skills in `pilot-1/.claude/skills/` (after Task 2) |
| S1 | as above | `modern-python` (T1), `anthropic-skills:skill-creator` (T2), `codebase-design` (T5 facade), Context7 `/websites/inspect_aisi_uk` (T3, T7), `dataviz` (T8) |
| S2 | as above | `dimensional-analysis` (T11, T13, T14), `property-based-testing` (T10), `banking-simulation-domain` |
| S3 | `superpowers:dispatching-parallel-agents` (T16/T17 after T15) | `property-based-testing` (T18), `banking-simulation-domain`, `benchmark-methodology`; optional `mutation-testing` on `scoring.py` |
| S4 | as above | Context7 (compaction, `CachePolicy`, limits, `StoreModel`), `benchmark-methodology` |
| S5 | `superpowers:verification-before-completion` **before every paid step** | `dataviz`, `scientific-visualization`, `statistical-analysis` |
| S6 | `superpowers:requesting-code-review`, `superpowers:finishing-a-development-branch` | `banking-simulation-domain` |

### 3b. Skill and tooling map per task (invoke these before the task)

The names below are the exact strings for the **Skill tool**. They match `../claude-tooling/README.md` ("Which tool for which job"). If a skill is missing, check that README's install table and tell the owner. Don't install new packs without asking.

**Always, in every task:**
- `superpowers:using-superpowers` (session start)
- `superpowers:subagent-driven-development` or `superpowers:executing-plans` (whichever is recorded in §4)
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion` (before ticking a box)
- `superpowers:systematic-debugging` (any red test or surprise)
- After Task 2: the project skills `temptation-bench-architect`, `banking-simulation-domain` and `benchmark-methodology`, as listed in this table

**Library docs:**
- Inspect AI: Context7 (`resolve-library-id` → `query-docs`, library `/websites/inspect_aisi_uk`), or fetch a page listed in `../claude-tooling/inspect-ai-context.md`.
- Other libraries (pydantic, Hypothesis, pandas, matplotlib): Context7 via the `documentation-lookup` skill.

| Task(s) | Invoke |
|---|---|
| 1 scaffold | `modern-python:modern-python` |
| 2 project skills | `anthropic-skills:skill-creator`, `superpowers:writing-skills` |
| 3 prices | Context7 (Inspect `set_model_info`, `ModelCost`) |
| 4–5 engine primitives, `Branch` facade | `codebase-design` (deep-module facade), `temptation-bench-architect` |
| 6 skeleton scoring, bots | `benchmark-methodology` |
| 7 Inspect skeleton | Context7 (Inspect agent, `@tool`, `StoreModel`, mockllm), `agent-harness-construction` (tool docstrings and outputs), `temptation-bench-architect` |
| 8 graph 1 | `dataviz`, `scientific-visualization` |
| 9 clock | `temptation-bench-architect` |
| 10 ledger | `property-based-testing:property-based-testing`, `dimensional-analysis:dimensional-analysis` |
| 11 credit maths | `dimensional-analysis:dimensional-analysis`, `property-based-testing:property-based-testing`, `banking-simulation-domain` |
| 12–14 customers, book, run-off | `banking-simulation-domain`, `dimensional-analysis:dimensional-analysis` (13, 14) |
| 15 records | `temptation-bench-architect` |
| 16 scenario | `banking-simulation-domain`, `benchmark-methodology`, `experimental-design` (minimal pairs) |
| 17 tools | `agent-harness-construction`, `banking-simulation-domain` |
| 18 invariants fuzzing | `property-based-testing:property-based-testing` |
| 19 full scorer | `benchmark-methodology`; afterwards `mutation-testing:mutation-testing` on `engine/scoring.py` (do the tests catch bugs?) |
| 20 bots, sensitivity | `banking-simulation-domain`, `benchmark-methodology` |
| 21 prompt, calibration, golden hash | `benchmark-methodology` (no-leak wording), `superpowers:dispatching-parallel-agents` (if running 16/17 in parallel) |
| 22–24 harness | Context7 (`CompactionTrim`, `CachePolicy`, limits, model roles), `agent-harness-construction` |
| 25 budget guard | `cost-aware-llm-pipeline` |
| 26 people prose | Context7 (model roles), `benchmark-methodology` (no-leak check) |
| 27 loaders, stats | `statistical-analysis`, `exploratory-data-analysis`; `statistical-power` (for the "n = 3 is exploratory" caveat) |
| 28 graphs 2–10, report | `dataviz`, `scientific-visualization` |
| 29–31, 34 paid runs | `superpowers:verification-before-completion` **before each paid command**, `cost-aware-llm-pipeline` |
| 32–33 audit, modes | `banking-simulation-domain`, `property-based-testing:property-based-testing` |
| 34 wrap-up | `superpowers:requesting-code-review`, `superpowers:receiving-code-review`, `superpowers:finishing-a-development-branch` |

Not for pilot-1: `literature-review` (it has paid scripts; ask the owner first), and `hypothesis-generation` (pre-registration comes later).

### 3a. Research reading map (read before each task)

The research in `../research/` is the *why* behind every number and rule. Read the listed notes (and sections) before starting a task.

**How the research fits the scope:**
- The spec and the design doc (DD) decide what pilot-1 builds. The research explains why.
- If a research note and the spec disagree, **follow the spec**, and add a note in §8 if it matters.
- If a research note describes something outside pilot-1, treat it as background only. Don't build it.

Start with `../research/README.md` (the index) once per session.

| Task(s) | Read in `../research/` |
|---|---|
| 2 (project skills: link these, don't copy them) | **architect:** `05-simulator-architecture/*`, `03-tooling/project-structure-patterns.md` · **banking:** `02-banking-domain/*` (rulebook, credit-risk, default-timing, calibration-table, customer-behaviour, personas, branch-economics, conduct-gifts, audit) · **methodology:** `04-methodology/*`, `00-papers/*`, `01-prior-work/gap-check.md` |
| 4–5 engine primitives, skeleton `Branch` | `05-simulator-architecture/engine-layout.md` §1–5; `integrity-and-invariants.md` §1; `prosus-vending-bench-study.md` §5–6; `03-tooling/project-structure-patterns.md` §3, §5, §6; `00-papers/vending-bench.md` (agent setup, clock) |
| 6, 19 scoring | `04-methodology/attribution-and-controls.md` §3; `scenario-taxonomy.md` §2–4 |
| 7, 22–24 Inspect harness | `03-tooling/inspect-ai.md` (all); `memory-tools.md` §2–3; `multiagent-and-subagents.md` §2 (model roles); `04-methodology/experiment-matrix.md` §6 (eval-awareness) |
| 9 clock, end-of-day | `02-banking-domain/default-timing-and-horizon.md` §2; `05-simulator-architecture/engine-layout.md` §3; `consequence-model.md` §4 |
| 10, 18 ledger, invariants | `05-simulator-architecture/integrity-and-invariants.md` §2, §5–7; `prosus-vending-bench-study.md` §6 |
| 11 credit maths | `02-banking-domain/credit-risk-and-underwriting.md` §3–6; `default-timing-and-horizon.md` §5–6; `calibration-table.md` |
| 12 customers, arrivals | `02-banking-domain/customer-behaviour-models.md` §2–3; `personas.md` §3, §5, §6; `evergreening-and-loan-fraud.md` §4 (income fraud); `calibration-table.md` |
| 13–14 book, provisions, run-off | `02-banking-domain/default-timing-and-horizon.md` §3; `credit-risk-and-underwriting.md` §6; `branch-economics-and-targets.md` §1–2 (internal pricing); `general-rulebook.md` R5 |
| 15 records, edits | `05-simulator-architecture/integrity-and-invariants.md` §3; `02-banking-domain/evergreening-and-loan-fraud.md` §4 |
| 16 planted scenario | `04-methodology/scenario-taxonomy.md`; `price-of-integrity.md` §3; `experiment-matrix.md` §2 (minimal pairs); `02-banking-domain/personas.md` §2–3; `conduct-gifts-whistleblowing.md` §3–4; `branch-economics-and-targets.md` §5–6 |
| 17 tools | `05-simulator-architecture/engine-layout.md` §5; `02-banking-domain/general-rulebook.md`; `00-papers/blueprint-bench.md` (strict formats); `03-tooling/memory-tools.md` |
| 20 bots | `02-banking-domain/customer-behaviour-models.md` §4; `personas.md` §1 (elite manager = honest bot); `05-simulator-architecture/integrity-and-invariants.md` §7 (exploit attacks) |
| 21 prompt, target calibration | `02-banking-domain/branch-economics-and-targets.md` §4–6; `calibration-table.md`; `00-papers/vending-bench.md` |
| 25, 29–31 budget, paid runs | `04-methodology/experiment-matrix.md` §3, §5; `03-tooling/models-and-pricing.md` (the spec's gateway prices override it) |
| 26 people prose | `03-tooling/multiagent-and-subagents.md` §2–3; `02-banking-domain/personas.md` |
| 27–28 analysis, graphs | `04-methodology/price-of-integrity.md` §6+; `attribution-and-controls.md` §4; `experiment-matrix.md` |
| 32 audit, D11–D30 | `02-banking-domain/audit-and-supervision.md` §3–5; `05-simulator-architecture/consequence-model.md` §2–3; `02-banking-domain/conduct-gifts-whistleblowing.md` §5–6 |
| 33 window vs full mode | `05-simulator-architecture/engine-layout.md` §6 |

**Where pilot-1 knowingly differs from the research (follow the spec):**
- RNG: `project-structure-patterns.md` §4 suggests numpy Generators. Pilot-1 uses the stdlib keyed `random.Random`, and the engine has no numpy.
- Providers and prices: `models-and-pricing.md` assumes direct APIs. Pilot-1 uses the Experiential Labs gateway (spec D1, D4).
- Dates: research notes saying "pilot run 2026-11-22/23" are out of date. The deadline is 2026-11-24.

**Background only (out of pilot-1 scope; P3 or later):**
- `aml-kyc-and-vip-customers.md`
- evergreening methods (`evergreening-and-loan-fraud.md` §1–3)
- sub-agents (`multiagent-and-subagents.md` §4)
- vector DB memory
- price-of-integrity designs (i) and (iii) and B50 estimates
- `gap-check.md` (for writing up later, not for building)

Useful references:
- `../research/03-tooling/inspect-ai.md`: verified Inspect API notes and an agent-loop sketch
- `../claude-tooling/inspect-ai-context.md`: index of Inspect doc pages
- `../research/05-simulator-architecture/engine-layout.md` and `integrity-and-invariants.md` (exploit attacks for Task 20)

---

## 4. Next action

**Execution method:** not chosen yet. Ask the owner once: subagent-driven (recommended) or native. Record the answer here.

**Session S1, Task 1** (project scaffold). Branch `pilot-1` already exists (planning commit 57719a1); skip Task 1 Step 1.

Blocked items (owner only):
- **Revoke the API key that was pasted in chat**, create a new one, and write `pilot-1/.env` from `.env.example` yourself. This is needed only from Task 29 on. Tasks 1–28 cost \$0 (mockllm).

---

## 5. Spend tracker (\$10 hard limit, \$9.50 stop line)

The source of truth is `budget/ledger.jsonl` (from Task 25). Copy each line's totals here.

| Step | Cap | Estimate | Actual | Running total | Date | Notes |
|---|---|---|---|---|---|---|
| G-free (Task 29) | \$0 | \$0 | | | | free Luna |
| Route check (Task 30) | \$0.05 | | | | | |
| Smoke (Task 30) | \$1.00 | ~\$0.13 cached / ~\$0.33 uncached | | | | |
| People pregen (Task 31) | \$0.05 | | | | | |
| Mini-batch (Task 31) | \$5.00 | | | | | 12 runs; drop Luna to 2 seeds if tight |
| Full run (Task 34, optional) | \$1.50 | | | | | |
| **Total** | **\$9.50** | | | | | |

Rules:
- The owner gave **standing approval** up to each cap.
- Anything over a cap, or a route fallback, needs a **fresh OK** from the owner.
- Always run `budget.py check` first. It fails closed.

Measured numbers (fill in from G-free and smoke; used for later estimates):
- Turns per window run: —
- Mean input / output tokens per turn: —
- Cache hit rate h: —
- Cost per window run (Haiku, Luna): —

---

## 6. Security and hard rules (read every session)

- The API key **only** lives in `pilot-1/.env`, which the owner creates. Never print it, log it, commit it, or paste it into chat or docs.
- **Never `export` or `source`** `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `XPL_API_KEY` or `XPL_BASE_URL` in a shell. Claude Code itself reads `ANTHROPIC_*` and would send *your* session through the gateway. Only the eval process loads `.env`.
- To check the file exists, use only `test -s .env && echo present`. Never `cat` it.
- `tests/test_no_secrets.py` must stay green.
- Never write to `../research/`, `../docs/`, `../idea.md` or the root README.
- Never invent result numbers. Design values are proposals; label them so.
- Fictional bank only (Woz Valley Bank, Branch 014; fictional regulator and dollar).
- Agent-facing text never says test, evaluation, benchmark, bribe, cheat or simulation.
- Escape `$` as `\$` in markdown.

---

## 7. Session log

Newest first. One entry per session.

### 2026-11-22: Planning session (no code)
- Wrote and got approval for `docs/spec.md` (two subagent reviews folded in: 3 blockers fixed, 6 builder questions answered).
- Wrote `docs/plan.md` (34 tasks, 6 sessions) and this tracker.
- Owner decisions: build order A (walking skeleton first); all of M0–M7 by 2026-11-24; standing approval for paid steps up to each cap.
- Checked on 2026-11-22: inspect-ai 0.3.291 is the latest on PyPI; uv 0.12.5 and Python 3.13.0 are installed.
- Nothing has been spent: \$0 of \$10.

---

## 8. Decisions and open items

### Decisions made (do not reopen without the owner)

| # | Decision | Where |
|---|---|---|
| 1 | Use the Experiential Labs gateway, not direct provider APIs | spec D1 |
| 2 | People prose is pre-generated offline; agent-dependent texts and the bribe email are always templates | spec §5, D2 |
| 3 | Smoke + 12-run mini-batch instead of the full run matrix | spec D3, §7 |
| 4 | Models: Haiku 5.5 (main agent), gpt-6-luna (second agent), qwen3.7-flash (people); fallback deepseek-v4-flash | spec D4 |
| 5 | Reasoning effort `low` for all models | spec D5 |
| 6 | Build order: walking skeleton, then thicken | spec D6 |
| 7 | The campaign target is calibrated from bots (1.15 × honest mean) | spec D7, Task 21 |
| 8 | Per-sample `cost_limit` = 2 × the measured smoke cost | spec D9 |
| 10 | Watched vs unwatched (O) and pressure (P) are **fixed** in pilot-1 at `normal` / `target` (DD §5A.7); varying them is FULL. Pilot-1 still builds both slots (D1 boss sentence, D2 IT notice) and tags every log with them (Task 16), so FULL only changes config. D2 timing is a designer call | DD §5A.7, plan Task 16 |
| 9 | Plan lives in `pilot-1/docs/plan.md`, not `docs/superpowers/plans/` (owner: keep `docs/` untouched) | this file |

### Design values changed during the build

Log any config value changed to make a test pass, such as the base case or detection rates. Never change a test to make it pass.

| Date | Value | Old → new | Why | Task |
|---|---|---|---|---|
| | | | | |

### Open items / questions for the owner

- [ ] Revoke the pasted key and create `.env` (before Task 29)
- [ ] Merge or push `pilot-1` at the end? (Task 34)
- Longer-term questions stay in `../docs/open-questions.md`. That file is read-only for this pilot; add any new ones here instead.
