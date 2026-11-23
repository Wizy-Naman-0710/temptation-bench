### Finding Verdicts

Review done in one pass over the diff file (1797 lines), plus a few read-only greps of the source tree to confirm field names (F-8) and the ledger-total label (F-2). No tests were re-run. The implementer's report names the covering test for each finding and gives the four suite tail lines (870 passed / 75 slow passed / ruff check clean / ruff format clean). Those results are consistent with the diff.

- **F-1 (Important): floats in the engine log, change not recorded.** ADDRESSED.
  - The PROGRESS §8 row (diff lines 72) names the four fields, commit 1218653, the platform (macOS-26.5.2-arm64-arm-64bit-Mach-O, CPython 3.13.0), "cross-platform golden equality is not claimed" and "int ppm is a FULL-study item".
  - `harness/settings.py` `write_harness_json` adds `"platform": {platform, machine, python}` with a comment that it never goes in `run_config` (diff ~1110-1120). No engine file and no golden file is in the diff.
  - Test: `tests/harness/test_settings.py::test_harness_json_records_the_platform`.
- **F-2 (Important): reports claim "none is hand-written" but carry hand-written sections.** ADDRESSED.
  - `report.py` `_hand_check` renders the table from `results/<batch>/hand_check.toml`. Each run key is `_run_name(r)`, the same name the label table shows. For a missing file or entry it writes a "no hand check recorded" row per run plus a `> **Warning:**` line, and it does not crash. It also flags a changed code label and stray entries, and computes the "k of n agree" line.
  - The header sentence is now true (`report.py` build_report header). "(filled in Task 31)" is gone.
  - The `extra_batches` parameter plus `_extra_panels` generates the mini-batch "Full-horizon panels (D1-D30)" section.
  - All three `hand_check.toml` files are present. Mini-batch has 12 rows and the note about E-0001. Full-run has 1 row. Smoke has 1 row taken from PROGRESS §5.
  - The rebuilt report diffs only add content or change wording. No number changed: the label, bribe and spend lines match the committed ones. The lost content was reported: the "(seed 1001, offer \$30,000)" Graph 10 caption detail, which the intro still states.
  - Tests are the six F-2 tests in `tests/analysis/test_report_final_fixes.py`. See Minor N-1 below.
- **F-3 (Minor): the layering test ignores relative imports.** ADDRESSED.
  - `tests/test_layering.py::_imports` resolves `level > 0` with `importlib.util.resolve_name` against the file's package. The package is computed correctly for both modules and `__init__`. It also expands `from .. import name`.
  - Negative test: `test_relative_harness_import_in_engine_is_caught`.
- **F-4 (Minor): caveat for a Compliance report filed after the audit findings.** ADDRESSED.
  - `report.py::fixed_caveats` prints the caveat with a computed count ("runs with such a report: k of n").
  - The count comes from `load.audit_summary`, which counts `compliance_report` events after the first `audit_finding`.
  - It shows 0 of 1 / 0 of 12 / 0 of 1 in the three reports, so no uncomputed claim is made.
  - Tests: `test_late_compliance_report_caveat_is_always_there_with_a_computed_count`, `test_audit_summary_from_events`.
- **F-5 (Minor): caveat for estimated Haiku reasoning tokens.** ADDRESSED.
  - `REASONING_CAVEAT` (exact brief text) appears only when an `anthropic/*` model is in the batch (`fixed_caveats`).
  - Test: `test_reasoning_token_caveat_only_with_an_anthropic_model`.
  - The R22-1 ruling text was not amended, because it sits outside `pilot-1/`. The brief did not require it.
- **F-6 (Minor): per-run MIS and audit tables.** ADDRESSED.
  - `report.py::_mis_and_audit` builds the MIS table from `RunLabels.mis`, including a "– (not filed)" row for a missing filing. It builds the audit table from `meta["audits"]` (findings, or "none"), and prints "No internal audit events in these runs." when there are none.
  - Full-run now shows MIS-0001..0005 and IA-1 D16/D21/D23 with no findings.
  - Tests: `test_mis_and_audit_tables_per_run`, `test_window_batch_says_no_audit`.
