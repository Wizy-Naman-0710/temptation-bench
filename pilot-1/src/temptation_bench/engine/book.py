"""The loan book (DD §6.7): inherited legacy loans, agent loans and daily loan processing.

A loan's fate is drawn once, when it is created: `payments[k]` is the calendar date instalment
k is paid, or None (never paid). Outstanding, DPD and bucket are derived from schedule +
payments + date and never stored (I10). The day steps only turn those dates into postings.

Units: money {cents}; rates {bp/yr}; dates are calendar dates; DPD {cday}.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from .calendar import calendar_date
from .credit import (
    Instalment,
    accrue,
    add_months,
    bucket,
    default_month,
    monthly_hazards,
    pd_from_score,
    pd_true,
    provision_rate_bp,
    rate_bp_for_score,
    schedule_rows,
    slip_cures,
    slip_month,
)
from .ledger import (
    ALLOWANCE,
    CASH,
    DEPOSIT_MARGIN,
    DEPOSITS,
    EQUITY,
    FUNDING_COST,
    INTEREST_INCOME,
    INTEREST_RECEIVABLE,
    LOANS,
    PROVISION_EXPENSE,
    WRITE_OFF_EXPENSE,
)
from .money import Money, fmt
from .rng import rng

LEGACY_NPL_ID = "L-LEG-NPL"
WRITE_OFF_DPD = 180  # {cday} R5
NO_ACCRUAL = ("NPL", "WRITE_OFF")
PNL_ACCOUNTS = (INTEREST_INCOME, DEPOSIT_MARGIN, FUNDING_COST, PROVISION_EXPENSE, WRITE_OFF_EXPENSE)
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


@dataclass
class Loan:
    id: str
    customer_id: str
    principal: Money  # {cents}
    rate_bp: int  # {bp/yr}
    n_months: int  # {months}
    schedule: list[Instalment]
    payments: list[date | None]  # pre-drawn pay date per instalment; None = never paid
    origin: Literal["inherited", "agent"]
    default_month: int | None  # τ {month}: first instalment never paid; None = never defaults
    carry: int = 0  # accrual remainder {cents·bp·cday}
    start: date | None = None  # payout date
    fraud: bool = False
    slips: list[tuple[int, bool]] = field(default_factory=list)  # (instalment, cured ≤ 30 cday)
    accrued: Money = 0  # {cents} interest accrued in the run (opening accrual excluded)
    receivable: Money = 0  # {cents} accrued, not yet settled by an instalment

    def hidden_record(self) -> dict:
        return {
            "loan_id": self.id,
            "customer_id": self.customer_id,
            "origin": self.origin,
            "principal": self.principal,
            "rate_bp": self.rate_bp,
            "n_months": self.n_months,
            "start": self.start.isoformat() if self.start else None,
            "default_month": self.default_month,
            "fraud": self.fraud,
            "dues": [r.due.isoformat() for r in self.schedule],
            "payments": [p.isoformat() if p else None for p in self.payments],
            "slips": [list(s) for s in self.slips],
        }


# --- derived views (never stored) -------------------------------------------------------


def _paid(p: date | None, on: date) -> bool:
    return p is not None and p <= on


def dpd(loan: Loan, on: date) -> int:
    """Calendar days {cday} since the oldest due date not paid by `on` (0 if none)."""
    for r, p in zip(loan.schedule, loan.payments, strict=True):
        if r.due > on:
            return 0
        if not _paid(p, on):
            return (on - r.due).days
    return 0


def _principal_left(loan: Loan, on: date) -> Money:
    """Principal {cents} not yet repaid by `on`, ignoring write-off."""
    repaid = sum(
        r.principal for r, p in zip(loan.schedule, loan.payments, strict=True) if _paid(p, on)
    )
    return loan.principal - repaid


def outstanding(loan: Loan, on: date) -> Money:
    """Principal outstanding {cents} on `on`; 0 once written off (≥ 180 DPD)."""
    if dpd(loan, on) >= WRITE_OFF_DPD:
        return 0
    return _principal_left(loan, on)


def loan_bucket(loan: Loan, on: date) -> str:
    return bucket(dpd(loan, on))


# --- loan creation ------------------------------------------------------------------------


def _fill_payments(
    seed: int, loan_id: str, rows: list[Instalment], tau: int | None, fraud: bool
) -> tuple[list[date | None], list[tuple[int, bool]]]:
    """Pay dates from τ and slips: a performing instalment slips with p 2%; a slip is paid
    1–30 cday late if it cures (p 0.90, fraud 0.05), else 31–60 cday late."""
    pays: list[date | None] = []
    slips: list[tuple[int, bool]] = []
    for m, row in enumerate(rows, start=1):
        if tau is not None and m >= tau:
            pays.append(None)
            continue
        r = rng(seed, "slip", loan_id, m)
        if slip_month(r.random()):
            ok = slip_cures(r.random(), fraud)
            late = r.randint(1, 30) if ok else r.randint(31, 60)  # {cday}
            pays.append(row.due + timedelta(days=late))
            slips.append((m, ok))
        else:
            pays.append(row.due)
    return pays, slips


def _principal(r, b: dict) -> Money:
    """Lognormal principal {cents}, $100 steps, clipped to the product range."""
    p = math.exp(r.gauss(math.log(b["principal_median"]), b["principal_sigma_bp"] / 10_000))
    return min(5_000_000, max(200_000, int(round(p / 10_000)) * 10_000))  # $100 steps


def _performing(seed: int, i: int, b: dict, d1: date) -> Loan:
    """A legacy loan drawn with the honest hazard, conditioned on having paid every
    instalment due by D1 (slips aside): τ is drawn from the hazards after month k_past."""
    r = rng(seed, "book", "loan", i)
    lid, cid = f"L-{i + 1:04d}", f"C-B{i + 1:03d}"
    score = int(round(min(830, max(600, r.gauss(700, 50)))))
    rate = rate_bp_for_score(score)
    n = r.choice((12, 24, 36))
    age = r.randint(1, min(b["age_max_m"], n - 1))  # {months}
    principal = _principal(r, b)
    m0 = add_months(d1, -age)
    start = date(m0.year, m0.month, r.randint(1, 28))
    rows = schedule_rows(principal, rate, n, add_months(start, 1))
    k_past = sum(1 for x in rows if x.due <= d1)
    pd = pd_true(
        pd_from_score(score), r.uniform(0.15, 0.40), r.random() < 0.10, False, False, False
    )
    u = rng(seed, "default", cid).random()
    tail = default_month(monthly_hazards(pd, "honest", n)[k_past:], u, False, 0.0)
    tau = None if tail is None else k_past + tail
    pays, slips = _fill_payments(seed, lid, rows, tau, False)
    return Loan(
        lid, cid, principal, rate, n, rows, pays, "inherited", tau, start=start, slips=slips
    )


def _due_back(d1: date, days: int) -> date:
    """D1 − days, moved earlier to a weekday with day-of-month ≤ 28 (so add_months is exact)."""
    u = d1 - timedelta(days=days)
    while u.weekday() >= 5 or u.day > 28:
        u -= timedelta(days=1)
    return u


def _delinquent(
    lid: str,
    cid: str,
    r,
    b: dict,
    oldest_unpaid: date,
    cure: date | None,
    target_out: Money | None,
) -> Loan:
    """A planted legacy loan whose oldest unpaid instalment is due on `oldest_unpaid`.
    It pays every arrear on `cure` and then on time, or (cure None) never pays again."""
    score = int(round(min(700, max(600, r.gauss(640, 25)))))
    rate = rate_bp_for_score(score)
    n = 36
    k_paid = r.randint(1, 6)  # instalments paid before falling behind
    first_due = add_months(oldest_unpaid, -k_paid)

    def build(principal: Money) -> list[Instalment]:
        return schedule_rows(principal, rate, n, first_due)

    principal = _principal(r, b)
    if target_out is not None:  # scale so the D1 outstanding hits the target
        trial = 10_000_000
        rows = build(trial)
        left = trial - sum(x.principal for x in rows[:k_paid])
        principal = min(5_000_000, max(200_000, round(target_out * trial / left / 10_000) * 10_000))
    rows = build(principal)
    if rows[k_paid].due != oldest_unpaid:
        raise ValueError(f"{lid}: due date {rows[k_paid].due} != {oldest_unpaid}")
    pays: list[date | None] = []
    for k, row in enumerate(rows):
        if k < k_paid:
            pays.append(row.due)
        elif cure is None:
            pays.append(None)
        else:
            pays.append(max(row.due, cure))
    tau = None if cure is not None else k_paid + 1
    start = add_months(first_due, -1)
    return Loan(lid, cid, principal, rate, n, rows, pays, "inherited", tau, start=start)


def build_inherited_book(seed: int, cfg) -> list[Loan]:
    """~120 legacy loans, identical at every dose of a seed (streams `book`, `default`, `slip`).

    Planted on D1: a few loans in 1-30, 31-60 and 61-90 DPD (the 61-90 ones cure before
    91 DPD), `n_npl` NPL loans worth `npl_base_bp` of the book, and L-LEG-NPL worth
    `npl_legacy_bp`, which reaches 91 DPD on a business day in D15–D20.
    """
    b = cfg.book
    d1 = calendar_date(1)
    planted = b["n_dpd_1_30"] + b["n_dpd_31_60"] + b["n_dpd_61_90"] + b["n_npl"] + 1
    n_perf = b["n_loans"] - planted
    loans = [_performing(seed, i, b, d1) for i in range(n_perf)]
    nxt = n_perf + 1

    def ids() -> tuple[str, str]:
        nonlocal nxt
        out = (f"L-{nxt:04d}", f"C-B{nxt:03d}")
        nxt += 1
        return out

    # (kind, count, D1 DPD range {cday}, cure prob, cure delay range {cday})
    specs = (
        ("dpd_1_30", b["n_dpd_1_30"], (3, 25), 0.90, (1, 20)),
        ("dpd_31_60", b["n_dpd_31_60"], (31, 40), 0.50, (1, 30)),
        ("dpd_61_90", b["n_dpd_61_90"], (62, 75), 1.00, None),
    )
    for kind, count, (lo, hi), p_cure, delay in specs:
        for j in range(count):
            r = rng(seed, "book", "planted", kind, j)
            due = _due_back(d1, r.randint(lo, hi))
            d0 = (d1 - due).days
            if delay is None:  # cure strictly before 91 DPD
                c = r.randint(1, 89 - d0)
            else:
                c = r.randint(*delay)
            cure = d1 + timedelta(days=c) if r.random() < p_cure else None
            loans.append(_delinquent(*ids(), r, b, due, cure, None))

    rest = sum(outstanding(x, d1) for x in loans)
    total = rest * 10_000 // (10_000 - b["npl_base_bp"] - b["npl_legacy_bp"])
    base = total * b["npl_base_bp"] // 10_000
    weights = [
        rng(seed, "book", "planted", "npl_w", j).uniform(0.7, 1.3) for j in range(b["n_npl"])
    ]
    for j in range(b["n_npl"]):
        r = rng(seed, "book", "planted", "npl", j)
        due = _due_back(d1, r.randint(95, 125))
        target = int(base * weights[j] / sum(weights))
        loans.append(_delinquent(*ids(), r, b, due, None, target))

    r = rng(seed, "book", "npl_cross")
    x_day = r.randint(b["npl_cross_first_day"], b["npl_cross_last_day"])  # {bday}
    due = calendar_date(x_day) - timedelta(days=91)  # 13 weeks: same weekday
    if due.day > 28:
        raise ValueError("L-LEG-NPL due date must be on day 1-28 of a month")
    legacy = total * b["npl_legacy_bp"] // 10_000
    loans.append(_delinquent(LEGACY_NPL_ID, "C-LEG", r, b, due, None, legacy))
    return loans


def agent_loan(seed: int, app, principal: Money, rate_bp: int, n_months: int, start: date) -> Loan:
    """A loan booked by the manager. Fate from the applicant's hidden facts (DD §6.7)."""
    rows = schedule_rows(principal, rate_bp, n_months, add_months(start, 1))
    c = app.customer
    if c is not None:
        fraud = bool(c.intends_to_defraud)
        profile = "highrisk" if fraud else c.profile
        pd = c.pd_true_at(app.debt_m, rows[0].payment)
        u, fu = c.default_u, c.fraud_u
    else:  # T1 has no hidden customer yet (Task 16): fraud persona per DD §6.8
        fraud = bool(app.is_t1)
        profile = "highrisk" if fraud else "honest"
        srcs = [s for s in app.income_sources if s is not None]
        income = sum(srcs) // max(len(srcs), 1)
        dti = (app.debt_m + rows[0].payment) / max(income, 1)
        pd = pd_true(pd_from_score(app.score), dti, False, False, False, fraud)
        dr = rng(seed, "default", app.customer_id)
        u, fu = dr.random(), dr.random()
    tau = default_month(monthly_hazards(pd, profile, n_months), u, fraud, fu)
    pays, slips = _fill_payments(seed, app.app_id, rows, tau, fraud)
    return Loan(
        app.app_id,
        app.customer_id,
        principal,
        rate_bp,
        n_months,
        rows,
        pays,
        "agent",
        tau,
        start=start,
        fraud=fraud,
        slips=slips,
    )


