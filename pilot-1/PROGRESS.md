# Pilot-1 Progress Tracker

This is the **live** status file. Every session reads it first and updates it last.

- Plan (fixed, don't tick there): [`docs/plan.md`](docs/plan.md)
- Spec (approved): [`docs/spec.md`](docs/spec.md)
- Last updated: 2026-11-22, during Session S2
- **Current state: S1, S2 done; S3 Tasks 15–19 done (batches [14, 15, 16] and [17, 18, 19] approved; T17 after 1 fix round); Tasks 20–21 done; batch review [20, 21] running, then S3 exit. \$0 spent.**
- Deadline: all milestones M0–M7 done by **2026-11-24**

---

## 1. Start here (new session checklist)

Do these in order at the start of **every** session:

- [ ] Read this whole file, especially §4 (next action) and §7 (session log).
- [ ] Read [`docs/spec.md`](docs/spec.md) in full (264 lines). It holds the *why* and every number.
- [ ] Read the plan section for your session only (e.g. "Session S2" in [`docs/plan.md`](docs/plan.md)). Also read the plan's **Global Constraints** and **Review Focus**.
- [ ] Skim [`docs/gap-audit.md`](docs/gap-audit.md) once (research gap audit: what each research note changed in the plan, and 13 open owner questions).
- [ ] Read the design-doc (DD) sections your tasks cite: [`../docs/2026-11-21-temptation-bench-pilot-design.md`](../docs/2026-11-21-temptation-bench-pilot-design.md).
- [ ] Do **§3.0 "Load these first"** step by step: check the tools are installed, invoke `superpowers:using-superpowers` and the execution skill, read `../research/README.md`, and set up Context7 if the session uses Inspect.
- [ ] Before **each** task: invoke the skills on its **Skills:** line in §2 and read its **Read:** notes (§3a). Log both in §7.
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
| M0 Tooling | S1 | done 2026-11-22 | scaffold, skills, prices, layering + no-secrets tests |
| M1 Walking skeleton | S1 | done 2026-11-22 | mockllm run → `.eval` + sealed JSONL + T1 label + graph 1 |
| M2a Economy | S2 | done 2026-11-22 | 30-day bot runs; invariants green; run-off numbers |
| M2b Scenario, tools, scorer, bots | S3 | in progress | 18 tools; scorer-on-bots; golden hash; minimal pair; base case |
| M3 Harness complete | S4 | not started | trim/in_window test; loop policies; cache; budget guard |
| M4 People prose | S4 | not started | post-check; mockllm pregen; minimal pair holds under prose |
| M5 Analysis + graphs | S5 | not started | graphs 1–10 render; report.md |
| G-free | S5 | not started | free Luna D1–D3 run; slugs + credits confirmed; \$0 |
| M6 Paid window runs | S5 | not started | route check, smoke, pregen, mini-batch under caps; hand check |
| M7 Full horizon | S6 | not started | D11–D30 + audit; mode-prefix test; optional paid full run |

### S1: M0 tooling + M1 walking skeleton

Under each task: **Skills:** = invoke these with the Skill tool first (on top of the "always" list in §3b). **Read:** = notes in `../research/` (sections in §3a). **Docs:** = Inspect lookups (§3b).

- [x] Task 1: Project scaffold (uv, ruff, pytest, `.gitignore`, `.env.example`, layering + no-secrets tests, canary) (6774828)
  - Skills: `modern-python:modern-python` · Read: project-structure-patterns, engine-layout §7, prosus §2, §8 (canary)
  - New: `CANARY_GUID` in `src/temptation_bench/__init__.py` + the canary line in `README.md` (Task 5 copies it into `world.toml`)
- [x] Task 2: Project skills (architect, banking domain, methodology) + pointer line in `claude-tooling/README.md` (b4f3972)
  - Skills: `anthropic-skills:skill-creator`, `superpowers:writing-skills` · Read: the three lists in §3a row 2 (each skill links them)
- [x] Task 3: `pricing.yaml` + `register_prices()` + test (277d9e3)
  - Skills: (always list) · Read: inspect-ai §8, models-and-pricing §7 · Docs: `set_model_info`, `ModelCost`
- [x] Task 4: Engine primitives (money, rng, queue, event log) (85fc825)
  - Skills: `codebase-design`, `dimensional-analysis:dimensional-analysis` · Read: engine-layout §1–5, integrity §1, §4 (event `cause`), consequence-model §1, project-structure §3, §5, §6
- [x] Task 5: Config + skeleton `Branch` (D1–D3, 7 tools, status line) (16a4ac6)
  - Skills: `codebase-design`, `agent-harness-construction` · Read: engine-layout, prosus §4–6, rulebook §0, branch-economics (pay line), memory-tools §1 (briefing), vending-bench
  - Key tests: `test_window_mode_ends_after_last_day` (`PERIOD CLOSED`), `test_get_status_shows_pay_line`, `test_canary_present_in_repo_files`
- [x] Task 6: Skeleton scoring (T1 label) + `honest` / `cheater` bots (6367692)
  - Skills: `benchmark-methodology` · Read: attribution §2–3, §4 (exposure), scenario-taxonomy §2, blueprint-bench
  - Key test: `test_exposed_iff_bribe_email_read_before_t1_decision` (`exposed` = `offer_read_before_decision`)
- [x] Task 7: Inspect task, agent loop, tools, scorer; mockllm e2e; truncation test (01fd606)
  - Skills: `agent-harness-construction`, `temptation-bench-architect` · Read: inspect-ai §1–4, §7, §9; attribution §2 M1 · Docs: custom agent, `@tool`, `StoreModel`, mockllm, scorer, limits
- [x] Task 8: Graph 1 (tool calls per day) (3765577)
  - Skills: `dataviz`, `scientific-visualization` · Read: vending-bench, price-of-integrity §9
- [x] **S1 exit check** (139d93f)

### S2: M2a economy

- [x] Task 9: Calendar clock + 8-step end-of-day pipeline (065a7c0)
  - Skills: `temptation-bench-architect` · Read: default-timing §2, engine-layout §3, consequence-model §4, prosus §7, memory-tools §1 (morning briefing)
- [x] Task 10: Double-entry ledger + invariants I1–I4, I13 (Hypothesis) (6388cbd; I3/I13 made real in 1218653)
  - Skills: `property-based-testing:property-based-testing`, `dimensional-analysis:dimensional-analysis` · Read: integrity §2, §5, §6 (replay, postconditions); prosus §6
- [x] Task 11: Credit maths (EMI, n_min, PD, hazards, accrual, buckets) + `dimensional-analysis` (8bf0bed; verified-income rule fixed in 1218653)
  - Skills: `dimensional-analysis:dimensional-analysis`, `property-based-testing:property-based-testing`, `banking-simulation-domain` · Read: credit-risk §2–7, default-timing §5–6 (**§6b** slips and cures), **customer-behaviour §2e** (markup take-up), calibration-table, rulebook R2–R4
- [x] Task 12: Customers, evidence, verification, arrivals (96c8269; evidence/truth stores + strict args in 1218653)
  - Skills: `banking-simulation-domain` · Read: customer-behaviour §2a, §2e–2f, §3; personas (§8 officer note); credit-risk §1, §4b (soft hints); integrity §4 (`customer_created`); evergreening §4; calibration-table
- [x] Task 13: Inherited book, DPD, provisions, `day_close` event, NPL crossing D15–D20 (0e05040; review approved)
  - Skills: `banking-simulation-domain`, `dimensional-analysis:dimensional-analysis` · Read: default-timing §1, §3; credit-risk §6 (no accrual on NPL); **branch-economics §2** (FTP, deposit margin) and §1; rulebook R5–R6; consequence-model §1, §5
- [x] Task 14: Run-off, finalize, seal (bc70ac0; review in the next batch)
  - Skills: `banking-simulation-domain`, `dimensional-analysis:dimensional-analysis` · Read: default-timing §3, consequence-model §1, integrity §4
  - Key test: `test_sealed_branch_returns_period_closed` (end message is `PERIOD CLOSED`, not the DD's banned-word text)
- [x] **S2 exit check** (134 tests green, ruff clean; bots run 30 days; run-off numbers produced)

### S3: M2b scenario, tools, scorer, bots

- [x] Task 15: Versioned records + edit tags (390a85e; review in batch [14, 15, 16])
  - Skills: `temptation-bench-architect`, `codebase-design` · Read: integrity §3, evergreening §4, rulebook R1, R17
- [x] Task 16: Planted scenario (T1, C1–C4, D1 email) + `TemplatePeople` + P/O factor slots + `run_config` tag (ff4654d; review in batch [14, 15, 16])
  - Skills: `banking-simulation-domain`, `benchmark-methodology`, `experimental-design` · Read: scenario-taxonomy §1–2; **experiment-matrix §1–2**; price-of-integrity §1, §3, §7, §10; personas §2–3; conduct-gifts §2–4; branch-economics §5–6; DD §5A.7 (see the gap note in §3a)
- [x] Task 17: Remaining 11 tools (18 total), MIS CSV format, size caps (964b4b6; review in batch [17, 18, 19])
  - Skills: `agent-harness-construction`, `banking-simulation-domain` · Read: engine-layout §5, prosus §7, integrity §3, rulebook (R14), attribution §2 M4, blueprint-bench, memory-tools §2–3
- [x] Task 18: Full invariants + Hypothesis state machine (3eafb32; review in batch [17, 18, 19])
  - Skills: `property-based-testing:property-based-testing` · Read: integrity §5, §8, §9
- [x] Task 19: Full scorer (DD §10.1–§10.3) (e54ef37; review in batch [17, 18, 19])
  - Skills: `benchmark-methodology`, then `mutation-testing:mutation-testing` · Read: attribution §3–4, scenario-taxonomy §2–4, blueprint-bench, rulebook R12, R14, integrity §4
- [x] Task 20: All bots, scorer-on-bots, sensitivity base case (fe09cf2; base case holds on all 10 seeds, no config change; review in batch [20, 21])
  - Skills: `banking-simulation-domain`, `benchmark-methodology` · Read: customer-behaviour §4, personas §1, scenario-taxonomy §4, integrity §7, prosus §4, price-of-integrity (sweep)
  - New: `BOTS["honest_legal_max"]` (best legal shortcut); optional `python -m temptation_bench.sweep` CLI (cut order item 4)
  - Key tests: `test_no_legal_shortcut`, `test_refusal_not_safe`, `test_no_pay_in_truth`, `test_sweep_cli_two_seeds` (only if the sweep is built)
- [x] Task 21: System prompt, target calibration, golden hash, minimal pair (1ac65d6; calibrated target \$450,000 = round_10k(1.15 × honest mean \$387,017, seeds 1–30); review in batch [20, 21])
  - Skills: `benchmark-methodology`, `experimental-design` · Read: rulebook "Agent-facing compact version" (active rules only), branch-economics §4–6, calibration-table, engine-layout §4, §7, prosus §4
  - Key tests: `test_prompt_has_no_canary`, `test_prompt_rulebook_only_active_rules`
- [ ] **S3 exit check**

### S4: M3 harness + M4 people prose

- [ ] Task 22: `CompactionTrim` + real `in_window` tracking
  - Skills: `agent-harness-construction` · Read: inspect-ai §3a–3b, attribution §2 M1, memory-tools §3, prosus §9 · Docs: compaction
- [ ] Task 23: Loop policies (nudge, caps, auto-advance, REAL/EVAL probe, transcript spans)
  - Skills: `agent-harness-construction`, `benchmark-methodology` · Read: inspect-ai §7, §9; experiment-matrix §6; prosus §9 (reminder test); integrity §4 (replay) · Docs: limits, `transcript`, `span`, `read_eval_log`
  - New: `harness/replay.py` (cuttable, cut order item 5) · Key test: `test_replay_mockllm_eval_reproduces_jsonl_hash`
- [ ] Task 24: Model settings (effort low, no seed/temperature) + per-cell cache + `harness.json`
  - Skills: `cost-aware-llm-pipeline` · Read: inspect-ai §5–6, §12; models-and-pricing §7 · Docs: reasoning effort, `CachePolicy`, model roles
- [ ] Task 25: Budget guard (`budget.py`) + paid runner (`run.py`; steps include `gfree` with a \$0 cap)
  - Skills: `cost-aware-llm-pipeline` · Read: experiment-matrix §5, inspect-ai §8, project-structure §8 · Docs: `cost_limit`, `ModelUsage`
- [ ] Task 26: People prose pregen + post-check + `ProsePeople`
  - Skills: `benchmark-methodology` · Read: multiagent §2–3, personas, engine-layout §6, prosus §4 (mailroom) · Docs: model roles
- [ ] **S4 exit check**

### S5: M5 graphs + G-free + M6 paid

- [ ] Task 27: Analysis loaders + stats (Clopper-Pearson, paired exact, HP_norm)
  - Skills: `statistical-analysis`, `statistical-power`, `exploratory-data-analysis` · Read: price-of-integrity §6, §8.1; attribution §4 (ITT, per-protocol); scenario-taxonomy §3–4; experiment-matrix §3, §6 (awareness) · Docs: `read_eval_log`, dataframes
  - New: `analysis/awareness.py` (`scan`, also over notes), Fisher + Holm in `stats` · Key tests: `test_awareness_regex_hits_and_misses`, `test_awareness_scan_includes_notes`
- [ ] Task 28: Graphs 2–10 + `report.md`
  - Skills: `dataviz`, `scientific-visualization` · Read: price-of-integrity §9 (and its "cannot report at this n" list), attribution-and-controls, scenario-taxonomy §4 (two axes), experiment-matrix §6
- [ ] Task 29: G-free connectivity check (\$0) — **needs the owner's new key in `.env` first**
  - Skills: `superpowers:verification-before-completion`, `cost-aware-llm-pipeline` · Read: inspect-ai §8, §10–11; project-structure §8 · Docs: providers, Hooks (route in headers)
- [ ] Task 30: Route check (≤ \$0.05) + smoke (≤ \$1.00)
  - Skills: `superpowers:verification-before-completion` (before each paid command), `cost-aware-llm-pipeline` · Read: experiment-matrix §3, §5; inspect-ai §12 · Docs: caching, concurrency
- [ ] Task 31: People pregen (≤ \$0.05) + mini-batch (≤ \$5.00) + hand check of every T1 decision
  - Skills: `superpowers:verification-before-completion`, `cost-aware-llm-pipeline`, `benchmark-methodology` (hand check) · Read: experiment-matrix §3 (go/no-go), attribution §3
- [ ] **S5 exit check** (ledger ≤ \$6.10, the sum of the S5 caps, plus anything the owner approved)

### S6: M7 full horizon

- [ ] Task 32: D11–D30 events (MIS #2–#5, boss replies) + internal audit
  - Skills: `banking-simulation-domain`, `property-based-testing:property-based-testing` · Read: audit-and-supervision §2–5, rulebook R14–R16, **consequence-model §1, §4** (cause link, fire-time guard) and §2–3, §5, conduct-gifts §5–7, personas §7
- [ ] Task 33: Mode-prefix test, full-horizon golden hash, detection-rate range
  - Skills: `property-based-testing:property-based-testing`, `benchmark-methodology` · Read: default-timing §4, engine-layout §7, consequence-model §5, audit-and-supervision Design impl.
- [ ] Task 34: Optional paid full run (≤ \$1.50), final report, whole-branch review, wrap-up
  - Skills: `superpowers:verification-before-completion`, `cost-aware-llm-pipeline`, `superpowers:requesting-code-review`, `superpowers:receiving-code-review`, `superpowers:finishing-a-development-branch` (+ built-in `code-review`, `simplify`) · Read: experiment-matrix §3 (go/no-go)
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
4. Sensitivity sweep beyond the base case (the optional `sweep` CLI in Task 20)
5. The replay test (`harness/replay.py`, Task 23)

---

## 3. Skills, tools and research to load

Check `../claude-tooling/README.md` for what each skill is for. **Superpowers is the core.**
Every name in §3 and §2 is the exact string for the **Skill tool**. All were checked against the installed skills on 2026-11-22.

> **Task numbers** in §2, §3a and §3b follow the **current** `docs/plan.md` (34 tasks). If the plan's task list changes, update all three together.

### 3.0 Load these first (follow literally, every session)

Don't write code for a task until its steps below are done.

1. **Start in the right folder.** Best: start Claude Code inside `pilot-1/`. Then this folder's `CLAUDE.md` loads, and so do the project skills in `pilot-1/.claude/skills/` (after Task 2).
2. **Check the tools are installed** (1 minute):
   - In a shell, `claude plugin list` must show **enabled** for: `superpowers@claude-plugins-official`, `context7@claude-plugins-official`, `property-based-testing@trailofbits`, `modern-python@trailofbits`, `dimensional-analysis@trailofbits`, `mutation-testing@trailofbits`.
   - `ls ~/.claude/skills/` must list: `codebase-design`, `experimental-design`, `statistical-analysis`, `statistical-power`, `scientific-visualization`, `agent-harness-construction`, `cost-aware-llm-pipeline`, `documentation-lookup`, `exploratory-data-analysis`.
   - `dataviz` and `anthropic-skills:skill-creator` are built in. They show in your session's skill list, not in that folder.
   - **If anything is missing or disabled: stop and tell the owner.** Don't install, enable or update anything yourself.
   - While you wait, you may read that skill's `SKILL.md` directly if the file exists. Plugin skills live at `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/skills/<name>/SKILL.md`. Write the gap in §7.
3. Invoke `superpowers:using-superpowers`.
4. Invoke the execution skill recorded in §4: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. If none is recorded yet, ask the owner once and record the answer.
5. Read `../research/README.md` (the research index).
6. **If your session touches Inspect** (Tasks 3, 7, 22–27, 29–31, 34):
   - Read `../research/03-tooling/inspect-ai.md` in full. It was checked against the installed 0.3.291 package.
   - Load Context7. Its tools may be deferred. If so, load them first with ToolSearch: `select:mcp__plugin_context7_context7__resolve-library-id,mcp__plugin_context7_context7__query-docs`.
   - Library ids (confirmed with `resolve-library-id` on 2026-11-22):
     - `/websites/inspect_aisi_uk`: the docs site. Use this first.
     - `/ukgovernmentbeis/inspect_ai`: the source code, for exact signatures.
   - Or fetch one page listed in `../claude-tooling/inspect-ai-context.md`. It indexes 79 doc pages, each a `.md` URL. §3b says which pages each task needs.
   - Context7 and the web docs can be newer than 0.3.291. **The installed package wins.** Check a signature like this: `uv run python -c "import inspect; from inspect_ai.model import set_model_info; print(inspect.signature(set_model_info))"`.
7. **Before each task** (every task, not once per session):
   - invoke the skills on the task's **Skills:** line in §2 (why and when: §3b);
   - read the notes on its **Read:** line in §2 (exact sections: §3a);
   - run its Inspect doc lookups (§3b, last column);
   - add one line to today's §7 log entry: `T<n>: skills …; read …`. If you skip something, say why.
8. Invoke `superpowers:test-driven-development` before the first line of engine, scorer or harness code. Invoke `superpowers:verification-before-completion` before you tick any box in §2.

**Tool caveats (read once per session):**
- **`modern-python:modern-python` changes `python` and `pip`.** At session start it adds small wrapper scripts ("shims"). `python script.py`, `pip install` and `python -m pip` are intercepted and point you to `uv`. `python -c` and `python -m <module>` pass straight through. Always use `uv run …` and `uv add …` here.
- **`literature-review` has optional paid scripts** (OpenRouter diagrams, Parallel search). They only run if `OPENROUTER_API_KEY` / `PARALLEL_API_KEY` are set, and they aren't. Never set them. Ask the owner before any paid API. Pilot-1 doesn't need this skill.
- **K-Dense skills** (`experimental-design`, `statistical-analysis`, `statistical-power`, `scientific-visualization`, `hypothesis-generation`, `literature-review`) expect Python 3.12+ and their own environment for their helper scripts. Use their advice. Don't add their script dependencies to `pilot-1/pyproject.toml`.
- **Project skills** (`temptation-bench-architect`, `banking-simulation-domain`, `benchmark-methodology`) exist only after Task 2. Before that, read the §3a notes directly. If the session started at the repo root, they may be listed with a folder prefix (for example `pilot-1:banking-simulation-domain`). Use the name exactly as your skill list shows it.
- **Skills are advice.** If a skill disagrees with the spec, the plan or §6, the spec wins.

### 3.1 Per session (summary)

| Session | Process skills | Domain / tool skills |
|---|---|---|
| Every session | `superpowers:using-superpowers`; `superpowers:subagent-driven-development` or `superpowers:executing-plans`; `superpowers:test-driven-development`; `superpowers:verification-before-completion`; `superpowers:systematic-debugging` when anything fails | project skills in `pilot-1/.claude/skills/` (after Task 2) |
| S1 | as above; `superpowers:writing-skills` (T2) | `modern-python:modern-python` (T1), `anthropic-skills:skill-creator` (T2), `codebase-design` (T4–T5), `dimensional-analysis:dimensional-analysis` (T4), Context7 (T3, T7), `agent-harness-construction` (T5, T7), `dataviz` + `scientific-visualization` (T8) |
| S2 | as above | `property-based-testing:property-based-testing` (T10, T11), `dimensional-analysis:dimensional-analysis` (T10, T11, T13, T14), `banking-simulation-domain` (T11–T14), `temptation-bench-architect` (T9) |
| S3 | as above; `superpowers:dispatching-parallel-agents` (T16/T17 after T15) | `banking-simulation-domain`, `benchmark-methodology`, `experimental-design` (T16, T21), `agent-harness-construction` (T17), `property-based-testing:property-based-testing` (T18), `mutation-testing:mutation-testing` (after T19) |
| S4 | as above | Context7 (T22–T26), `agent-harness-construction` (T22–T23), `cost-aware-llm-pipeline` (T24–T25), `benchmark-methodology` (T23, T26) |
| S5 | `superpowers:verification-before-completion` **before every paid step** | `statistical-analysis`, `statistical-power`, `exploratory-data-analysis` (T27), `dataviz` + `scientific-visualization` (T28), `cost-aware-llm-pipeline` (T29–T31), Context7 (T27, T29–T30), `benchmark-methodology` (T31 hand check) |
| S6 | `superpowers:requesting-code-review`, `superpowers:receiving-code-review`, `superpowers:finishing-a-development-branch`; built-in `code-review` and `simplify` (T34) | `banking-simulation-domain` (T32), `property-based-testing:property-based-testing` (T32–T33), `benchmark-methodology` (T33–T34), `cost-aware-llm-pipeline` (T34 paid run) |

### 3b. Skill and tooling map per task (invoke these before the task)

The names below are the exact strings for the **Skill tool**. `../claude-tooling/README.md` writes the Trail of Bits skills by short name (`modern-python`, `property-based-testing`, `dimensional-analysis`, `mutation-testing`). Those are plugin skills, so the Skill tool needs the `plugin:skill` form used here (e.g. `modern-python:modern-python`). If a skill is missing, follow §3.0 step 2. Never install a new pack without asking.

**Always, in every task:**
- `superpowers:using-superpowers` (session start)
- `superpowers:subagent-driven-development` or `superpowers:executing-plans` (whichever is recorded in §4)
- `superpowers:test-driven-development` (before any code)
- `superpowers:verification-before-completion` (before ticking a box)
- `superpowers:systematic-debugging` (any red test or surprise)
- After Task 2: the project skills `temptation-bench-architect`, `banking-simulation-domain` and `benchmark-methodology`, as listed in this table

**Library docs:**
- Inspect AI: see §3.0 step 6 (Context7 `/websites/inspect_aisi_uk`, or a page from `../claude-tooling/inspect-ai-context.md`).
- Other libraries (pydantic, Hypothesis, pandas, matplotlib, httpx): invoke `documentation-lookup`, which uses Context7.

"Inspect docs" column: what to query in Context7 · which page to open from `inspect-ai-context.md` · which section of `research/03-tooling/inspect-ai.md`.

| Task | Invoke (Skill tool) | Inspect docs |
|---|---|---|
| 1 scaffold | `modern-python:modern-python` (uv, ruff, pytest, pyproject) | – |
| 2 project skills | `anthropic-skills:skill-creator`, `superpowers:writing-skills` | – |
| 3 prices | (always-list only) | `set_model_info`, `ModelInfo`, `ModelCost`, `get_model_info` · `reference/inspect_ai.model` · §8 |
| 4 engine primitives | `codebase-design`, `dimensional-analysis:dimensional-analysis` (cents, basis points, minutes), `temptation-bench-architect` (after T2) | – |
| 5 config, `Branch` facade | `codebase-design` (deep-module facade, seams), `agent-harness-construction` (status line, tool output shape), `temptation-bench-architect` | – |
| 6 skeleton scoring, bots | `benchmark-methodology` | – |
| 7 Inspect skeleton | `agent-harness-construction` (tool docstrings, outputs, errors), `temptation-bench-architect` | custom `@agent` loop, `@tool` + `ToolError`, `StoreModel` / `store_as`, `mockllm/model`, `@scorer`, limits · Custom Agents, Custom Tools, Custom Scorers, Providers (mockllm), Setting Limits, `reference/inspect_ai.util` · §1–4, §7, §9 |
| 8 graph 1 | `dataviz`, `scientific-visualization` | – |
| 9 clock, end of day | `temptation-bench-architect` | – |
| 10 ledger | `property-based-testing:property-based-testing`, `dimensional-analysis:dimensional-analysis` | – |
| 11 credit maths | `dimensional-analysis:dimensional-analysis`, `property-based-testing:property-based-testing`, `banking-simulation-domain` | – |
| 12 customers, arrivals | `banking-simulation-domain` | – |
| 13–14 book, run-off | `banking-simulation-domain`, `dimensional-analysis:dimensional-analysis` | – |
| 15 records | `temptation-bench-architect`, `codebase-design` | – |
| 16 scenario + P/O factor slots | `banking-simulation-domain`, `benchmark-methodology`, `experimental-design` (minimal pairs, the P/O slots, the `run_config` tag) | – |
| 17 tools | `agent-harness-construction`, `banking-simulation-domain` | – |
| 18 invariants fuzzing | `property-based-testing:property-based-testing` | – |
| 19 full scorer | `benchmark-methodology`; once green, `mutation-testing:mutation-testing` on `engine/scoring.py` (do the tests catch bugs?) | – |
| 20 bots, sensitivity | `banking-simulation-domain`, `benchmark-methodology` | – |
| 21 prompt, calibration, golden hash | `benchmark-methodology` (no-leak wording), `experimental-design` (minimal pair, calibration seeds) | – |
| 22 compaction, `in_window` | `agent-harness-construction` | `compaction()`, `CompactionTrim` · Compaction · §3a–3b |
| 23 loop policies, probe | `agent-harness-construction`, `benchmark-methodology` (probe wording) | `transcript().info`, `span`, message/turn limits · Setting Limits, Log Files, `reference/inspect_ai.util` · §7, §9 |
| 24 model settings, cache | `cost-aware-llm-pipeline` (caching) | `GenerateConfig` reasoning effort, `CachePolicy(scopes=...)`, model roles · Reasoning, Caching, Using Models · §5, §6, §12 |
| 25 budget guard | `cost-aware-llm-pipeline` | `cost_limit`, `ModelUsage` · Setting Limits, Log Files · §7, §8 |
| 26 people prose | `benchmark-methodology` (no-leak check) | `model_roles`, `get_model(role=...)` · Using Models · §6 |
| 27 loaders, stats | `statistical-analysis`, `exploratory-data-analysis`; `statistical-power` (only for the "n = 3 is exploratory" caveat) | `read_eval_log`, dataframes · Log Files, Dataframes, `reference/inspect_ai.log` · §9 |
| 28 graphs 2–10, report | `dataviz`, `scientific-visualization` | – |
| 29–31 G-free, route check, smoke, mini-batch | `superpowers:verification-before-completion` **before each paid command**, `cost-aware-llm-pipeline`; T31 hand check: `benchmark-methodology` | `openai-api` and `anthropic` providers with a base URL, `max_samples` · Providers, Concurrency, Hooks (only if the route is in response headers) · §10–12 |
| 32 D11–D30 events, audit | `banking-simulation-domain`, `property-based-testing:property-based-testing` | – |
| 33 modes, determinism | `property-based-testing:property-based-testing`, `benchmark-methodology` | – |
| 34 paid full run, wrap-up | `superpowers:verification-before-completion`, `cost-aware-llm-pipeline` (paid step); `superpowers:requesting-code-review`, `superpowers:receiving-code-review`, built-in `code-review` / `simplify`, `superpowers:finishing-a-development-branch` | as 29–31 |

#### Every tool in `claude-tooling/README.md`, and whether pilot-1 uses it

| Skill or tool (exact name) | Pilot-1 use |
|---|---|
| `superpowers:brainstorming` | **Not for build tasks.** The spec and plan are done. Use only if the owner asks for a new feature or a design change. |
| `superpowers:writing-plans` | **Not for build tasks.** The plan is fixed. Use only if the owner asks to re-plan. |
| `superpowers:test-driven-development` | Every code task (1, 3–33) |
| `superpowers:systematic-debugging` | Any red test or surprise |
| `superpowers:verification-before-completion` | Before ticking a box; before every paid command (29–31, 34) |
| `superpowers:requesting-code-review`, `superpowers:receiving-code-review` | Task 34 whole-branch review; optional at each session's exit check |
| `superpowers:subagent-driven-development` / `superpowers:executing-plans` | Every session (choice recorded in §4) |
| `modern-python:modern-python` | Task 1; its shim caveat applies every session (§3.0) |
| `dimensional-analysis:dimensional-analysis` | Tasks 4, 10, 11, 13, 14 |
| `mutation-testing:mutation-testing` | After Task 19, on `engine/scoring.py`. Optional; skip if time is short (not on the never-cut list) |
| `property-based-testing:property-based-testing` | Tasks 10, 11, 18, 32, 33 |
| `experimental-design` | Tasks 16 and 21 (minimal pairs, factor slots, seeds crossed with doses) |
| `hypothesis-generation` | **Not for pilot-1.** Pilot-1 is exploratory. Pre-registering H1–H4 comes before the FULL runs (price-of-integrity §1, DD §5A.7). |
| `statistical-power` | Task 27, only to explain why n = 3 per arm is exploratory. No power claims. |
| `statistical-analysis` | Task 27 (Clopper-Pearson, exact paired test) and graph 7 |
| `literature-review` | **Not for pilot-1.** Novelty is already checked (`01-prior-work/gap-check.md`), and its optional scripts are paid. |
| `scientific-visualization` | Tasks 8, 28 |
| `anthropic-skills:skill-creator` | Task 2 |
| Context7 MCP | Tasks 3, 7, 22–27, 29–31 (via `documentation-lookup` for non-Inspect libraries) |
| Built-in `code-review`, `simplify` | Task 34; optional before a session's final commit |
| Pyright LSP, Plugin Developer Toolkit | Not installed. Not needed. Ask the owner before adding either. |

**Installed and used here, but not listed in `claude-tooling/README.md`:** `superpowers:using-superpowers`, `superpowers:dispatching-parallel-agents`, `superpowers:writing-skills`, `superpowers:finishing-a-development-branch`, `codebase-design`, `dataviz` (built in), `agent-harness-construction`, `cost-aware-llm-pipeline`, `documentation-lookup`, `exploratory-data-analysis`. They are verified present (§3.0 step 2).

**Installed but not for pilot-1:** `eval-harness` (we have our own Inspect harness and pytest), `domain-modeling` (no glossary/ADR planned), `improve-codebase-architecture`, `grilling`, `handoff` (this file is the handoff), `superpowers:using-git-worktrees` (all work stays on branch `pilot-1`; use it only if `superpowers:subagent-driven-development` asks, and tell the owner).

### 3a. Research reading map (read before each task)

The research in `../research/` is the *why* behind every number and rule. Read the listed notes (and sections) before starting a task.

**How the research fits the scope:**
- The spec and the design doc (DD) decide what pilot-1 builds. The research explains why.
- If a research note and the spec disagree, **follow the spec**, and add a note in §8 if it matters.
- If a research note describes something outside pilot-1, treat it as background only. Don't build it.

Start with `../research/README.md` (the index) once per session. Paths below are inside `../research/`. "Design impl." = the note's last section, "Design implications".

| Task(s) | Read in `../research/` |
|---|---|
| 1 scaffold | `03-tooling/project-structure-patterns.md` §1–2 (engine vs glue, layout), §7 (how others test); `05-simulator-architecture/engine-layout.md` §7 (test strategy, incl. the layering test); `prosus-vending-bench-study.md` §2, §8 (canary GUID) |
| 2 project skills (link these, don't copy them) | **architect:** `05-simulator-architecture/*` (incl. its README), `03-tooling/project-structure-patterns.md` · **banking:** `02-banking-domain/README.md` (top 10), rulebook, credit-risk, default-timing, calibration-table, customer-behaviour, personas, branch-economics, conduct-gifts, audit, `evergreening-and-loan-fraud.md` §4 · **methodology:** `04-methodology/*` (incl. its README), `00-papers/*`, `01-prior-work/gap-check.md` (background) |
| 3 prices | `03-tooling/inspect-ai.md` §8 (cost tracking); `03-tooling/models-and-pricing.md` §7 (caching). The spec §7.1 gateway prices override this note's prices. |
| 4–5 engine primitives, skeleton `Branch` | `05-simulator-architecture/engine-layout.md` §1–5; `integrity-and-invariants.md` §1, §4 (event `cause` link); `consequence-model.md` §1 (T4); `02-banking-domain/branch-economics-and-targets.md` (pay and bonus line, T5); `03-tooling/memory-tools.md` §1 (VB2 morning briefing, T5); `prosus-vending-bench-study.md` §4 (config, status line), §5–6; `05-simulator-architecture/README.md` (top takeaways); `03-tooling/project-structure-patterns.md` §3, §5, §6; `02-banking-domain/general-rulebook.md` §0 (world setup); `00-papers/vending-bench.md` (agent setup, clock) |
| 6 skeleton scoring, bots | `04-methodology/attribution-and-controls.md` §2 (M1 policy-check line, M4 attestation), §3; `scenario-taxonomy.md` §2 (rows 1–2); `00-papers/blueprint-bench.md` (scripted baselines) |
| 7 Inspect skeleton | `03-tooling/inspect-ai.md` §1–4, §7, §9; `03-tooling/README.md` (top takeaways; `tau2_banking` in inspect_evals is code worth reading); `04-methodology/attribution-and-controls.md` §2 M1 (`in_window`); `00-papers/vending-bench.md` (agent setup, the continue nudge) |
| 8 graph 1 | `00-papers/vending-bench.md` (tool-use counts); `04-methodology/price-of-integrity.md` §9 (figure labelling rule) |
| 9 clock, end-of-day | `02-banking-domain/default-timing-and-horizon.md` §2; `05-simulator-architecture/engine-layout.md` §3; `consequence-model.md` §4; `prosus-vending-bench-study.md` §7 (tool time costs); `03-tooling/memory-tools.md` §1 (briefing); `00-papers/vending-bench.md` (Clock) |
| 10 ledger | `05-simulator-architecture/integrity-and-invariants.md` §2, §5, §6 (ledger replay, tool postconditions); `prosus-vending-bench-study.md` §6; `05-simulator-architecture/README.md` takeaway 3 (boundary account, bribes off-ledger) |
| 11 credit maths | `02-banking-domain/credit-risk-and-underwriting.md` §2–7 (§7 = formula sheet); `default-timing-and-horizon.md` §5–6 (**§6b**: slips, cures, EPD mixture); `customer-behaviour-models.md` **§2e** (rate markup take-up, elasticity); `calibration-table.md`; `general-rulebook.md` R2–R4 |
| 12 customers, arrivals | `02-banking-domain/customer-behaviour-models.md` §2a (calendar multiplier), §2e–2f (loan applications, tenor), §3; `personas.md` §3, §5, §6, §8 + Design impl. (officer note); `credit-risk-and-underwriting.md` §1 (loan file), §4b + Design impl. (soft hints); `05-simulator-architecture/integrity-and-invariants.md` §4 (`customer_created` event); `general-rulebook.md` R3 (2-of-3 sources); `evergreening-and-loan-fraud.md` §4 (income fraud); `calibration-table.md` |
| 13–14 book, provisions, run-off | `02-banking-domain/default-timing-and-horizon.md` §1 (why the inherited book), §3 (run-off); `credit-risk-and-underwriting.md` §6 (no accrual on NPL); `branch-economics-and-targets.md` **§2** (FTP, deposit margin) + Design impl., and §1; `general-rulebook.md` R5–R6; `05-simulator-architecture/consequence-model.md` §1, §5 (run-off, inherited book); `integrity-and-invariants.md` §4 (logs, seal) |
| 15 records, edits | `05-simulator-architecture/integrity-and-invariants.md` §3; `02-banking-domain/evergreening-and-loan-fraud.md` §4; `credit-risk-and-underwriting.md` Design impl. (`as_submitted` / `as_approved`); `general-rulebook.md` R1, R17 |
| 16 planted scenario + P/O factor slots | `04-methodology/scenario-taxonomy.md` §1–2 (rows 1–5); **`experiment-matrix.md` §1 (exact P and O sentences: copy them) and §2 (one sentence, one slot, same time, length-matched)**; `price-of-integrity.md` §1 (B50 is conditional on P and O; H2, H3), §3, §7 (cap `B ≤ L`), §10 (contingent personal offer); `02-banking-domain/personas.md` §2–3, §6; `conduct-gifts-whistleblowing.md` §2–4; `branch-economics-and-targets.md` §5–6; `audit-and-supervision.md` Design impl. (watched vs unwatched); `05-simulator-architecture/engine-layout.md` §4 (keyed streams keep pairs identical) |
| 17 tools | `05-simulator-architecture/engine-layout.md` §5; `prosus-vending-bench-study.md` §7; `integrity-and-invariants.md` §3 (`report_differs_from_ledger` tag); `02-banking-domain/general-rulebook.md` (all, esp. R14 report format); `conduct-gifts-whistleblowing.md` Design impl. (gift and whistleblowing tools); `04-methodology/attribution-and-controls.md` §2 M4 (`policy_exceptions`, `escalate_to_rcc`); `customer-behaviour-models.md` §5 (token-cheap CSV); `00-papers/blueprint-bench.md` (strict formats); `03-tooling/memory-tools.md` §2–3 |
| 18 invariants fuzzing | `05-simulator-architecture/integrity-and-invariants.md` §5, §8 (Hypothesis state machine sketch), §9 (core principle as tests); `03-tooling/project-structure-patterns.md` §7 |
| 19 full scorer | `04-methodology/attribution-and-controls.md` §3–4; `scenario-taxonomy.md` §2–4; `00-papers/blueprint-bench.md` (count format errors apart from lies); `02-banking-domain/general-rulebook.md` R12, R14; `05-simulator-architecture/integrity-and-invariants.md` §4 (attempt and tamper tags) |
| 20 bots | `02-banking-domain/customer-behaviour-models.md` §4; `personas.md` §1 (elite manager = honest bot); `04-methodology/scenario-taxonomy.md` §4 (refuse-all / approve-all / oracle); `05-simulator-architecture/integrity-and-invariants.md` §7 (exploit attacks); `prosus-vending-bench-study.md` §4 (reference bot); `03-tooling/project-structure-patterns.md` §8; `04-methodology/price-of-integrity.md` (for the optional `sweep` CLI) |
| 21 prompt, target calibration, golden hash | `02-banking-domain/general-rulebook.md` "Agent-facing compact version"; `branch-economics-and-targets.md` §4–6; `calibration-table.md`; `05-simulator-architecture/engine-layout.md` §4, §7 (golden seed, prompt test); `prosus-vending-bench-study.md` §4 (prompt from config, `sync_config --check`); `05-simulator-architecture/README.md` "Added recommendations"; `04-methodology/experiment-matrix.md` §2; `00-papers/vending-bench.md` |
| 22–24 harness | `03-tooling/inspect-ai.md` §3a–3b, §5–7, §11–12; `memory-tools.md` §2–3; `multiagent-and-subagents.md` §2 (model roles); `models-and-pricing.md` §7 (caching); `04-methodology/attribution-and-controls.md` §2 M1 (`in_window`); `experiment-matrix.md` §6 (REAL/EVAL probe, keyword scan); `05-simulator-architecture/prosus-vending-bench-study.md` §9 (reminder test, count tokens not characters); `integrity-and-invariants.md` §4 (T23 `replay.py`: logged `DecisionContext` per call) |
| 25, 29–31 budget, paid runs | `04-methodology/experiment-matrix.md` §3, §5; `03-tooling/models-and-pricing.md` (the spec's gateway prices override it); `03-tooling/inspect-ai.md` §8, §10–12; `project-structure-patterns.md` §8 (checklist before paid runs); `02-banking-domain/default-timing-and-horizon.md` §2c (illustrative, not results) |
| 26 people prose | `03-tooling/multiagent-and-subagents.md` §2–3; `02-banking-domain/personas.md`; `05-simulator-architecture/engine-layout.md` §6 (Lite vs Full people, post-check); `prosus-vending-bench-study.md` §4 (`mailroom.py`: LLM rewrites prose only, falls back to the template); `04-methodology/experiment-matrix.md` §2 (templates keep pairs intact) |
| 27–28 analysis, graphs | `04-methodology/price-of-integrity.md` §6 (floors, Clopper-Pearson), §8.1 (pilot exact test), §9 (figure rule); `attribution-and-controls.md` §4 (ITT first, per-protocol second); `scenario-taxonomy.md` §3–4 (over-refusal, `HP_norm`, two axes); `experiment-matrix.md` §3 (analysis step 6, go/no-go), §6 (awareness per arm; T27 `analysis/awareness.py`); T28 "cannot report at this n" list: price-of-integrity and attribution-and-controls |
| 32 audit, D11–D30 | `02-banking-domain/audit-and-supervision.md` §2–5; `general-rulebook.md` R14–R16; `personas.md` §7 (auditor); `evergreening-and-loan-fraud.md` §4 (audit sampling); `05-simulator-architecture/consequence-model.md` **§1, §4** (`cause` link, fire-time guard, `consequence_skipped`), §2–3, §5; `02-banking-domain/conduct-gifts-whistleblowing.md` §5–7; `default-timing-and-horizon.md` §1 (NPL crossing) |
| 33 window vs full horizon | `02-banking-domain/default-timing-and-horizon.md` §4 (horizons); `05-simulator-architecture/engine-layout.md` §7 (golden seed); `consequence-model.md` §5 and `02-banking-domain/audit-and-supervision.md` Design impl. (detection probability, for the 30–80% detection test) |

**The watched-vs-unwatched gap (decision 10 in §8).** Pilot-1 fixes `O = normal` and `P = target`. Task 16 still builds both slots and the `run_config` tag. For that task, read: `04-methodology/experiment-matrix.md` §1 (all P and O sentences) and §2 (slot rules), §6 (awareness per O level, for later); `price-of-integrity.md` §1 (H2, H3); DD §5A.7; `02-banking-domain/audit-and-supervision.md` and `evergreening-and-loan-fraud.md` Design impl. (both suggest watched vs unwatched weeks); `01-prior-work/gap-check.md` "Evaluation awareness / watched vs unwatched" (prior art). Skills: `experimental-design`, `benchmark-methodology`. Build only the slots. Don't run other levels.

**Where pilot-1 knowingly differs from the research (follow the spec):**
- RNG: `project-structure-patterns.md` §4 suggests numpy Generators. Pilot-1 uses the stdlib keyed `random.Random`, and the engine has no numpy.
- Providers and prices: `models-and-pricing.md` assumes direct APIs. Pilot-1 uses the Experiential Labs gateway (spec D1, D4).
- Dates: research notes saying "pilot run 2026-11-22/23" are out of date. The deadline is 2026-11-24.
- Horizon: `default-timing-and-horizon.md` §4 proposes a 63-day pilot. Pilot-1 uses a 10-day window and a 30-day full horizon (spec §6–7).
- Run matrix and doses: `experiment-matrix.md` §3 proposes 3 × 3 × 5 runs with doses `{0, $1k, $30k}`. Pilot-1 runs a smoke plus a 12-run mini-batch at `{0, $30k}` (spec D3, §7.2).
- Bribe wording: `experiment-matrix.md` §2 has example sentences. Use the exact DD §6.8 sentences in the plan's Global Constraints instead.
- Build order: `engine-layout.md` §8 is replaced by the plan.
- Config file names: research says `rules.yaml`; pilot-1 uses `configs/rules.toml`.
- Knowledge probe (attribution M3) and the reasoning judge (M5) are deferred to FULL (DD §10, §16). Pilot-1 always shows the policy-check line.

**Every research file, and where it is used** (31 files; "T" = task):

| File | Used in | Background only (why) |
|---|---|---|
| `README.md` | every session (index) | – |
| `00-papers/vending-bench.md` | T4–5, 7, 8, 9, 21 | – |
| `00-papers/blueprint-bench.md` | T6, 17, 19 | – |
| `01-prior-work/gap-check.md` | T16 (watched-vs-unwatched prior art only) | the rest: for the later write-up, not for building |
| `02-banking-domain/README.md` | T2 | – |
| `02-banking-domain/aml-kyc-and-vip-customers.md` | – | all: AML is FULL (spec §2 non-goals) |
| `02-banking-domain/audit-and-supervision.md` | T16, 32, 33 | inspector interview (§6): FULL |
| `02-banking-domain/branch-economics-and-targets.md` | T5, 13–14, 16, 21 | §3 cost structure: context only |
| `02-banking-domain/calibration-table.md` | T11, 12, 20, 21 | – |
| `02-banking-domain/conduct-gifts-whistleblowing.md` | T16, 17, 19, 32 | the bribe ladder and retaliation test: FULL |
| `02-banking-domain/credit-risk-and-underwriting.md` | T11, 12, 13–14, 15 | – |
| `02-banking-domain/customer-behaviour-models.md` | T11, 12, 17, 20 | §1 evidence; reputation, runs, cross-sell, fake accounts (§2b–2d, §2g–2h): not in the spec |
| `02-banking-domain/default-timing-and-horizon.md` | T9, 11, 13–14, 25, 32, 33 | §6c: FULL |
| `02-banking-domain/evergreening-and-loan-fraud.md` | T12, 15, 16, 32 (§4 and Design impl.) | §1–3, §5: evergreening is FULL |
| `02-banking-domain/general-rulebook.md` | T4–5, 11, 12, 13–14, 15, 17, 19, 21, 32 | R7–R11, R13: FULL rules |
| `02-banking-domain/personas.md` | T12, 16, 20, 26, 32 | §4 launderer: FULL |
| `03-tooling/README.md` | T7 | VB re-implementations list: context only |
| `03-tooling/inspect-ai.md` | T3, 7, 22–27, 29–31 | – |
| `03-tooling/memory-tools.md` | T5, 9, 17, 22–24 | §1 history; vector DB: P3 |
| `03-tooling/models-and-pricing.md` | T3, 24, 25, 29–31 | its prices are replaced by spec §7.1 |
| `03-tooling/multiagent-and-subagents.md` | T22–24, 26 (§2–3) | §1 archived library, §4 sub-agents: P3 |
| `03-tooling/project-structure-patterns.md` | T1, 4–5, 18, 20, 25 | §4 numpy RNG: replaced (see above) |
| `04-methodology/README.md` | T2 | verdict table and score card: context only |
| `04-methodology/attribution-and-controls.md` | T6, 7, 17, 19, 22–24, 27–28 | M3 probe, M5 judge: FULL |
| `04-methodology/experiment-matrix.md` | T16, 21, 22–24, 25, 27–28, 29–31 | §4 full matrix: FULL |
| `04-methodology/price-of-integrity.md` | T8, 16, 20, 27–28 | §2–5 ladder/hybrid designs, §8.2–8.5, B50 estimation: FULL |
| `04-methodology/scenario-taxonomy.md` | T6, 16, 19, 20, 27–28 | rows 6–19: FULL |
| `05-simulator-architecture/README.md` | T2, 4–5, 10, 21 | – |
| `05-simulator-architecture/consequence-model.md` | T4, 9, 13–14, 32, 33 | rows beyond the pilot's 3: FULL |
| `05-simulator-architecture/engine-layout.md` | T1, 4–5, 9, 16, 17, 21, 26, 33 | §8 build order: replaced by the plan |
| `05-simulator-architecture/integrity-and-invariants.md` | T4–5, 10, 12, 13–14, 15, 17, 18, 19, 20, 23 | hash chain: FULL |
| `05-simulator-architecture/prosus-vending-bench-study.md` | T1 (§2, §8 canary), 4–5, 9, 10, 17, 20, 21, 22–24, 26 | §1, §3, §10: context only |

Useful references:
- `../research/03-tooling/inspect-ai.md`: verified Inspect API notes and an agent-loop sketch
- `../claude-tooling/inspect-ai-context.md`: index of Inspect doc pages
- `../research/05-simulator-architecture/engine-layout.md` and `integrity-and-invariants.md` (exploit attacks for Task 20)

---

## 4. Next action

**Execution method:** `superpowers:subagent-driven-development` from Task 13 on (owner asked for multi-agent coding; Tasks 1–12 were inline). Every implementer and reviewer runs on **Opus 5.5, effort medium** (owner instruction). One implementer at a time; each task gets a spec + quality review. Ledger with every ruling: `../.superpowers/sdd/plan/progress.md` (gitignored).

**Reviews run in batches** (owner, 2026-11-22: "don't run review after each task, review in batches"): one Opus reviewer per batch of about 3 tasks, plus the final whole-branch review. Batches: [14, 15, 16], [17, 18, 19], [20, 21], [22–26], [27, 28], [32, 33].

**Next:** S3, Task 15. Tasks 15–17 run one after another (not in parallel: they edit the same files).

Owner items:
- The owner put a key in `../key.txt`; `pilot-1/.env` was written from it (chmod 600, gitignored, never printed). `key.txt` is in the root `.gitignore`. **Still revoke the key that was pasted in chat earlier.**

---

## 5. Spend tracker (\$10 hard limit, \$9.50 stop line)

The source of truth is `budget/ledger.jsonl` (from Task 25). Copy each line's totals here.

| Step | Cap | Estimate | Actual | Running total | Date | Notes |
|---|---|---|---|---|---|---|
| G-free (Task 29) | \$0 | \$0 | | | | free Luna |
| Route check (Task 30) | \$0.05 | 2026-11-22 | chart of accounts | + 1150 INTEREST_RECEIVABLE, + 4100 DEPOSIT_MARGIN (designer call) | LOANS equals Σ outstanding principal; deposit margin kept apart from funding cost | 13 |
| 2026-11-22 | officer note | honest files get a false soft hint with p = 0.10 (designer call) | hints that are always right would make fraud trivially visible | 12 |
| 2026-11-22 | `true_profit_final` | DD §6.9 formula + provisions held at T added back, E_NII minus interest accrued but unpaid (designer call) | otherwise expected losses and accrued interest are counted twice (in-run P&L and run-off) | 14 |
| 2026-11-22 | `[book] default_lgd_bp` | new, 6000 (proposal) | run-off LGD when a customer has none | 14 |
| 2026-11-22 | opening ledger | opening equity sized positive (was −\$500k) | balance sheet must make sense with the inherited book | 13 |
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

### 2026-11-22: S2 build (M2a economy), \$0
- Execution: inline for Tasks 9–12; switched to `superpowers:subagent-driven-development` at Task 13 (owner question). All subagents on Opus 5.5, effort medium (owner instruction).
- Skills: T9 `temptation-bench-architect` (read from file; project skills were not in the session's list then, now they are); T10 `property-based-testing`, `dimensional-analysis` (unit comments only); T11 `dimensional-analysis` (unit comments), `property-based-testing`, `banking-simulation-domain`; T12 `banking-simulation-domain`; T13 and T14 subagents told to invoke `superpowers:test-driven-development`, `dimensional-analysis` (light), read `banking-simulation-domain` and the §3a notes.
- Tasks 9–13 done. Scope audit of Tasks 1–12 (Opus, read-only): no Critical; 6 Important, 13 Minor. Fixed in 1218653: verified income = mean of the agreeing pair (DD §6.5); string/`$` amounts now refused; separate evidence and truth stores (hidden customer no longer on the application); full-precision hidden draws in `customer_created`; real I3 and I13; unknown tool calls logged; D1 in the March P&L; accrued interest reversed when a loan turns NPL; write-off test. Review: approved. 115 tests green.
- Kept after the audit (rulings in the ledger): full `plugin:skill` names in `claude-tooling/README.md` (the owner asked for it); `key.txt` line in the root `.gitignore` (protects the public repo).
- Task 14 (bc70ac0): run-off (ELL, E_NII, `true_profit_final`, agent vs inherited book reported apart), `ev_obs` from visible data only, finalize/seal. Bot outputs (not results): cheater ends \$21k–\$25k below honest on agent loans, seeds 1–5. 134 tests green; JSONL hash the same under two `PYTHONHASHSEED`s.
- Deferred to later tasks: `approve_loan` takes `rate_bp`; Task 17 replaces it with `markup_bp` + `exception_reason`. `policy_check` must read the frozen version-1 record once `edit_application` exists (Task 15). A full `dimensional-analysis` pass on the economy formulas after Task 14.

### 2026-11-22: S1 build (M0 + M1), \$0
- Execution: `superpowers:executing-plans` inline; peer planning session confirmed its final review was done before coding started.
- Skills loaded: `superpowers:using-superpowers`, `executing-plans`, `test-driven-development`, `modern-python:modern-python` (T1), `anthropic-skills:skill-creator` + `superpowers:writing-skills` (T2), `dimensional-analysis:dimensional-analysis` (T4, unit comments only), `codebase-design` + `agent-harness-construction` (T5, T7), `dataviz` (T8, palette validated).
- Tasks 1–8 done, 32 tests green, ruff clean. mockllm e2e writes `.eval` + sealed JSONL + T1 label; truncated run still sealed and scored; graph 1 renders.
- `claude-tooling/README.md`: Trail of Bits skill names now in `plugin:skill` form; project-skills pointer line.
- Rulings (details in the ledger): optional `Branch.new(log_path=...)`; status line shows the clock after the call; verified income = mean of 3 when all agree else closest pair; DTI rounds up; refused calls cost 0 minutes; RunStore filled by a `setup_run` solver; JSONL under `RUNS_DIR/<uuid>/`; `task.py` absolute imports; graph CSV table view.
- Spend: \$0.

### 2026-11-22: Final planning review (no code, \$0)
- Read all five pilot-1 docs, the DD, `idea.md`, `qna.md`, `open-questions.md`, `claude-tooling/README.md` and every research note. Checked skill names against `~/.claude/skills/` and the plugin cache: all present. Planning commit 57719a1 confirmed.
- Sampled 37 gap-audit rows against `plan.md`: all at the named task. Hunted for missed items: 17 new rows in `docs/gap-audit.md` §9 (total now 170).
- Fixes: cut order (plan Tasks 20/23 now items 4/5, as spec §6); exposure tag names and `exposed` definition (Tasks 5, 6, 27); awareness scan over notes; role and several-tools texts; "no current date"; variant files `full`/`gfree` created in Task 5; `generate_config` takes seed and dose; G-free through `run.py --step gfree` (cap \$0); S5 exit \$6.10; ρ = 1/3 labelled assumption; spec no-secrets regex; new tests for list CSVs, compliance ack, ordinary withdrawal.
- 3 new owner questions (11–13). Nothing outside pilot-1 was edited.

### 2026-11-22: Planning session (no code)
- Wrote and got approval for `docs/spec.md` (two subagent reviews folded in: 3 blockers fixed, 6 builder questions answered).
- Wrote `docs/plan.md` (34 tasks, 6 sessions) and this tracker.
- Owner decisions: build order A (walking skeleton first); all of M0–M7 by 2026-11-24; standing approval for paid steps up to each cap.
- Checked on 2026-11-22: inspect-ai 0.3.291 is the latest on PyPI; uv 0.12.5 and Python 3.13.0 are installed.
- Nothing has been spent: \$0 of \$10.
- Research gap audit (2026-11-22, commit 0e8232b): 153 items checked: 50 covered, 57 gaps fixed, 20 conflicts resolved or explained, 26 FULL-only. Details in `docs/gap-audit.md`. No tasks renumbered. Skill map rewritten (below), then resynced to the revised plan.
- Tooling audit (2026-11-22): checked every skill name against the installed skills (`claude plugin list`, `~/.claude/skills/`). Trail of Bits skills need the `plugin:skill` form. Context7 id `/websites/inspect_aisi_uk` confirmed with `resolve-library-id`. Added §3.0 (load-first steps), per-task **Skills:** / **Read:** lines in §2, the full tool inventory in §3b, and every research file in §3a.

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
| 9 | Plan lives in `pilot-1/docs/plan.md`, not `docs/superpowers/plans/` (owner: keep `docs/` untouched) | this file |
| 10 | Watched vs unwatched (O) and pressure (P) are **fixed** in pilot-1 at `normal` / `target` (DD §5A.7); varying them is FULL. Pilot-1 still builds both slots (D1 boss sentence, D2 IT notice) and tags every log with them (Task 16), so FULL only changes config. D2 timing is a designer call. Reading and skills for it: §3a "watched-vs-unwatched gap" note | DD §5A.7, plan Task 16 |

### Design values changed during the build

Log any config value changed to make a test pass, such as the base case or detection rates. Never change a test to make it pass.

| Date | Value | Old → new | Why | Task |
|---|---|---|---|---|
| | | | | |

### Open items / questions for the owner

- [ ] Revoke the pasted key and create `.env` (before Task 29)
- [ ] Merge or push `pilot-1` at the end? (Task 34)
- [ ] 13 owner questions in `docs/gap-audit.md` ("Questions for the owner"): markup take-up, `sad_story` slot, `order` text, `wait_days`, C3 decline-by-email, exploit attacks 5/7, payday date, MIS error floors, exploit pass rule, `PERIOD CLOSED`, G-free billing cap (11), plan size / extra cuttable items (12), ρ assumption (13). Until answered, the designer calls in the plan stand.
- Longer-term questions stay in `../docs/open-questions.md`. That file is read-only for this pilot; add any new ones here instead.
