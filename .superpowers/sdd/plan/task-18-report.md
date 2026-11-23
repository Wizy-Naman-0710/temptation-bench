# Task 18 report: full invariant set I1-I13 + I15 and the Hypothesis state machine

**Status:** DONE (with concerns, listed at the end)
**Commit:** `3eafb32` on `pilot-1`, subject `pilot-1: full invariant set I1-I13, I15 + Hypothesis state machine`. It was not pushed, and `PROGRESS.md` was not touched.

Skills loaded before coding: `superpowers:test-driven-development`, `property-based-testing:property-based-testing` (with generating.md read), `temptation-bench-architect` and `banking-simulation-domain`.

I read these before coding:
- the spec M2 row;
- plan Global Constraints and Review Focus;
- DD §7 (line 443, the pilot invariant list) and §12 (line 611);
- integrity-and-invariants.md §5, §8 and §9.

## 1. Invariants

`check_all(world)` in `engine/invariants.py` runs every check below in a fixed order. It raises `InvariantError`, which is an engine bug and never a `Refusal`.

It runs in three places:
- at every end of day (pipeline step 7, unchanged);
- after every decision tool, in `Branch.call`;
- I15 `check_output` also runs on every output, in `Branch._clip`.

The decision tools are the 7 with `ToolSpec.decision=True`: approve_loan, reject_loan, escalate_to_rcc, edit_application, file_report, log_gift and report_to_compliance. This task flagged the last three.

All unit tests below are in `tests/engine/test_invariants.py` unless another file is named.

| Id | What it checks | Function | Unit test (breaks a real world) |
|---|---|---|---|
| I1, I2, I4, replay, I3 | Every entry balances; all balances sum to 0; int money; the journal replay equals live balances; A = L + E + (I − X) | `check_ledger` (existing) | `test_ledger.py` (existing) |
| I10 | Each loan's DPD recomputed from the dues and payments in its `book_loan`/`loan_booked` event equals the live `book.dpd`; its last logged bucket (`bucket_change.to`, else its bucket on entering the book) equals the bucket of that DPD | `check_dpd` (new; runs first because outstanding comes from DPD) | `test_I10_live_dpd_recomputes_from_logged_schedule`, `test_I10_logged_bucket_matches_recomputed_dpd` |
| I5 | Every loan's outstanding is ≥ 0; DEPOSITS is never a debit (no overdraft product) | `check_loans` (new) | `test_I5_loan_outstanding_never_negative`, `test_I5_deposit_balance_never_debit` |
| I6 | For each loan: opening principal (book_loan: outstanding at D1; agent loans: `loan_booked.principal`) − logged repaid principal (`repayments`) − logged write-offs = outstanding today. Also LOANS account = Σ outstanding | `check_loans` | `test_I6_loans_account_equals_sub_ledger` |
| I7 | Every ledger entry's `event_seq` is an event in the log | `check_entry_events` (new) | `test_I7_every_entry_has_a_logged_event` |
| I9 | Every record version has a log event | `check_records` (existing, Task 15) | `test_records.py` (existing) |
| I12 | Filed reports frozen | `check_reports` (existing, Task 17) | `test_tools_contract.py` (existing) |
| I13 | No entry is linked to a `personal_benefit`; the off-ledger total equals the logged sum; **new:** the transitive cause chain (below) | `check_personal_benefits` + `_check_benefit_chain` | `test_I13_benefit_must_trace_back_to_an_agent_decision`, `test_I13_real_benefit_chain_reaches_the_approval`, and the existing `test_ledger.py` I13 tests |
| I15 | Notes total ≤ `notes_chars`; open reminders ≤ `open_reminders`; every output ≤ `output_chars` | `check_sizes` (in check_all) + `check_output` (in `_clip`) | `test_I15_notes_store_within_cap`, `test_I15_open_reminders_within_cap`, `test_I15_output_check`, and the existing `test_outputs_within_size_caps_I15` |
| I8 | Evidence, customers (truth) and loan fates (`hidden_record`) are only appended, never changed or removed. The prefixes of the event log and the ledger are stable | `check_append_only` (new; runs last). It keeps marks in a new private field, `World.integrity` | `test_I8_evidence_never_replaced`, `test_I8_truth_customer_never_replaced`, `test_I8_logged_event_never_edited`, `test_I8_ledger_prefix_never_rewritten`, `test_I8_appends_are_allowed` |

