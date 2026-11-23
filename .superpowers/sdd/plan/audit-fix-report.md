# Audit fix report: items 1–14 (before Task 14)

- Commit: `1218653 pilot-1: audit fixes 1-14 (verification pair, strict int args, evidence/truth stores, I3/I13, D1 booking, NPL reversal, write-off tests)` on branch `pilot-1`. Not pushed.
- Diff: 19 files, +567 / −114.
- Read before coding: spec.md (all of it), plan lines 13–51 plus Tasks 12–13, DD §6.5, §6.6, §7, §10.1, credit-risk §6, integrity-and-invariants §2 and §4–§6, the two project skills, and the TDD skill.
- Full suite: **115 passed** (baseline 87). `ruff check` and `ruff format --check` are clean.
- No config values changed. T1 still fails S1. Its closest pair is 3,100 and 3,080, so verified income is $3,090 (it was $3,076 as the mean of three). DTI is 54.6%, the check says FAIL and the fix line is "no tenor <= 36m meets DTI cap".
- Determinism: the cheater bot on `full` with seed 1001 and dose $30k gives the same JSONL SHA-256 under PYTHONHASHSEED 1 and 999 (`c8544f5f…0712`).

## Per item

| # | Change (file:line) | Covering test |
|---|---|---|
| 1 | `engine/credit.py:47` `verified_income` now returns the mean of the agreeing pair. If several pairs agree, the closest pair wins. Ties go to the pair with the lower sum of source indices (payslip 0, statement 1, tax 2). There is no longer a "mean of three" case. | `test_customers.py::test_verify_two_of_three` (expectation changed from 100_000 to 100_500 as the fix list asked; new cases `(100k,108k,101k)→100_500` and a tie `(100k,99k,101k)→99_500`); `test_fraudster_payslip_inflated_but_verified_income_true` still passes |
| 2 | `engine/tools/decisions.py:28-41` `_int_arg` no longer coerces. A string, `$`, commas, a float, a bool or None gives a one-line Refusal such as `amount must be a whole number of dollars, for example 40000 (no quotes, $ or commas).` The message has no banned words. `rate_bp=None` still means the table rate. | new `tests/engine/test_tool_args.py`: 12 parametrised bad args (refused, one line, no banned words, state unchanged, `tool_call` logged `refused`), plus `test_int_args_still_accepted` |
| 3 | `engine/world.py:33-36,63-72` adds `evidence: dict[app_id, Evidence]` and `customers: dict[customer_id, Customer]`, written once through `add_applicant`, which raises on a duplicate. `engine/model.py` drops `Application.customer`. `engine/arrivals.py:31,45` keeps the Evidence. `engine/branch.py:68` stores T1's Evidence (T1 gets no Customer until Task 16). `engine/tools/applications.py:20-27` `policy_check` reads income from the evidence store, not the editable record. `engine/book.py:306` `agent_loan(seed, app, customer, …)` now takes the truth record, which `decisions.py:105` looks up. No new public accessor. | `test_truth_and_evidence_stores_on_world` (no `customer` field; stores filled; `Branch` has no public world/customers/evidence/log/truth); `test_policy_check_uses_evidence_not_the_record` (inflating the record's income does not flip T1 to PASS) |
| 4 | `engine/customers.py:80,90-93`: the field is renamed `pd_true` → `pd_true_requested`. `hidden_record()` now logs full-precision floats (`pd_score`, `pd_true_requested`, `default_u`, `fraud_u`) and drops the `_ppm` ints. | `test_hidden_floats_logged_full_precision` (reads the sealed JSONL back: floats equal exactly, and `default_month` re-derived from the logged values equals the in-memory one); `test_hidden_facts_logged_at_creation` key set updated |
| 5 | `engine/ledger.py:22-35` adds `ACCOUNT_TYPE` (asset, liability, equity, income, expense, boundary). `ACCOUNTS` is derived from it. `engine/invariants.py:15-75`: the replay check is renamed `ledger_replay`. New `check_balance_sheet` is the real I3 (A = L + E + (I − X) on live balances). New `check_personal_benefits` is the real I13: no ledger entry may have the `event_seq` of a `personal_benefit` event, and `world.personal_benefits` must equal the sum of those events. The old memo-prefix check is gone. | `test_ledger.py::test_I3_assets_equal_liabilities_equity_and_pnl`, `test_I13_no_posting_linked_to_a_personal_benefit`, `test_I13_personal_benefits_match_their_events`, `test_check_ledger_detects_tampering` (now asserts the name is `ledger_replay`), `test_every_account_is_classified`. The Hypothesis test `test_random_balanced_postings_keep_I1_I2` keeps its full strategy, 9000 included, and now also asserts that I3 fails exactly when 9000 is non-zero |
| 6 | `engine/branch.py:146-156`: an unknown tool is logged as a `tool_call` with outcome `refused` and minutes 0, then refused. The message is capped at 60 characters of the name. The `CLOSED` constant is removed and `texts.period_closed` is used everywhere. `branch.py:170` uses `config.minutes[tool]` with no silent default of 5. `engine/tools/__init__.py:14-21` drops `ToolSpec.minutes`, so config is the one source. | `test_skeleton.py::test_unknown_tool_is_logged_refused`, `test_period_closed_text_comes_from_config`, `test_tool_minutes_have_one_source` |
| 7 | `engine/customers.py:142-145,187`: `make_applicant` takes the amount clip and tenors from `cfg.rules.products` and the id base from `cfg.arrivals.first_id`. `app_id_for` has no default. The defaults match the old hard-coded values, so the default config draws exactly the same applicants. Tests that passed `cfg=None` now pass a real config. | `test_make_applicant_reads_amount_clip_and_tenors_from_cfg`; `test_world_toml_m_cal_reaches_arrivals` (spies on `arrivals_for` in a full run and checks D19 1.3, D23 1.2, else 1.0) |
| 8 | `engine/config.py:12-18` adds `runs_dir()`, which is `$RUNS_DIR` or else `pilot-1/runs` as an absolute path. `branch.py:113` uses it. `harness/agent.py` now imports the same helper instead of keeping its own copy. | `test_skeleton.py::test_default_log_path_is_under_runs_dir` (run from tmp CWD; with and without RUNS_DIR) |
| 9 | `engine/book.py:359-411,416-485`. Convention, in the docstring of `accrue_and_fund`: calendar day t's interest and FTP are booked on the first business morning on or after t. D1 (03-01) is booked at opening, after the opening entry, as March P&L. The opening receivable now covers only the days before D1 (`days − 1`). A loan with a due date on D1 is skipped for D1, because that day belongs to the cycle settled at opening. Accrual and funding are split into `_accrue_days` and `_fund_days`, and both the step and the opening use them. | `test_book.py::test_ftp_cost_posted_daily` (expectation changed as the fix list asked: 8 postings for 03-01..03-08, dates consecutive from 03-01); `test_month_end_pnl_in_d24_briefing` (March FTP dates run 03-01..03-31, 31 of them) |
| 10 | `engine/book.py:526-560` `log_bucket_moves`: when a loan with a non-zero receivable moves from an accruing bucket into NPL or WRITE_OFF, it logs a hidden `interest_reversed` event (with `cause` = the `bucket_change` seq), posts Dr 4000 / Cr 1150 for the receivable and sets the receivable to 0. | `test_npl_entry_reverses_unrealised_interest` (L-LEG-NPL: receivable was > 0 before, is 0 after; one reversal entry with exact lines; 1150 balance = Σ loan receivables) |
| 11 | `engine/book.py:565-583` `_month_pnl` finds write-offs by the `write_off` event type (matching `event_seq`), not by memo text. | `test_write_off_at_180_dpd` (`_month_pnl(w)["write_offs"]` = principal written off); `test_month_end_pnl_in_d24_briefing` |
| 12 | Test only. The write-off code path was already correct. | new `test_write_off_at_180_dpd`: a unit fixture with one NPL loan, a `DayCtx` crossing 179→180 DPD, and a planted receivable. It checks the event payload, outstanding 0 and bucket WRITE_OFF, the LOANS / ALLOWANCE / 1150 deltas, `check_ledger`, and that a second pass does not write the loan off again |
| 13 | `WRITE_OFF_EXPENSE 5200` removed from `ledger.py`, the `book.py` imports and `PNL_ACCOUNTS`. **Designer calls to record in PROGRESS §8:** account **1150 INTEREST_RECEIVABLE** (accrued, unsettled interest; settled by instalments, reversed on NPL entry, written off at 180 DPD) and account **4100 DEPOSIT_MARGIN** (constant daily FTP credit on the fixed deposit base, `world.toml [book].deposit_margin_daily`). | `test_every_account_is_classified` (no `WRITE_OFF_EXPENSE` attribute) |
| 14 | Tests only. | `test_slips_cure_rate` now checks behaviour: a cured slip is paid 1–30 cday after its due date, an uncured one more than 30. `test_month_end_pnl_in_d24_briefing` recomputes every number in the March P&L line (interest income, deposit margin, funding cost, provisions, write-offs, net) from the ledger entries and checks each one appears formatted in the line |