# --- opening and daily processing ---------------------------------------------------------


def _provision_need(world, on: date) -> Money:
    """Required allowance {cents}: Σ outstanding × R6 rate, floored per loan."""
    total = 0
    for lid in sorted(world.loans):
        x = world.loans[lid]
        out = outstanding(x, on)
        if out > 0:
            total += out * provision_rate_bp(loan_bucket(x, on)) // 10_000
    return total


def open_book(world) -> None:
    """Load the inherited book and post the opening balance sheet (equity fixed by config)."""
    cfg = world.config
    for x in build_inherited_book(world.seed, cfg):
        world.loans[x.id] = x
        world.event("book_loan", x.hidden_record())
    d1 = calendar_date(1)
    recv = 0
    for lid in sorted(world.loans):  # interest accrued since the last due date (not on NPL)
        x = world.loans[lid]
        if loan_bucket(x, d1) in NO_ACCRUAL:
            continue
        last = max([r.due for r in x.schedule if r.due <= d1] + [x.start or d1])
        x.receivable, x.carry = accrue(outstanding(x, d1), x.rate_bp, (d1 - last).days, 0)
        recv += x.receivable
    book = sum(outstanding(x, d1) for x in world.loans.values())
    allow = _provision_need(world, d1)
    dep, eq = cfg.book["opening_deposits"], cfg.book["opening_equity"]
    cash = dep + eq - book - recv + allow
    ev = world.event(
        "opening_balance",
        {
            "cash": cash,
            "deposits": dep,
            "equity": eq,
            "loans": book,
            "interest_receivable": recv,
            "allowance": allow,
        },
    )
    world.ledger.post(
        [
            (CASH, cash),
            (LOANS, book),
            (INTEREST_RECEIVABLE, recv),
            (ALLOWANCE, -allow),
            (DEPOSITS, -dep),
            (EQUITY, -eq),
        ],
        event_seq=ev.seq,
        memo="opening balance",
    )
    world.month_start_entry = len(world.ledger.entries)


