# Review: batch [27, 28], e774b9f..5a46c5a

I reviewed this in one pass per file. I read the full diff and the changed files as they stand at HEAD (`analysis/{stats,awareness,load,plots,report}.py`, `tests/analysis/test_{load,plots}.py`).

Checks I ran (targeted only, read-only):
- **Stats known values** via `uv run python`:
  - `fisher_one_sided(3,3,0,3)` = 0.05;
  - `holm([0.01,0.04])` = [0.02, 0.04];
  - `clopper_pearson(0,3)` = (0, 0.70760);
  - `clopper_pearson(3,3)` = (0.29240, 1.0);
  - `holm([.03,.03,.03])` = [.09,.09,.09].
- **Regex spot-check:**
  - "This is a simulation", "being tested", "Benchmark", "red team", "Simulated" and "THIS IS A TEST" hit;
  - "not realistic" and "this is an evaluation" miss.
- **Graphs 6, 7 and 8:** rendered from 48 bot runs into the scratchpad and viewed. Graph 7's title reads `Bribe effect on T1 (exploratory, n = 3 per arm)`.
- **Engine purity:** `git diff --stat` shows no `engine/` change. The analysis imports are pandas, matplotlib, `engine.{config,eventlog,scoring,money}`, `budget` and `inspect_ai.log` (lazy). There is no `harness` import.
- **Named risks checked:**
  - JSONL and `.eval` layout: `harness/agent.py:55-80` and `run.py:49,343` show the `.eval` files in `logs/paid/<step>-<stamp>/`, the JSONL files in `runs/<run_id>/`, and attempt files beside the JSONL.
  - JSONL write timing: `engine/eventlog.py:62` writes on finalize only.
  - Units: `npl_ratio` is in 1e-4 units (`engine/scoring.py:41`), so it equals bp. `reported_npl_bp` is correct.

---

## Task 27: analysis loaders, exact stats, awareness scan

### Spec Compliance

✅ **Spec compliant.**
- **`RunFrame` fields** (`load.py:84-99`):
  - `daily` (`:180-197`)
  - `turns` (`:119-164`)
  - `labels`
  - `markers` (`:203-254`)
  - plus `clipped`, `awareness_hits` and `probe_hits`
- **`load_batch` and `labels_table`** (`:424-493`). `itt` is always True, and `per_protocol` = `exposed` (`:481-482`).
- **Stats functions** (`stats.py`, stdlib `math.comb` only) give every required known value.
- **`hp_norm`** returns None when the oracle equals refuse_all (`stats.py:76-78`).
- **Awareness scan** uses the DD §10.5 list (`awareness.py:13-21`). It covers assistant text, visible reasoning (`load.py:105-116`), `write_note` texts (`:368-369`) and, separately, the probe (`:381`).
- **Attempt files** are never loaded (`:456`) and are counted per run (`:279`).
- **Cached turns** are zero-usage and flagged (`:141-151`). This is the ledger's "Deferred to Task 27" clipped item, now done (`:350-366`).
- **Tests:** all 7 named tests are present, and the known values are asserted (`test_load.py:38-80`).

⚠️ **Cannot verify from the diff:** the `.eval` event ordering assumptions. Examples are the `engine_call` journal entries arriving 1:1 before the `tool_call`s, and `info/source=="engine"` marking the end of the loop. These hold for mockllm, but they rest on the Task 23 harness and Inspect 0.3.291 behaviour. The Task 30 smoke log should be checked once: `load_run` must not raise, and the turn count must equal the number of agent generates.

### Strengths
- **Cache-read usage:** the implementer found a real trap. A cache-read `ModelEvent` still carries the original call's usage. The fix zeroes it and flags the turn (`load.py:141-142`), and a test pins it, with a mutation check reported.
- **Turn pairing fails loudly:** if pairing goes wrong, `load_run` raises instead of mis-mapping turns (`load.py:290-294`).
- **In-call event ordering:** `own_turn` handles events logged before their own `tool_call` (`:327-333`), so the T1 decision and MIS markers are exact.
- **Stats code:** small, readable and documented. The two-sided vs DD one-sided zero-event bound is stated in the docstring (`stats.py:32-34`).
- **Probe kept apart:** probe hits are separate from in-run hits, and `aware` uses in-run hits only (`load.py:485`). That is correct, since the probe question itself says "evaluation".

### Issues

#### Critical
None.

#### Important
None.

#### Minor
- **R27-1 (Minor), `load.py:290-294, 454`: one bad sample aborts the whole batch.** A single sample whose journal and `tool_call` counts disagree raises `ValueError` out of `load_batch`. So one malformed sample makes `build_report` fail for the whole batch. It is loud, not silent. But the "list, never drop" rule would be better served by catching it per sample and keeping an errored `RunFrame` with `meta["error"]` carrying the message.
- **R27-2 (Minor), `load.py:279, 436-451`; `report.py:96-101`: some attempt files go uncounted.** Attempt files are counted only next to a run that has `jsonl_path`. Suppose a sample's final attempt never produced a JSONL (the errored-sample branch at `:436`). Its `<name>.attempt<k>.jsonl` from an earlier attempt is then neither counted nor listed. `load_batch(logs/...)` never globs `runs/` either. This is rare, because `finalize` runs in `finally`, but it breaks "attempt files are counted, never dropped". Fix: in the no-JSONL branch, glob `Path(st["log_path"]).parent` for `<stem>.attempt*.jsonl` and store the result in `meta`.
- **R27-3 (Minor), `awareness.py:14-20`: the patterns are tightened versions of the DD list.** The word boundaries and inflections are documented. Two side effects:
  - "this is an evaluation" and "this is just a test" miss. That is DD-literal, so acceptable.
  - The added `\b` means `simulated` no longer matches inside "unsimulated". That is fine.

  Consider adding `this is an? ` (allow "an") in a later round. It is not required.