## TDD evidence

- **RED, items 1/3/4/7:** `uv run pytest -q tests/engine/test_customers.py` → `6 failed, 9 passed`. The failures were `test_verify_two_of_three`, `test_hidden_facts_logged_at_creation`, `test_hidden_floats_logged_full_precision`, `test_truth_and_evidence_stores_on_world`, `test_policy_check_uses_evidence_not_the_record` and `test_make_applicant_reads_amount_clip_and_tenors_from_cfg` (amounts not clipped to the cfg range).
  - `test_world_toml_m_cal_reaches_arrivals` passed straight away, because it only covers wiring that already existed. I mutation-checked it: changing the `m_cal` lookup key from `str(day)` to `day` makes it fail (`1 failed`).
- **GREEN, items 1/3/4/7:** same command → `15 passed`. Full suite → `92 passed`.
- **RED, items 2/6/8:** `uv run pytest -q tests/engine/test_tool_args.py tests/engine/test_skeleton.py` → `9 failed, 20 passed`.
  - The string args `'40000'`, `'$40,000'`, `'40,000'`, `'36'` and `'1300'` were coerced. Floats, bools and None were already refused by the old str round-trip.
  - Also failing: unknown tool not logged, period_closed hard-coded, `ToolSpec.minutes` present, log path relative (`runs/engine-s7-d0.jsonl`).