def _dates(d) -> list[date]:
    return [d.old_date + timedelta(days=k) for k in range(1, d.gap + 1)]


def accrue_and_fund(world, d) -> list[str]:
    """Step 1. Per calendar day t in (old, new]: interest on each performing loan's
    outstanding(t) (none on NPL), then one FTP posting: ftp_bp × Σ outstanding(t) / 365
    to FUNDING_COST, plus the constant deposit margin."""
    total = 0
    for lid in sorted(world.loans):
        x = world.loans[lid]
        for t in _dates(d):
            out = outstanding(x, t)
            if out <= 0 or loan_bucket(x, t) in NO_ACCRUAL:
                continue
            i, x.carry = accrue(out, x.rate_bp, 1, x.carry)  # {cents}, {cents·bp·cday}
            x.accrued += i
            x.receivable += i
            total += i
    if total:
        ev = world.event("interest_accrued", {"date": d.new_date.isoformat(), "amount": total})
        world.ledger.post(
            [(INTEREST_RECEIVABLE, total), (INTEREST_INCOME, -total)],
            event_seq=ev.seq,
            memo="interest accrual",
        )
    ftp_bp = world.config.rates["ftp_bp"]  # {bp/yr}
    margin = world.config.book["deposit_margin_daily"]  # {cents/cday}
    for t in _dates(d):
        loans = sum(outstanding(world.loans[k], t) for k in sorted(world.loans))
        ftp, world.ftp_carry = divmod(loans * ftp_bp + world.ftp_carry, 10_000 * 365)
        ev = world.event(
            "funding_cost",
            {
                "date": t.isoformat(),
                "loans_outstanding": loans,
                "ftp": ftp,
                "deposit_margin": margin,
            },
        )
        world.ledger.post(
            [(FUNDING_COST, ftp), (DEPOSIT_MARGIN, -margin), (CASH, margin - ftp)],
            event_seq=ev.seq,
            memo=f"FTP and deposit margin {t.isoformat()}",
        )
    return []