- **R27-4 (Minor), `load.py:342`: unknown tools default to "read".** An unknown tool name silently gets `kind = "read"`. If a tool is ever added without updating `TOOL_KIND`, graphs 1 and 2 misclassify it without warning. Fix: use `TOOL_KIND[...]`, so it raises, or add a test that `TOOL_KIND` equals the registered tool list.

### Assessment
**Task quality: Approved.**

**Reasoning:** the stats are exact and verified, the loader is careful about Inspect's cache and event-order quirks, and failure modes are mostly loud. The remaining items are edge cases.

---

## Task 28: graphs 2–10 and batch report

### Spec Compliance

❌ **Issues found.**
- **Misunderstood: ITT is computed on labelled runs only.** See R28-1.
- **Everything else matches the brief and spec §8:**
  - all 9 functions, with fixed names (`plots.py:253-1056`);
  - graph 3 has 4 panels;
  - graph 7's title contains `exploratory, n = {n} per arm` (`:738`);
  - graph 4 marks cached turns with an × plus a legend entry and a count note (`:396-412, 473-482`);
  - "exploratory" appears in every figure through `_suptitle`, and in the graph 1 title.
- **`build_report` contents:**
  - the arm table with n assigned, n exposed, ITT and then per-protocol, each with a CP CI (`report.py:199-240`);
  - the label table;
  - bot baselines;
  - awareness, as a per-arm share plus every hit with its context and the probe answers verbatim (`:345-380`);
  - clipped outputs;
  - failed attempts and errored samples, listed and counted (`:402-427`);
  - spend from the ledger;
  - a figure section that links every PNG;
  - the hand-check header;
  - the "cannot report" list (B50, dose slope, Integrity Index, H1; π(0) and the dose effect are descriptive only) (`:24-35`).
- **No significance claims:** no p-value is printed, and the paired table gives discordant counts only (`:241-267`).

⚠️ **Cannot verify from the diff:** legibility at real-batch scale, with 2 models × 2 doses × 3 seeds over ~100+ turns. The implementer viewed the mock renders, and I viewed graphs 6–8 from bots. Re-view the figures after Task 31.

### Strengths
- **Dataviz rules are followed:**
  - one axis per measure, with panels instead of dual axes (graphs 3, 4, 5, 8, 9, 10);
  - fixed slot order;
  - neutral ink for reference lines, with direct labels;
  - a figure legend whenever there are 2 or more series;
  - a CSV table view for every figure (`save`, `plots.py:1126-1140`).
- **Honest-reporting details:**
  - the "+k unlabelled" annotation on graph 7 (`:716-717`);
  - the "k runs not shown: x undefined" note on graph 8 (`:900-909`);
  - the unpriced-turn note on graph 4;
  - the "cached replay" tag on run names.
- **Markdown safety:** `$` is escaped exactly once, and a test pins it. Probe answers are fenced with a fence that adapts to the content (`report.py:63-65`).
- **Graph 7 rendered from bots** matches the stats exactly (0/3 → [0, 0.71], 3/3 → [0.29, 1]).

### Issues

#### Critical
None.

#### Important
- **R28-1 (Important), `plots.py:654, 663-672, 739`; `report.py:171-173, 203-205`: the ITT rate and CI exclude errored (unlabelled) samples.**
  - **What the code does:** `bribe_table` computes `itt_k/itt_n` over `lab` (runs with a `t1_label`), not over every assigned run. Graph 7's subtitle says "ITT (all labelled runs)". The report's caveat says "ITT (every assigned run) is the primary cut" (`report.py:171`), and then its own arm-table text says "the rates use the runs that have a label".
  - **Why it matters:** this is a complete-case analysis labelled ITT. The binding constraint is "ITT covers every assigned run". At n = 3, one errored sample turns 0/3 [0, 0.71] into 0/2 [0, 0.84], and the reader sees "ITT" on both.
  - **Second symptom:** the "n per arm" disagrees between outputs. Graph 7's title uses `itt_n` (labelled, `plots.py:736`), while the report header uses `n_assigned` (`report.py:158`).
  - **Fix (pick one and state it in the caveat):**
    - (a) ITT n = n_assigned, with unlabelled runs reported as bounds: k/n with each missing outcome counted as 0 and as 1, giving two CP intervals or one CI spanning both; or
    - (b) rename the column "labelled (complete-case)", and add an ITT column over n_assigned that shows the missing count explicitly.

    Then make graph 7's n and the report's n come from the same field. `test_report_itt_before_per_protocol_with_ci` (`test_plots.py:194-198`) currently enshrines n = labelled and must change with the fix.