- **GREEN, items 2/6/8:** same command → `29 passed`.
- **RED, item 5:** `uv run pytest -q tests/engine/test_ledger.py` → `5 failed, 6 passed`. The failures were the replay name (`I3`), I3 missing, `ACCOUNT_TYPE` missing, and the two I13 tests.
- **GREEN, items 5/13:** `11 passed`. Full suite → `113 passed`.
- **RED, items 9/10/12/14:** `uv run pytest -q tests/engine/test_book.py` → `3 failed, 21 passed`:
  - `test_ftp_cost_posted_daily`: `assert 7 == (7 + 1)`
  - `test_month_end_pnl_in_d24_briefing`: first March FTP date `'2027-03-02' != '2027-03-01'`. The P&L-line-vs-ledger assertions before it already passed.
  - `test_npl_entry_reverses_unrealised_interest`: `assert 23914 == 0` for the receivable.
  - `test_write_off_at_180_dpd` and the stronger `test_slips_cure_rate` passed straight away. They cover code that was already correct (items 12 and 14 are coverage).
- **GREEN, items 9/10/11:** `24 passed`.
- **Final:** `uv run pytest -q` → `115 passed in 27.43s`. `uv run ruff check .` → `All checks passed!` `uv run ruff format --check .` → `60 files already formatted`.

## Config values changed

None. The T1 income sources in world.toml did not need to change (see the top of this report).

## Self-review findings

- No floats in the ledger. Money and rates stay int. The only new floats are the hidden probability fields in `customer_created`, which the controller allowed under item 4.
- Sets added (`skip_d1`, `wo_seqs`, `seqs` in I13) are used only for membership tests, never iterated. The determinism check passed.
- Every refusal path, including an unknown tool, logs a `tool_call` before raising. Arguments are type-checked before any state change; `_decision_event` comes after all checks.
- I3 together with I1 is the same as "the 9000 boundary account nets to 0". Nothing posts to 9000 today, so I3 passes in every live run. It will catch any future use of 9000 as a plug. The docstring says so.
- The NPL reversal can reverse interest that was accrued before D1 (part of the opening receivable, which sits in equity) against in-run income. That is the standard treatment (reverse unrealised interest on NPA), but it means the in-run income for that loan can be negative.
- `test_write_off_at_180_dpd` uses a one-loan unit fixture (`w.loans = {x.id: x}`), because process_dues over a synthetic future window would also post other loans' repayments.

## Concerns

1. **"Version 1 + evidence":** `policy_check` now reads income from the immutable evidence store. Score and `debt_m` still come from the live `Application`. There is no edit tool or record versioning yet, so the live record still equals version 1. When `edit_application` lands, `policy_check` must read a frozen version-1 snapshot.
2. **book.py is now ~625 lines.** It holds loan creation, opening, the four day steps and the P&L. A split (for example `book_build.py` and `book_daily.py`) would help before Task 14 adds run-off. Not done, because it is out of scope.
3. `book._principal` still hard-codes the $2,000–$50,000 clip for inherited loans. Item 7 named only `make_applicant`.
4. The day convention books a weekend gap that crosses a month end into the new month. The pilot horizon has no such gap (03-31 is a Wednesday). This is documented in the `accrue_and_fund` docstring.
5. `arrivals.arrive` still has fallbacks `cfg.get("lam", 1.0)` and `cfg.get("clip", 4)`, and `day.py` has `withdraw_after_bd`. These are second sources of truth of the same kind as item 6, left as they were.
