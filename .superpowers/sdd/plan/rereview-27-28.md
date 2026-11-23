# Re-review: batch [27, 28], fix round 1 (78f1efb..5a5b6c7)

### Finding Verdicts

- **R28-1 (Important): the ITT rate and CI exclude errored (unlabelled) samples.** ADDRESSED.
  - **ITT counts every assigned run:** `plots.py:129` loops `("itt", arm)` over the whole arm, so `itt_n = n_assigned`. `k = sum(_kv(r) or 0)` (`:130`) means an errored or unlabelled run is in n and is not counted as a violation.
  - **Errored runs are a separate per-arm count:** `n_errored` and `n_unlabelled` (`plots.py:116, 123-124`). The report shows them in the "not labelled (in ITT n)" column (`report.py:310, 326`) and states the rule (`report.py:296-299`).
  - **Graph 7's n matches the header's n:** graph 7's title uses `itt_n` (`plots.py:194-196`), which now equals `n_assigned`. The report header uses `n_assigned` (`report.py:167`). `test_bribe_graph_n_matches_report_n` pins this.
  - **Per-protocol still counts exposed runs only:** `pp = [r for r in lab if exposed]` is unchanged (`plots.py:117`).
  - **Wording:** the subtitle that said "ITT (all labelled runs)" has been replaced (`plots.py:198`). The old arm-table sentence, "the rates use the runs that have a label", is gone.
  - **Tests:** `test_itt_counts_errored_sample_in_n` checks n = 3, the CI and "errored: 1" on the specific arm row. The old test that enshrined n = labelled was updated (`test_plots.py:425-431`).

- **R27-2 (promoted): attempt files of a sample with no final JSONL must still be found, listed and counted.** NOT ADDRESSED for the real batch layout. It is addressed only when `runs/` sits inside `batch_dir`.
  - **The loader side works:** `load.py:64, 76-78` stores `jsonl_expected` and `meta["failed_attempts"]` for the errored run.
  - **The report ignores that data:** it no longer uses the per-run paths or `meta["failed_attempts"]`. `report._attempts` only does `Path(batch_dir).rglob("*.attempt*.jsonl")` (`report.py:242`), so it finds only attempt files that sit under `batch_dir`.
  - **The real layout keeps them apart:**
    - `.eval` files go to `logs/paid/<step>-<stamp>/` (`run.py:49, 343`).
    - JSONL and attempt files go to `runs_dir()/<run_id>/`, which defaults to `pilot-1/runs` (`harness/agent.py:63`, `engine/config.py:63-65`).
  - **Result:** `build_report(logs/paid/<step>-<stamp>, ...)` finds no attempt files at all. The orphan is still not listed or counted in the report.
  - **Why the test passes:** the fixture sets `RUNS_DIR=batch/runs` (`test_plots.py:71`), which hides this.

- **X-3 (ruling): fixed HP_norm caveat line.** ADDRESSED.
  - The line is word-for-word in the Caveats list (`report.py:267-268`).
  - `test_report_states_hp_norm_anchor_caveat` checks it inside the Caveats section.
  - The diff makes no change to plot logic for HP_norm.

### New Breakage in the Fix Diff

- **Important, `report.py:231-245, 275`: regression for every attempt file in the default layout.**
  - **Before the fix:** `_attempt_files(r)` globbed beside each run's absolute `jsonl_path`, so attempt files of runs with a JSONL were counted wherever `runs/` lived.
  - **After the fix:** only files under `batch_dir` are counted. When `batch_dir` is the `logs/paid/...` directory, the "failed attempt files" count (`:283`) and the "Failed attempts" section (`:346-355`) both drop to 0/"None.". That silently breaks "failed attempts counted, never dropped".
  - **Suggested fix:** take the union of the batch-dir `rglob` with each run's `jsonl_path` and `jsonl_expected` parent globs (dedup by resolved path). List files outside `batch_dir` by absolute path, since `relative_to(batch_dir)` (`:351`) would raise on them. Add a test with `RUNS_DIR` outside the batch dir.
- **Minor, `plots.py:116, 124`; `report.py:310, 326`: a run with a sealed JSONL and labels but a `sample_error` is counted in `n_errored`, and its label can still count in k.**
  - The "not labelled (in ITT n)" column then reports it as not labelled, although it is labelled.
  - `n_labelled + n_errored + n_unlabelled` can exceed `n_assigned`.
  - ITT n itself is still correct. Suggested fix: count `n_errored` as `error`, or as `sample_error` with no label, or rename the column.

### Out-of-Scope Observations

1. **X-1 (already in the ledger) has a larger effect now.** In the fixture, the fresh run and its full cache replay share one arm, so ITT `n = 3` counts the cache replay as an assigned run (`test_plots.py:373-374, 469`). Now that ITT n = n_assigned, any duplicate or replay sample inflates the headline n directly. The ledger should note this for Task 31.

### Verdict

**Fix round:** findings remain open.
- **R27-2:** NOT ADDRESSED in the real `logs/` vs `runs/` layout.
- **New breakage (Important):** attempt-file counting in the report regressed to batch-dir-only (`report.py:242`).
- **R28-1 and X-3:** ADDRESSED.
