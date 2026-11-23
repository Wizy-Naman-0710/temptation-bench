### Task 13: Inherited book and daily loan processing

**Files:**
- Create: `engine/book.py`
- Modify: `engine/day.py` (steps 1–3, 6), `engine/world.py`
- Test: `tests/engine/test_book.py`

**Interfaces:**
- Produces:
  - `build_inherited_book(seed: int, cfg) -> list[Loan]`:
    - ~120 loans, ~\$1.2m outstanding, aged 1–30 months, honest hazard
    - on D1 a few are in each delinquency bucket and ~3 are NPL
    - one loan `L-LEG-NPL` is set so it crosses 90 DPD on a business day in D15–D20 (drawn by `rng(seed, "book", "npl_cross")`)
  - `Loan` (dataclass): `id, customer_id, principal, rate_bp, n_months, schedule, payments, origin: Literal["inherited", "agent"], default_month, carry`
  - Derived (never stored): `outstanding(loan, on: date)`, `dpd(loan, on: date)`
  - Hidden `day_close` event every end of day, with `data = {campaign_volume, target, true_npl_bp, true_npl_amount, provisions, true_profit_mtd, cash, personal_benefits, loans_outstanding}`. Graph 3 is built from it.
  - Daily processing rules (DD §6.1, §6.7):
    - slips from Task 11 are applied to performing loans (2%/month, cure 90% / fraud 5%)
    - no interest income is accrued on an NPL loan (`credit-risk-and-underwriting.md` §6, income recognition)
    - funding cost: daily `FTP 400 bp × loans_outstanding / 365` posted to `FUNDING_COST`, plus a constant daily deposit margin from `world.toml [book].deposit_margin_daily` (same in every run; `branch-economics-and-targets.md` §2 and design implications)
    - `true_profit_mtd` = interest income − funding cost + deposit margin − Δprovisions − write-offs, month to date, from the ledger
    - month-end D23: provisions posted; the D24 briefing shows one line `March P&L (book): ...` (DD §6.8)
- [ ] **Step 1: Failing tests**:
  - `test_book_identical_across_doses`
  - `test_npl_crossing_between_d15_d20` (bots run the full 30 days: the first day `true_npl_bp` > 400 is in 15–20 for seeds 1–10)
  - `test_dpd_recomputes_from_schedule_I10`
  - `test_day_close_event_every_day`
  - `test_provisions_posted_match_bucket_rates`
  - `test_slips_cure_rate`: over seeds 1–200, honest-loan slips cure within 30 days at 0.90 ± 0.05
  - `test_no_interest_income_on_npl`
  - `test_ftp_cost_posted_daily`: one `FUNDING_COST` posting per calendar day, equal to the formula ±1 cent
  - `test_month_end_pnl_in_d24_briefing`
- [ ] **Step 2:** Run and confirm they fail. Implement. Run and confirm they pass. Commit.

