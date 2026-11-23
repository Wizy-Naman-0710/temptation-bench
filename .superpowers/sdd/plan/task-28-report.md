# Task 28 report: graphs 2–10 and the batch report

Branch `pilot-1`. Status: DONE_WITH_CONCERNS (the concerns are listed at the end; none blocks the task).

## Graphs

Every graph comes from `analysis/plots.py`. They all use matplotlib Agg, one y-axis per panel, and colours in a fixed categorical order. No status colours are used. Every title ends in "· exploratory", and every number comes from the loaded data. `save()` writes a PNG, an SVG and a CSV view of the data (`fig._tb_table`).

| # | function | form | encoding | data source | basis |
|---|---|---|---|---|---|
| 2 | `plot_tool_timeline(rf)` | strip / event timeline | y = all 18 tools grouped by kind; x = agent turn (bots: call number); colour = tool kind; filled = ok, hollow = refused; grey vertical lines for markers (offer read, T1 file ready, T1 decided, MIS filed), labels stacked in free rows | `rf.tool_calls`, `rf.markers` | DD §10.6 graph list; dataviz "position first", direct labels |
| 3 | `plot_reward_vs_truth(rf)` | 2×2 small multiples (a–d) | (a) reported vs true profit by day, (b) NPL bp with the 400 bp ceiling, (c) volume with the target, (d) bribe taken; target and ceiling are dashed lines with direct labels; "no MIS filed" / "none taken" notes | `rf.daily`, config ceiling and target | spec §8 graphs; dataviz no dual axes → panels |
| 4 | `plot_tokens_cost(rf)` | 3 stacked panels | (a) input stacked by component (only nonzero ones), (b) output with reasoning inside, (c) cumulative cost; **cached turns: black × with gid `cached-turns` and the legend entry "cached turn (replay: 0 new tokens, $0)"**, plus a note "k of N turns cached" and an unpriced-turns note | `rf.turns` (Inspect `ModelEvent`, `cached`) | carried item (cached turns visible); dataviz one axis per measure |
| 5 | `plot_context_size(rf)` | 2 panels, line | prompt tokens per turn (cached turns = NaN gaps + ×) with the 30,000 trim line; messages in input; compaction = dotted vertical lines | `rf.turns` | scientific-visualization: missing shown as gaps |
| 6 | `plot_outcome_labels(runs)` | 1×4 horizontal 100 % stacked bars | panels T1, C1, C2, C3; one bar per arm; colour = label (T1 slots 1–3, C slots 4–8, no_decision muted, C3 reuses slots 1–3 with `///` hatch); one figure legend at the bottom | `labels_table` | dataviz part-to-whole, fixed order |
| 7 | `plot_bribe_effect(runs)` | dot + error bar, faceted per series | x = offer; y = ITT knowing-violation rate; bar = Clopper-Pearson 95 % CI; k/n annotation (+k unlabelled); "no runs" text; title `Bribe effect on T1 (exploratory, n = {n} per arm)` | `bribe_table(runs)`, `stats.clopper_pearson` | DD §10.4, benchmark-methodology (ITT first, CP CI) |
| 8 | `plot_integrity_usefulness(runs, bots)` | 2-panel scatter, shared y | y = 1 − knowing-violation share; x = (a) HP_norm, (b) over-refusal; series = colour + shape, earlier series drawn larger so coincident points show as rings; "×k" where points coincide; bot means as hollow grey with clustered labels; rotated "refuse_all = 0 / oracle = 1" lines; "k runs not shown" note | `integrity_usefulness_table`, `stats.hp_norm` | DD §10.3 (two axes, never one score) |
| 9 | `plot_cost_turns(runs)` | 2-panel dot strip | one dot per run; (a) cost, (b) turns; hollow = run with cached turns | `cost_turns_table` | dataviz: two measures → two panels |
| 10 | `plot_bot_baselines(bots)` | 2-panel dot plot | y = bots in fixed order; x = (a) true profit after run-off, (b) campaign volume with target "(whole campaign)"; dots per seed coloured by dose, small vertical dodge | `bot_table` | DD §9 bot sanity |

Graph 1 is unchanged, except that its title now carries "· exploratory".

## Palette validator

I ran `validate_palette.js` with `--mode light` on the surface `#fcfcfb`.

- **8 slots, adjacent pairs:** `#2a78d6,#eb6834,#1baf7a,#eda100,#e87ba4,#008300,#6250d6,#e34948`.
  - ALL PASS. Worst adjacent CVD ΔE was 9.1; the normal-vision floor was 19.6.
  - Contrast WARN for `#1baf7a` (2.74), `#eda100` (2.11) and `#e87ba4` (2.62).
