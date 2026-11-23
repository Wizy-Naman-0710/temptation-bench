# Re-review: batch [27, 28], fix round 2 (5a5b6c7..55cfde5)

### Finding Verdicts

- **R27-2: attempt files found, listed and counted in the REAL layout (engine JSONLs in `runs/<run_id>/`, `.eval` in `logs/...`, both outside the batch dir), including a sample whose final attempt has no JSONL.** ADDRESSED.
  - **Real layout checked:**
    - `harness/task.py:40,49` puts `run_id` in the sample metadata.
    - `harness/agent.py:62-63` writes `runs_dir()/<run_id>/<sample_id>-e<epoch>.jsonl` to the store.
    - `run.py:343` puts `.eval` files under `logs/<step>-<stamp>`.
  - **Expected path of an errored sample:** `load._expected_jsonl` (`load.py:424-441`) takes the store's absolute `jsonl_path`/`log_path`. That path is outside the batch and its parent exists, so it is returned as-is. If setup never ran, it falls back to `runs_dir()/<run_id>/...` (`load.py:433`). `meta["failed_attempts"]` is counted beside that path (`load.py:518`).
  - **Report discovery:** `report._attempts` (`report.py:100-126`) globs beside every run's `jsonl_path` or `jsonl_expected` (`:118`), takes the union with the batch-dir `rglob` (`:120`), and dedupes by resolved path.
  - **Listing:** files are listed as `<run_id>/<file>` (`report.py:446`), so `relative_to(batch_dir)` no longer raises.
  - **Count:** the same list feeds both the Runs-table count and the section count (`report.py:220, 227`).
  - **Tests:** the fixture now sets `RUNS_DIR` outside the batch (`test_plots.py` fixture), and `test_real_layout_runs_dir_is_outside_the_batch` pins this. `test_orphan_attempt_found_through_eval_run_id_in_real_layout` checks that `jsonl_expected` points to the orphan's folder, that the orphan is listed, and the count in both places.

- **Round-1 regression: attempt files beside a loaded run's JSONL counted again in the default layout.** ADDRESSED.
  - The glob beside each `jsonl_path` (`report.py:113-119`) restores this wherever `runs/` lives.
  - `test_attempt_beside_loaded_run_counted_in_real_layout` checks the listing and `meta["failed_attempts"] == 1`.
  - `test_report_lists_failed_and_errored_samples` now globs `runs_root`, not `batch_dir`.

- **X-1: dedupe by (model, seed, dose, people, variant, sample_id, epoch); a cache replay counts once and is listed as a replay; ITT n not inflated.** ADDRESSED.
  - **Key:** `_cell` (`load.py:452-455`) uses exactly those 7 keys.
  - **Same values on both paths:** an errored run's metadata (`task.py:45-51`) and a loaded run's `run_config` (`runtag.py:29-39`; `people_name` gives "template"/"prose", `people.py:150,167`) both carry int seed and dose and str people and variant. So an errored sample and its successful re-run fall into the same group.
  - **Which run is kept:** the labelled, non-cached run (`load.py:474`). The others go to `replays` and get `duplicate_of`. Dedupe always runs (`load.py:530`).
  - **Report:** a Runs row (`report.py:229`) and a "Replays and duplicate samples" section with kind "cached replay" (`report.py:484-505`). Replays still count toward attempt files (`report.py:220`).
  - **ITT n:** the arm now has n = 2 (`test_itt_counts_errored_sample_in_n`, `test_cache_replay_counted_once_and_listed`).

- **Ruling on sample_error: a sealed, labelled run counts as labelled, its error is listed in the failures table, and it is never counted both as errored and in k.** ADDRESSED.
  - **Rule:** `plots.is_errored` (`plots.py:648-651`) means `error` (no JSONL), or `sample_error` with no labels.
  - **Never both:** a run with labels has `t1_label` (always a str, `scoring.py:80,447`), so it can be in k but never in `n_errored`. An errored run has no labels, so it is never in k.
  - **Failures list:** `report._failures` (`report.py:129-133`) feeds "Errored samples" and "Labelled runs with a sample error: k", plus a table (`report.py:470-480`).
  - **Test:** `test_labelled_run_with_sample_error_counts_as_labelled` checks the counts (1, 0, 0) and the identity.

### New Breakage in the Fix Diff

- **Minor, `load.py:474` + `report.py:497`: an errored sample that has a successful re-run in the same batch moves to `replays`.**
  - It leaves the "Errored samples" table, and its `sample_error` text is not shown anywhere.
  - The replays table labels it "re-run" when it is really the failed copy.
  - n is correct and its attempt files are still counted. Suggested fix: add an "errored" kind, or the error text, to the replays row.
- **Minor, `load.py:433`: the setup-never-ran fallback uses `runs_dir()` at analysis time, not at run time.**
  - If `RUNS_DIR` differs between the two, the path is wrong and the attempt count is 0.
  - Low impact: attempt files only exist once setup has run, and that case takes the store path instead.
- **Minor, `load.py:463-464` vs `report.py:91-92`: `_all_cached` is duplicated, and `_run_desc` (`report.py:95-97`) repeats the logic inline.** This is a nit.

### Out-of-Scope Observations

1. **Latent crash in `plots.py:673`, on a line this fix did not change:** `r not in errored` runs the dataclass `RunFrame.__eq__`, which compares DataFrames.
   - Checked: `b in [a]` raises `ValueError: The truth value of a DataFrame is ambiguous`.
   - It is reached only for an arm that has both an errored run and a run that is not errored but has `t1_label` None. Today that cannot happen, because every loaded JSONL is scored.
   - Use `any(r is e for e in errored)`, or `@dataclass(eq=False)`.
2. **The dedupe key (`load.py:452-455`) leaves out `pressure`/`observation`.**
   - That is fine for pilot-1: the reference cell is fixed by the variant, and the sample id is `s<seed>-d<dose>`.
   - FULL-factor batches would merge distinct cells. Ledger this for any later factor work.

### Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage. R27-2, the round-1 regression, X-1 and the sample_error ruling are all ADDRESSED; there are 3 new Minor issues and 2 out-of-scope notes.