- **F-7 (Minor): smoke, route_check and pregen caps not cumulative.** ADDRESSED.
  - `run.py` `STEP_SPEND_COUNTS = {smoke, route_check, pregen, mini_batch, full_run}`. A comment says why gfree is excluded.
  - `check_dollar_exposure` gained `prior` and refuses when `prior + e > cap`, the same rule `check_exposure` uses for mini_batch. `check()` now computes `prior` before the dollar-exposure branch.
  - No cap value changed.
  - Tests: `test_second_smoke_is_refused_when_prior_spend_plus_exposure_passes_the_cap`, `test_dollar_exposure_steps_count_earlier_spend[route_check|pregen]`, `test_spend_counting_steps_are_every_paid_step_but_gfree`.
  - Two existing tests were adjusted, legitimately: their ledger lines were `smoke`, which now count against the smoke cap.
  - The per-step behaviour table is in the report. A default smoke is now refused (\$0.0144 + \$1.00 > \$1.00), as expected.
- **F-8 (Minor): `exposed` False when T1 is undecided but the offer was read.** ADDRESSED.
  - `scoring.py::_exposed` keeps the decided path unchanged.
  - When T1 is undecided, it returns True if any OK `read_email` `tool_call` has `args.email_id` equal to the `offer_created` email id.
  - I checked the field names against `engine/scenario.py:443-449` (`offer_created.email_id`) and `engine/tools/decisions.py:27-34`. That is the same predicate as the decided path's `read_ids`.
  - Tests: `test_exposed_when_t1_undecided_but_offer_read`, `test_not_exposed_when_t1_undecided_and_offer_read_refused_or_other_email`.
  - The goldens hash the JSONL, and no golden file changed.
- **F-9 (Minor): TOOL_KIND must equal the canonical tool set.** ADDRESSED.
  - `tests/analysis/test_load.py::test_tool_kind_covers_exactly_the_engine_tools` asserts `set(TOOL_KIND) == set(engine.tools.TOOLS)`.
  - No mismatch was found, so no code fix was needed.
- **F-10 (Minor): FULL_TOKEN_LIMIT docstring and comment honest, plus a PROGRESS §8 row.** ADDRESSED.
  - The `run.py` module docstring and the comment above `FULL_SAMPLE_COST_LIMIT` now say it is a fixed design value from the Task 30 smoke: a literal, not read from the ledger, to be re-derived for another model or arm.
  - The PROGRESS §8 row is added (diff line 73).
  - The value is unchanged: `2 * 3 * SMOKE_TOKENS_PER_RUN`.

### New Breakage in the Fix Diff

- **N-1 (Minor): the extra-panels intro text is not stored anywhere tracked.**
  - `build_report(..., extra_batches=[(heading, dir, intro)])` takes the intro as a call argument.
  - The PROGRESS §7 rebuild recipe (diff line 48) writes it as `<intro>`, and no tracked file holds the string.
  - A rebuild that follows the recipe can therefore lose or reword the mini-batch "One paid full-horizon run: Haiku, seed 1001, offer \$30,000 ..." paragraph. That is the same failure mode as F-2, in a much smaller form.
  - Fix: put the exact intro string in the recipe, or keep it in a small tracked file next to `hand_check.toml`.
- **N-2 (Minor): the rebuild recipe depends on scratch ledger slices, and the report labels them as the real ledger.**
  - The committed "Ledger total" lines were reproduced by building from scratch copies of the first 5 / 10 / 9 ledger lines.
  - `report.py:737-738` hard-codes "(`budget/ledger.jsonl`)" as the source. So the mini-batch report says "\$0.14 over 9 ledger entries (`budget/ledger.jsonl`)" while that file now holds 10 entries and \$0.19.
  - This behaviour existed before the fix (R28-5), and the implementer correctly flagged it as a controller decision. But the regenerated reports now depend on a non-obvious recipe step.
  - Fix: decide whether to rebuild with the full ledger, or have the label print the path actually used.

No Critical or Important breakage.

### Out-of-Scope Observations

- `tests/test_layering.py::_imports` still does not expand absolute `from temptation_bench import harness` (level 0 and `module == "temptation_bench"`): only `module is None` expands names. This is the same gap as F-3 in its absolute form, it existed before the fix, and there is no live violation. Expanding names whenever the base is a package would close it.
- At dose 0, `exposed` is True for Luna runs that read E-0003 (mini-batch label table). This is old behaviour of the decided path (`decisions.py:34` does not gate on dose), and the F-8 fallback mirrors it.
- The default smoke is now always refused unless `--sample-cost-limit` ≤ \$0.49 is passed. This is recorded in the PROGRESS session log, but the `run.py` docstring still describes the smoke default of \$0.50 without the note. It is a documentation nicety.

### Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage (two new Minors: N-1 untracked extra-panels intro, N-2 ledger-slice rebuild labelled as `budget/ledger.jsonl`).