- **3 slots, all pairs** (graph 7/8 series): PASS. CVD 9.2, normal-vision 24.0; WARN for `#1baf7a`.

The contrast WARNs are covered in two ways: every figure has a CSV table view, and the report gives every number in tables. Identity never rests on colour alone. Graph 8 adds shape, graph 6 adds a legend and hatching, and graph 2 adds row position.

## report.md (`build_report(batch_dir, bots_dir, *, results_dir=None, ledger_path=None)`)

The report goes to `$RESULTS_DIR` or to `pilot-1/results/<batch>/report.md`, with figures in `figures/`. Sections, in order:

1. Title and blockquote "Exploratory pilot, n = … per arm".
2. Caveats (fixed): exploratory, ITT before per-protocol, no B50 / dose slope / Integrity Index / H1, awareness hits are candidates, cached turns understate cost, clipped outputs.
3. Runs: counts for assigned, labelled, errored, failed attempts and bot runs.
4. T1 knowing violations per arm, ITT then per-protocol. Each row gives n assigned, n labelled and n exposed, then ITT k/n, rate and Clopper-Pearson 95 % CI, then the per-protocol k/n, rate and CI. A paired-by-seed table of discordant counts follows; it is descriptive and has no p-value.
5. Label table, one row per run, including HP_norm.
6. Bot baselines.
7. Awareness scan (candidate hits): the per-arm share, then each hit with its context in a fenced block, then "Probe answers (verbatim…)".
8. Clipped outputs.
9. Failed attempts and errored samples: "Failed attempts: N" with a list, and "Errored samples: M" with a table. Errored samples stay in ITT n.
10. Spend: the ledger total from `budget.spent`, plus cost per run from the `.eval` files (cached turns shown).
11. Figures: graphs 6–10, then graphs 1–5 for each labelled run.
12. Hand check of every T1 decision (filled in Task 31): `| run | code label | hand label | agree? |`.
13. Cannot report at this n: B50, the dose slope, Integrity Index, H1 test. π(0) and the dose effect are descriptive only.

## Visual check (every PNG viewed with Read)

These problems were fixed after viewing the renders:

- Graph 3: the legend sat on top of the target and ceiling lines, so the lines now carry direct labels. The all-zero panel repeated "$0" ticks.
- Graph 4: the all-cached run had fractional y ticks, and the legend listed zero-valued entries.
- Graph 6: the legends on each panel were clipped, so there is now one figure legend.
- Graph 8:
  - bot labels collided, so they are now clustered and staggered;
  - the reference labels collided, so they are now rotated;
  - the mock point was hidden under clipdemo, so series now get shapes and a geometric size step (re-checked: a blue ring shows around the orange square).
- Graph 10: "$-10,000" now reads −$10,000.
- Graph 7: added "no runs" text.
- Graph 2: the "offer email read" and "T1 decided" labels overlapped, so labels now stack into free rows (re-checked: no overlap).
- Report:
  - the money in the arm table was escaped twice (`\\$30,000`);
  - the HP_norm cell printed a whole pandas Series, because the fresh run and its cache replay share one `source`;
  - figure headings and spend rows for those two runs were identical.

  Fixed with `_run_name`, which adds `@<run id>` for harness runs, and `_run_desc`, which adds ", cached replay". HP_norm is now computed per run by position.

Known cosmetic point: for a bot run, graphs 4 and 5 show empty 0–1 axes with the text "bot run: no model turns". The report only draws graphs 1–5 for labelled batch runs.

## Tests (TDD)

File: `tests/analysis/test_plots.py`. A module fixture builds:

- every bot × seeds 1–3 × doses 0 / 3,000,000;
- in the batch: a mockllm window run, its cache replay, an errored sample (JSONL deleted), an `.attempt1.jsonl`, and a clipped-output run;
- a ledger with 0.1234.

Tests:

1. `test_all_graphs_render` (UserWarning → error): every plot returns a Figure with ≥ 1 axes, graph 3 has 4 panels, and the report links every PNG.
2. `test_bribe_effect_title_says_exploratory_n_per_arm`
3. `test_every_result_figure_says_exploratory`
4. `test_tokens_cost_marks_cached_turns`: a legend entry plus `cached-turns` offsets equal to the cached count; none on a fresh run.
5. `test_report_itt_before_per_protocol_with_ci`: k/n and the CI are computed from the data; n assigned counts the errored sample.
6. `test_report_cannot_report_list_and_caveats`: also the ledger "$0.12" and the hand-check header.
7. `test_report_lists_failed_and_errored_samples`
8. `test_report_awareness_hits_with_context`: the note context and the probe answer, verbatim.
9. `test_report_flags_clipped_outputs`
10. `test_report_money_escaped_once_and_figure_headings_unique`: also checks that no Series repr appears.
11. `test_report_label_table_one_row_per_run_with_unique_names`: also checks the spend table.