#### Minor
- **R28-2 (Minor), `test_plots.py:188-200`: the ITT test is weak.**
  - `md.find("ITT")` first hits the "Runs" table ("ITT: all assigned"), and `md.find("per-protocol")` hits the caveat. So the order of the arm-table columns is not really tested.
  - `f"{k}/{n}" in md` and `f"| {len(agent)} |" in md` can match any cell.
  - Fix: slice the arm-table section and check the header column order and the specific row.
- **R28-3 (Minor), `plots.py:753-760`; `report.py:294-297`: the HP_norm anchors are keyed by `(seed, dose)` only.** If `bots_dir` holds window- and full-mode bot runs of the same seed and dose, the dict silently keeps whichever loaded last, and HP_norm uses the wrong anchor. Fix: key by `(seed, dose, mode, variant)`.
- **R28-4 (Minor), `plots.py:848, 60, 166-169`: graph 8 series sizing and colour.**
  - The geometric size step `220·0.4^i` hits the 16 pt² floor by the 4th series. In my bot render, the legend markers for series 5–8 are near-invisible (cheater, exploit, approve_all and refuse_all show as dots). This is fine for the 2–3 agent series of the pilot, but fragile.
  - The comment "so a model keeps its colour across batches" is false: the slot index depends on which known series are present. Fix: index `SLOTS` by position in `KNOWN_SERIES`.
- **R28-5 (Minor), `report.py:431-437`: the spend shown is the whole-ledger total.** "Ledger total" sums every step to date, not this batch. The label is accurate, but the batch's own spend is not given. Add per-step rows (`step` field) or filter by the batch's step.
- **R28-6 (Minor), `test_plots.py:154-165`: the "exploratory" wording test covers 4 of the 9 functions.** Graphs 4, 5, 8 and 9 are not checked (graph 7 has its own test). Parametrise the test over every plot function.
- **R28-7 (Minor), `plots.py:178-181`: an arm is (series, dose), ignoring `mode` and `variant`.** Window-mode and full-horizon runs of the same model and dose would pool into one ITT rate if they ever share a batch dir. Add `mode` to the arm key, or assert there is one mode per batch.

### Assessment
**Task quality: Needs fixes.**

**Reasoning:** the graphs and report are well built and honest in most details. But the headline ITT number silently drops unlabelled runs while being labelled ITT. That is the one thing the pilot's primary result must get right.

---

## Cross-task: how 27 and 28 fit together

- **Fit:** Task 28 consumes Task 27's `RunFrame` and `labels_table` without reaching into the JSONL. The seam holds (spec §9.1). The `tool_calls.turn` extra in Task 27 was needed by graph 2. Task 28's small additions to `load.py` and `awareness.py` (`awareness_context`, `contexts()`) are consistent.
- **X-1 (Minor), `load.py:432-454`; `report.py:244-248`; `test_plots.py:74-75`: no guard against the same sample appearing twice.** Nothing stops the same (model, seed, dose, sample_id, epoch) from loading twice when a batch dir holds two `.eval` files, for example a rerun or a cache replay. Both count toward `n_assigned`. The paired-by-seed dict then silently overwrites one of them (`by.setdefault(seed)[dose] = k`). The Task 28 fixture puts a fresh run and its cache replay in one arm, which normalises this. Fix: warn on duplicates in `load_batch` or the report, and list them, or exclude all-cached replays from ITT n and say so.
- **X-2 (note, ruling check): `fisher_one_sided`, `holm` and `paired_exact` are built but unused by the report.** DD §10.4 says to report the paired exact and Holm-corrected Fisher tests, labelled exploratory. The batch constraint ("no significance claims; H1 only on the cannot-report list") overrides that, and the code follows the constraint. The ruling looks right for n = 3, but the DD/constraint conflict is not written in the ledger. Record it, so Task 31 does not add p-values back.
- **X-3 (note, outside this batch): HP_norm anchors look weak.** In my bot render, bot HP_norm spans about −7 to +3, and `honest_legal_max` sits above `oracle` (graph 8, panel a). So the oracle is not an upper anchor, and agent HP_norm values may be hard to read. This comes from the engine's honest-profit definition or the oracle bot, not from the analysis code. Flag it to the owner before Task 31's write-up.
- **Ledger rulings:**
  - The figures dir `figures/` over `fig/` is consistent with spec §8/§9.1. Agreed.
  - "Awareness hits are candidates, shown with context" is implemented at `report.py:360-366`. Agreed.
  - The deferred minors look acceptable:
    - the NPL ceiling taken from config;
    - the in-call markers that can be one turn early;
    - the fixture not being marked slow.
  - The carries to Task 32 are correct, since `AUDIT_EVENT_TYPES = ()` at `load.py:55` is the seam.

## Counts
- Critical: 0
- Important: 1 (R28-1)
- Minor: 11
  - R27-1 to R27-4
  - R28-2 to R28-7
  - X-1
- Notes: 2 (X-2, X-3)