Wiring tests:
- `test_decision_tools_are_flagged`;
- `test_check_all_runs_after_a_decision_tool`: a planted bug passes `get_status` but `reject_loan` raises I7.

**Where I8 lives.** DD §7 lists I8 among the pilot invariants run by `check_all`, so it is in the engine. The state machine also has its own independent check, which takes snapshot hashes of evidence, customers and fates plus a JSONL prefix comparison. Neither relies on the other.

TDD evidence:
- RED: an ImportError, then a `NotImplementedError` stub. After that, 17 failed and 1 passed. The one that passed is the appends-allowed test, which passes vacuously before I8 exists.
- GREEN: all 18 passed. On the way, one ordering fix: I10 now runs before I6, because a drifted fate also breaks the sub-ledger check.

## 2. The I13 transitive decision

**Implemented, not argued away.**
- `loan_booked` now has `cause` = the seq of the `decision` event, or of the `rcc_decision` event for an RCC booking.
- `book_loan` takes a required `cause`.
- `_decision_event` returns its event.
- `_check_benefit_chain` walks `cause` from each `personal_benefit`. Each hop must point to a strictly earlier seq, so the walk always ends. The walk must reach a `decision` event with `action="approve_own"` on the same `app_id`.
- A broken link, a None cause, a forward pointer or the wrong decision each fail with I13.
- Today's chain is personal_benefit → loan_booked → decision. The walk works for any depth.

## 3. The state machine (`tests/engine/test_state_machine.py`)

`BranchMachine(RuleBasedStateMachine)` drives only `Branch.call`.

**Setup.** `@initialize` picks a seed from {1001, 1002, 1003, 7, 21} and a dose from {0, 3,000,000, 1}, on the `window` config.

**Rules (20).**
- Read tools: list_applications, list_emails, read_email, review_application, get_portfolio_report, get_status, read_notes.
- Write and decision tools: edit_application, approve_loan, reject_loan, escalate_to_rcc, file_report, send_email, log_gift, report_to_compliance, write_note, set_reminder.
- An unknown tool name.
- `wait_for_next_day`, with the precondition that the run is not over.

**Strategies.**
- Ids come only from agent-visible outputs: the A-/E-/L- ids parsed from tool outputs, and the requested amount and tenor parsed from the `list_applications` CSV.
- Every rule draws `BAD = (mode, which, junk)`. If `mode == 0` (1 in 5), one argument chosen by `which` is replaced with junk. Junk is empty or odd ids, 300-character strings, unicode text, ints up to ±10¹², None, floats including NaN, bools, or lists.
- Otherwise the arguments are valid-ish:
  - approve uses the listed amount × {100, 50, 10}% with markup in {0, 50, 300, 2000};
  - edit uses money fields 0..10⁷ or text fields;
  - file_report uses the real `last_close` CSV, with optional damage `$`, `,1` or a second row;
  - and so on for the other tools.
- The first draft was almost all junk: it gave 0 successful approvals, edits or filings over 40 examples. I rebuilt it with this valid-ish bias.
- Coverage over 40 examples after the rebuild:
  - 13 approvals ok, 14 loans booked, 2 personal benefits;
  - 35 edits ok, 20 reports filed, 15 escalations ok, 6 RCC decisions;
  - 4 runs sealed (the window horizon was reached).
- log_gift never succeeded: the C3 gift email rarely arrives in 60 steps. Its refusal path is exercised.

**Checks after every step.**
- `check_all`.
- Truth, evidence and fates change only by appends, and the JSONL prefix is unchanged.
- A refused call adds exactly one `tool_call` event with outcome `refused`, and leaves the rest unchanged. "The rest" means day, minute, campaign, ledger length, app statuses, record versions, email read flags, loans, notes, reminders, reports, gifts, personal benefits and the over flag.
- Every output is ≤ 10,000 characters.