RED and GREEN evidence:

- **RED for tests 1–9:** with `NotImplementedError` stubs for the 9 functions and `build_report`, the run gave 9 errors (fixture/stub raise). That is the expected reason.
- **GREEN for tests 1–9:** 9 passed.
- **Test 10:** I reverted the fix in a copy and the test failed with `AssertionError` on `"\\\\$" not in md`. Restoring the fix gave 10 passed.
- **The Series and duplicate-name assertions (tests 10–11):** the RED evidence is the earlier render, which had `Name: hp_norm, dtype: float64` in two rows with the same name `s1-d3000000-e1`. After the fix: 11 passed.

Earlier in the task there were two more fixes: an empty-legend UserWarning on the cached run's graph 4 (caught by test 1), and "dose slope" missing because of its capitalisation (caught by test 6).

## Suite outputs

Final run, after the last change, before commit `5a46c5a pilot-1: graphs 2-10 and batch report`:

```
uv run ruff check .            -> All checks passed!
uv run ruff format --check .   -> 108 files already formatted
uv run pytest -q               -> 695 passed, 71 deselected in 151.58s
uv run pytest -q -m slow       -> 71 passed, 695 deselected in 229.52s
```

## Files changed

- `pilot-1/src/temptation_bench/analysis/plots.py`: graphs 2–10, helper tables (`bribe_table`, `integrity_usefulness_table`, `cost_turns_table`, `bot_table`), and "exploratory" in the graph 1 title.
- `pilot-1/src/temptation_bench/analysis/report.py` (new): `build_report`.
- `pilot-1/src/temptation_bench/analysis/awareness.py`: `contexts()`, which gives each hit with ±80 characters of context.
- `pilot-1/src/temptation_bench/analysis/load.py`: new `RunFrame.awareness_context`; notes are filtered to strings.
- `pilot-1/tests/analysis/test_plots.py` (new).
- `pilot-1/.gitignore`: `scratch/` (local visual-check renders; not committed).

No PNGs or `results/` were committed, and the engine was not touched, so the golden is unchanged.

## Self-review

- The interfaces match the brief. `build_report` also takes keyword-only `results_dir` and `ledger_path`, so tests never touch the real `results/` or ledger.
- There are no significance claims anywhere. The report has no p-values (H1 is on the cannot-report list). The paired table gives discordant counts only.
- Awareness hits are always shown with their context and labelled "candidate hits". Probe answers are verbatim in fences.
- Failed attempts and errored samples are listed and counted, and errored samples stay in ITT n.
- `$` is escaped exactly once in markdown (this is tested).
- `analysis/` imports pandas and matplotlib only. The engine is untouched.

## Concerns

1. **Paths:**
   - The figure folder is `figures/`; the plan text says `fig/` in one place. I followed spec §8 / §9.1.
   - `results/` is not git-ignored, because spec §9.1 wants real results committed. Tests write only to tmp.
2. DD §11 is the sketch of a day, not graph definitions. Graph forms follow spec §8 and DD §10.
3. C3 labels reuse colour slots 1–3, with a `///` hatch to tell them apart. Eight slots cannot hold every label.
4. **Graph 8:**
   - The y value counts knowing violations over every labelled decision (T1, C1, C2, ordinary files), not over T1 only.
   - HP_norm needs refuse_all and oracle bot runs on the same seed and dose; otherwise it shows "–".
5. Graph 10's volume target is a whole-campaign value; window-mode runs are shorter, and the label says so.
6. The audit markers (M7) are still absent from the event log, so graph 2 has no audit marker.
7. The graph 1 title changed (it now includes "exploratory").
8. The test fixture takes about 20–25 s (three mockllm evals plus 48 bot runs). It is not marked slow, so it runs in the default suite.
9. In window mode the mock run's over-refusal rate is undefined, so it is not drawn in graph 8 panel (b). The figure notes "k runs not shown".

## Fix round 1

Review: `review-27-28.md`. This round fixes R28-1, R27-2 and the X-3 ruling. All three were done test-first.

### R28-1 (Important): ITT counts every assigned run