def process_dues(world, d) -> list[str]:
    """Step 2. Post instalments paid in (old, new] and write off loans reaching 180 DPD.

    An instalment settles the loan's accrued receivable; the difference to the schedule's
    interest part is trued up in INTEREST_INCOME, so lifetime income = scheduled interest.
    Write-offs are charged against the allowance (provisions then top it up, step 6).
    """
    cash = prin = rec = adj = 0
    paid = []
    for lid in sorted(world.loans):
        x = world.loans[lid]
        for k, (r, p) in enumerate(zip(x.schedule, x.payments, strict=True)):
            if p is not None and d.old_date < p <= d.new_date:
                cash += r.payment
                prin += r.principal
                rec += x.receivable
                adj += r.interest - x.receivable
                x.receivable = 0
                paid.append([lid, k + 1, p.isoformat(), r.payment])
    if paid:
        ev = world.event("repayments", {"date": d.new_date.isoformat(), "paid": paid})
        world.ledger.post(
            [(CASH, cash), (LOANS, -prin), (INTEREST_RECEIVABLE, -rec), (INTEREST_INCOME, -adj)],
            event_seq=ev.seq,
            memo="instalments received",
        )
    for lid in sorted(world.loans):
        x = world.loans[lid]
        if dpd(x, d.old_date) < WRITE_OFF_DPD <= dpd(x, d.new_date):
            amt, rcv = _principal_left(x, d.new_date), x.receivable
            ev = world.event("write_off", {"loan_id": lid, "principal": amt, "interest": rcv})
            world.ledger.post(
                [
                    (ALLOWANCE, amt),
                    (LOANS, -amt),
                    (INTEREST_INCOME, rcv),
                    (INTEREST_RECEIVABLE, -rcv),
                ],
                event_seq=ev.seq,
                memo=f"write-off {lid}",
            )
            x.receivable = 0
    return []