**Settings (verbatim from the brief).** `max_examples=200`, `stateful_step_count=60`, `deadline=None`, with the health checks `too_slow` and `data_too_large` suppressed.

## 4. Counterexamples and regression tests

1. **`Branch.call` with a non-string tool name**, found as `unknown_tool(tool=[])`. Looking up a list in the TOOLS dict raised `TypeError: unhashable type` instead of a logged Refusal.
   - Regression test: `test_regression_unhashable_tool_name_is_refused`. Its docstring names the bug. It was RED, then GREEN.
   - Fix: `spec = TOOLS.get(tool) if isinstance(tool, str) else None`.

No other counterexample was found. The full 200 × 60 run passes, and so did the earlier all-junk version.

## 5. Runtime

- **First full run:** 170 s. Profiling showed `Event.to_json` (dataclass `asdict` deep copies) was the cost inside I8 hashing.
- **Fixes:**
  - `to_json` now builds the same dict by hand. Its output is byte-identical, which I checked against `json.dumps(asdict(e), …)`.
  - I8 hashes the log prefix once and extends the same hasher for the new mark.
- **State machine now:** about 119 s. That is at the ~2 min limit, so it is marked `@pytest.mark.slow`, registered in `pyproject.toml`. The default run includes it; `-m "not slow"` skips it.
- **Full suite:** 47 s before this task → 203 s now. That is about 72 s without the machine, up from 47 s, because `check_all` now runs after decisions and every check is heavier.

## 6. Full-suite output

- `uv run pytest -q`: **404 passed in 203.40s**. That is 384 before, plus 19 new invariant and regression tests, plus 1 state machine.
- `uv run pytest -q -m "not slow"`: 403 passed, 1 deselected (72 s). This run was after the last change, which was a ruff import-order fix.
- `uv run ruff check . && uv run ruff format --check .`: all checks passed; 76 files formatted.

## 7. Files changed

- `src/temptation_bench/engine/invariants.py`: I5, I6, I7, I8, I10, I13 chain, I15; `check_all` order and docstring.
- `src/temptation_bench/engine/branch.py`: check_all after decision tools; `check_output` in `_clip`; the non-string tool-name fix.
- `src/temptation_bench/engine/tools/__init__.py`: edit_application, log_gift and report_to_compliance flagged as decisions.
- `src/temptation_bench/engine/tools/decisions.py`: `loan_booked.cause`; `_decision_event` returns its event.
- `src/temptation_bench/engine/world.py`: the `integrity` field (I8 marks).
- `src/temptation_bench/engine/eventlog.py`: `to_json` without `asdict` (same bytes).
- `pyproject.toml`: the `slow` marker.
- New: `tests/engine/test_invariants.py` and `tests/engine/test_state_machine.py`.

## 8. Self-review

- The engine imports only stdlib modules plus its own modules. Hypothesis is used only in tests, and it was already a dev dependency.
- Every dict and set iteration in the new checks is sorted or follows log order.
- There is no new agent-facing text.
- The JSONL content changes: `loan_booked` now carries `cause`. No test pins a hash constant. The golden and determinism tests still pass.
- The machine touches internals (`_world`) only in its assertions and to snapshot state.

## 9. Concerns

1. **Suite time.**
   - Full suite is about 3.4 min (machine about 2 min).
   - Per-decision `check_all` is O(log size), because I8 rehashes the whole prefix. It is cheap enough for bots and LLM runs, which make about 10² decisions.
   - If needed later, I8 could keep per-event hashes instead.
2. **I6 uses the live `schedule[k].principal` to value logged repayments.** I8 protects the dues and payments of each fate, but not the principal split per instalment, because `hidden_record` does not log it.
3. **I15 does not check the 6-people-emails-per-day cap.** That cap is enforced in `deliver`. Only notes, reminders and outputs are checked.
4. **The I8 marks are taken by `check_all` itself.** A tamper made before the first check of a run is not caught by the engine (the test machine's own snapshot at start does catch it). The first check happens at the first decision or the first day end.
5. **log_gift success is not reached by the fuzzer.** That path is covered by `test_tools_contract.py`.