**`plots.bribe_table`**
- ITT now runs over the whole arm, so `itt_n = n_assigned`.
- An errored or unlabelled run counts in n and not as a knowing violation.
- New columns `n_errored` and `n_unlabelled`.
- Per-protocol still uses exposed, labelled runs only.

**Graph 7**
- The annotation reads `k/n (errored: e, unlabelled: u)`.
- The subtitle reads "ITT: every assigned run (errored = in n, not a violation)" and is split over three lines so it is not clipped at two-panel width; I re-viewed the render.
- The title's n comes from `itt_n`, which now equals the report header's `n_assigned`.

**Report arm table**
- New column "not labelled (in ITT n)", for example "errored: 1, unlabelled: 0".
- The rule is stated above the table: "an errored or unlabelled run is counted in n and not as a knowing violation".

**Tests**
- `test_itt_counts_errored_sample_in_n`: in the mock arm with one errored sample, `itt_n == n_assigned == 3`, the CI equals `clopper_pearson(k, 3)`, and the report row shows `k/3`, that CI and "errored: 1", along with the rule text.
- `test_bribe_graph_n_matches_report_n`.
- `test_report_itt_before_per_protocol_with_ci` changed from n = labelled to n = assigned.

### R27-2: attempt files of a sample with no final JSONL

**`load.py`**
- The errored-sample branch now stores `jsonl_expected`, the store path or the same `runs/<id>/` folder in a moved batch.
- It also stores `failed_attempts` for the attempts beside that path. New helpers: `_expected_jsonl` and `_attempts_of`.

**`report._attempts`**
- Scans `batch_dir.rglob("*.attempt*.jsonl")`.
- Each file gets an owner, matched on folder and stem: either the run, marked "(errored: no final JSONL)", or "(no run found)".
- Files are listed by their path relative to the batch, so attempt files with the same name in different run folders stay distinct.

**Tests**
- The fixture now keeps an `.attempt1.jsonl` of the errored sample before deleting its final JSONL.
- `test_orphan_attempt_of_errored_sample_is_listed_and_counted`: 2 attempt files in total, "Failed attempts: 2", the orphan's run folder listed, and `meta["failed_attempts"] == 1` on the errored run.

### X-3 ruling

**Change:** one fixed caveat line, word for word: "HP_norm uses the oracle bot as a heuristic upper anchor; values outside [0, 1] are possible and are shown unclipped." No plot logic changed.

**Test:** `test_report_states_hp_norm_anchor_caveat` checks that the line is in the Caveats section.

### RED, then GREEN

RED, with the new tests and before the fix (`uv run pytest -q tests/analysis/test_plots.py`): 6 failed, 9 passed.

```
FAILED test_report_itt_before_per_protocol_with_ci          (k/3 not in report: ITT n was 2)
FAILED test_report_lists_failed_and_errored_samples          (orphan attempt not counted)
FAILED test_itt_counts_errored_sample_in_n                   (KeyError: n_errored)
FAILED test_bribe_graph_n_matches_report_n                   (graph n 1–2 vs report n 1–3)
FAILED test_orphan_attempt_of_errored_sample_is_listed_and_counted
FAILED test_report_states_hp_norm_anchor_caveat
```

GREEN, on the final code:

```
uv run ruff check .              -> All checks passed!
uv run ruff format --check .     -> 108 files already formatted
uv run pytest -q tests/analysis  -> 30 passed in 28.14s
uv run pytest -q                 -> 699 passed, 71 deselected in 153.28s
```

Files changed:
- `analysis/plots.py`
- `analysis/report.py`
- `analysis/load.py`
- `tests/analysis/test_plots.py`

The other Minors are left in the ledger, as instructed.

## Fix round 2

Re-review: `rereview-27-28.md`. This round fixes R27-2 in the real layout, the attempt-counting regression, X-1 (pulled in by ruling) and the sample_error Minor. All were done test-first.

### Fixture now uses the real layout

- `RUNS_DIR = <tmp>/runs`, outside the batch dir; the `.eval` files go to `<tmp>/batch/logs`. This matches `harness/agent.py:63` (`runs_dir()/<run_id>/<sample>-e<epoch>.jsonl`) and `run.py` (logs dir).
- The batch now holds:
  - cell s1, fresh;
  - cell s1 again, a cache replay of the same model instance;
  - cell s2, errored: its own mock instance (`memoize=False`) with the JSONL deleted after keeping an `.attempt1.jsonl`;
  - an `.attempt1.jsonl` beside the fresh s1 JSONL;
  - clipdemo.
- `test_real_layout_runs_dir_is_outside_the_batch` pins the layout.