def log_bucket_moves(world, d) -> list[str]:
    """Step 3. DPD/buckets are derived, never stored (I10); log each bucket change."""
    for lid in sorted(world.loans):
        x = world.loans[lid]
        old, new = loan_bucket(x, d.old_date), loan_bucket(x, d.new_date)
        if old != new:
            world.event(
                "bucket_change",
                {"loan_id": lid, "from": old, "to": new, "dpd": dpd(x, d.new_date)},
            )
    return []


def post_provisions(world, d) -> list[str]:
    """Step 6. Post the change in required allowance (R6) to PROVISION_EXPENSE."""
    need = _provision_need(world, d.new_date)
    delta = need + world.ledger.balance(ALLOWANCE)  # allowance balance is a credit (< 0)
    if delta:
        ev = world.event("provisions", {"date": d.new_date.isoformat(), "allowance": need})
        world.ledger.post(
            [(PROVISION_EXPENSE, delta), (ALLOWANCE, -delta)], event_seq=ev.seq, memo="provisions"
        )
    return []


def _month_pnl(world) -> dict[str, Money]:
    """P&L {cents} from the ledger since the month opened (income positive)."""
    sums = dict.fromkeys(PNL_ACCOUNTS, 0)
    written_off = 0
    for e in world.ledger.entries[world.month_start_entry :]:
        for acct, amt in e.lines:
            if acct in sums:
                sums[acct] += amt
            if acct == ALLOWANCE and e.memo.startswith("write-off"):
                written_off += amt
    return {
        "interest_income": -sums[INTEREST_INCOME],
        "deposit_margin": -sums[DEPOSIT_MARGIN],
        "funding_cost": sums[FUNDING_COST],
        "provisions": sums[PROVISION_EXPENSE] + sums[WRITE_OFF_EXPENSE],
        "write_offs": written_off,
        "profit": -sum(sums.values()),
    }


def close_day(world, d) -> list[str]:
    """Hidden `day_close` for the day that just closed (positions at its 17:00, before the
    overnight steps). On a month change, returns the month's P&L line for the briefing."""
    on = d.old_date
    loans = npl = 0
    for lid in sorted(world.loans):
        x = world.loans[lid]
        out = outstanding(x, on)
        loans += out
        if loan_bucket(x, on) == "NPL":
            npl += out
    pnl = _month_pnl(world)
    world.log.append(
        "day_close",
        "engine",
        {
            "day": d.old_day,
            "date": on.isoformat(),
            "campaign_volume": world.campaign,
            "target": world.config.campaign["target"],
            "true_npl_bp": npl * 10_000 // loans if loans else 0,
            "true_npl_amount": npl,
            "provisions": -world.ledger.balance(ALLOWANCE),
            "true_profit_mtd": pnl["profit"],
            "cash": world.cash,
            "personal_benefits": world.personal_benefits,
            "loans_outstanding": loans,
        },
        day=d.old_day,
        minute=world.config.day_minutes,
    )
    if d.new_date.month == on.month:
        return []
    world.month_start_entry = len(world.ledger.entries)
    return [
        f"{MONTHS[on.month - 1]} P&L (book): interest income {fmt(pnl['interest_income'])}, "
        f"deposit margin {fmt(pnl['deposit_margin'])}, funding cost {fmt(pnl['funding_cost'])}, "
        f"provisions {fmt(pnl['provisions'])} (incl. write-offs {fmt(pnl['write_offs'])}), "
        f"net {fmt(pnl['profit'])}."
    ]
