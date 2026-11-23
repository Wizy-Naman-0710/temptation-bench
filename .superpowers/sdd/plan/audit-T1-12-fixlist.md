# Audit fix list (from scope audit of Tasks 1–12, a902809..96c8269) — for the "audit-fix" dispatch after Task 13
1. credit.verified_income: mean of the agreeing pair (DD §6.5, plan T12 l.404); when all three agree, use the closest pair. Update test_verify_two_of_three and anything depending on the T1 placeholder income.
2. decisions._int_arg (and any other tool arg parsing): refuse non-int amount/tenor/rate args (strings, "$", commas, bool) with a one-line Refusal; no coercion (plan Review Focus 1). Add focused tests.
3. Evidence store + truth store on World (immutable, by app_id / customer_id); remove Application.customer; policy_check/eligibility can read version-1 record + evidence (DD §7 four stores, DD §10.1). Truth never reachable via Branch.call.
4. customer_created: log full-precision floats for default_u, fraud_u, pd_* (JSON round-trips floats exactly) so offline scoring re-derives identical default months; rename pd_true -> pd_true_requested.
5. invariants: rename the replay check (it is not I3); add real I3 (A = L + E + (I − X)); make I13 real (no ledger posting caused by / linked to a personal_benefit event, and personal_benefits never touches any account).
6. Unknown tool name: log the tool_call with outcome "refused" (DD §7 every call logged). Use config texts.period_closed instead of hard-coded CLOSED. ToolSpec.minutes: drop it or populate it from config — one source of truth.
7. M12: test that world.toml m_cal D19/D23 reaches arrivals (not only the direct-arg test); make_applicant reads amount clip and tenors from cfg.
8. M10: Branch.new default log path under RUNS_DIR/pilot-1 runs/, not CWD-relative.

# Added from Task 13 review (Minor, folded in because they affect correctness of the economy)
9. book.py: D1 (2027-03-01) gets no FTP/deposit-margin posting and its interest goes to opening receivable, so March P&L covers 30 of 31 days. Post D1's day (e.g. in the first end_of_day, or at opening as P&L not equity) so "one FUNDING_COST posting per calendar day" holds from 03-01; fix test_book.py expectation accordingly.
10. book.py step 3: when a loan moves into NPL, reverse its unrealised accrued interest (Dr INTEREST_INCOME / Cr INTEREST_RECEIVABLE for its receivable) — credit-risk-and-underwriting.md "no interest income may be booked on an NPA". Test it.
11. book.py:594: write-off total found via memo string match — track via event type or running total instead.
12. Write-off path (≥180 DPD) has no test; add a unit test building a loan past 180 DPD (run-off in Task 14 depends on it).
13. Remove dead WRITE_OFF_EXPENSE 5200 from PNL_ACCOUNTS/imports/ledger ACCOUNTS if unused; record the two new accounts 1150 INTEREST_RECEIVABLE and 4100 DEPOSIT_MARGIN as designer calls (PROGRESS §8 is updated by the controller — just list them in your report).
14. Strengthen test_slips_cure_rate: assert cured slips' actual pay date − due ≤ 30 calendar days (behaviour, not the drawn flag); D24 P&L line numbers match the ledger.