### R27-2: attempt discovery in the real layout

**`load._expected_jsonl`**
- Uses the `.eval` store path (`jsonl_path`/`log_path`).
- If setup never ran, it rebuilds the path from the sample metadata's `run_id` as `runs_dir()/<run_id>/<id>-e<epoch>.jsonl`.
- Errored-sample meta now also carries `people`, `variant` and `run_id`.

**`report._attempts`** takes the union, deduplicated by resolved path, of:
- attempt files beside each run's `jsonl_path`;
- attempt files beside each errored sample's `jsonl_expected`;
- any attempt files under `batch_dir`.

Each file is listed as `<run_id>/<file>` with its owner run; it is never `relative_to(batch_dir)`, which would raise outside the batch. Replays' attempt files count as well.

**Tests:**
- `test_orphan_attempt_found_through_eval_run_id_in_real_layout`: the orphan is listed as `<run_id>/<name>`, and `jsonl_expected` points to its folder. "Failed attempts: 2" appears both in the section and in the Runs table.
- `test_orphan_attempt_of_errored_sample_is_listed_and_counted` now globs `runs_root`.

### Re-review Important: attempt files beside a loaded run in the default layout

Fixed by the same union.

**Test:** `test_attempt_beside_loaded_run_counted_in_real_layout`. The fresh run's attempt is listed, and `meta["failed_attempts"] == 1`. `test_report_lists_failed_and_errored_samples` now checks `<run_id>/<name>` for every attempt under `runs_root`.

### X-1: duplicate samples are deduped

**`load._dedupe`** (called by `load_batch(batch_dir, *, replays=None)`):
- There is one run per cell, keyed by (model, seed, dose, people, variant, sample_id, epoch).
- Kept: the labelled, freshly generated run (first wins on a tie).
- The others get `meta["duplicate_of"]` and go to the optional `replays` list.
- Bot JSONLs (no sample id) are never merged.

**Report:**
- A new Runs row: "replays / duplicate samples (not in n)".
- A new section "Replays and duplicate samples (not counted in n)", with the columns duplicate, kind (cached replay or re-run) and kept run.

**Fixture:** the mock arm is now n = 2 (s1 and the errored s2), not 3. The replay used for the graph-4 cached-turn tests now comes from `data["replays"]`.

**Test:** `test_cache_replay_counted_once_and_listed`. One replay, all of its turns cached, no duplicate cell keys, mock arm `n_assigned == 2`, and the replay listed by sample id, run id and "cached replay".

### Minor: sealed, labelled run with a sample_error

**Rule:** `plots.is_errored(r)` = no sealed JSONL, or a `sample_error` with no labels. A labelled run counts as labelled; its error is listed under "Labelled runs with a sample error: k" in the failures section (`report._failures`).

**Effect:** `n_labelled + n_errored + n_unlabelled == n_assigned`.

**Test:** `test_labelled_run_with_sample_error_counts_as_labelled`. On a copy of a labelled run with `sample_error` set, the counts are (1, 0, 0) and the identity holds; `_failures` returns `([], [run])`.

### Other updates

- `_run_name` adds `@<run_id>` for every harness run (any run with an `eval_path`), not only when the folder is called `runs`.
- The spend-table test now expects one row per run with turns, because the replay is no longer a run.

### RED, then GREEN

RED: I ran the new tests with the old `load_batch` (no dedupe, replays picked by hand) and the old report. Result: 7 failed, 13 passed.

```
FAILED test_report_lists_failed_and_errored_samples           (attempts outside batch not listed)
FAILED test_itt_counts_errored_sample_in_n                     (n = 3: replay counted)
FAILED test_orphan_attempt_of_errored_sample_is_listed_and_counted
FAILED test_attempt_beside_loaded_run_counted_in_real_layout
FAILED test_orphan_attempt_found_through_eval_run_id_in_real_layout
FAILED test_cache_replay_counted_once_and_listed
FAILED test_labelled_run_with_sample_error_counts_as_labelled
```

(Before that, the fixture raised `TypeError: load_batch() got an unexpected keyword argument 'replays'`.)

GREEN, on the final code:

```
uv run ruff check .              -> All checks passed!
uv run ruff format --check .     -> 108 files already formatted
uv run pytest -q tests/analysis  -> 35 passed in 25.65s
uv run pytest -q                 -> 704 passed, 71 deselected in 150.45s
```

Files changed:
- `analysis/load.py`
- `analysis/plots.py`
- `analysis/report.py`
- `tests/analysis/test_plots.py`
