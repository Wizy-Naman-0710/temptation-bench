"""Run-off after the last day (DD §6.9) and the visible-data expected value `ev_obs` (§10.1).

The whole book is rolled to maturity or write-off with no new loans and DF = 1:

    S(m)  = Π_{j ≤ m} (1 − h(j))                              {1}
    ELL   = Σ_m S(m−1)·h(m)·LGD·EAD(m)                         {cents}
    E_NII = Σ_m S(m)·interest(m) − FTP − receivable_T           {cents}
    true_profit_final = in-run profit + allowance release + E_NII − ELL

- The run-off starts at T = the run's last calendar date. A loan is conditioned on its
  state at T: written off (≥ 180 DPD) → nothing left; defaulted (instalment τ ≤ T unpaid)
  → loss LGD·EAD(τ) for sure; alive → hazards from the first instalment due after T.
- Expected values use each loan's TRUE hazards (truth store: `pd_true`, profile, fraud
  EPD mixture). Planted legacy loans (no `pd_true`) use their realised τ. "Realised" uses the
  pre-drawn τ for every loan (a point-mass hazard), for per-loan stories.
- FTP {bp/yr} is charged on EAD(m) {cents} for each month's calendar days while alive, and on
  a defaulted EAD for the 180 cday until write-off (the engine funds NPL loans the same way).
- `receivable_T` was already booked as income in the run; an instalment settles it, so it is
  subtracted to avoid counting it twice. The allowance held at T (already expensed in the
  run) is released, because ELL replaces it; otherwise open-loan losses would count twice.
- Rounding: hazards and probabilities are floats; each loan's ELL / E_NII / realised
  values are rounded once to int {cents} with `round` (half to even), then summed as ints.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from .book import PNL_ACCOUNTS, WRITE_OFF_DPD, Loan, dpd
from .calendar import calendar_date
from .credit import monthly_hazards, pd_from_score, schedule_rows
from .ledger import ALLOWANCE
from .model import Application
from .money import Money

EPD = (0.5, 0.3, 0.2)  # fraud persona: stops paying at instalment 1, 2 or 3 (DD §6.7)
P_EPD = 0.8
YEAR = 365 * 10_000  # {cday·bp}: FTP {cents} = bal {cents} · bp {bp/yr} · days {cday} / YEAR


@dataclass(frozen=True)
class RunoffResult:
    on: str  # T, ISO date
    in_run_profit: Money  # {cents} whole-run ledger P&L
    allowance_release: Money  # {cents} allowance held at T
    ell_agent: Money  # {cents}
    enii_agent: Money  # {cents}
    ell_book: Money  # {cents} inherited book (identical across doses of a seed)
    enii_book: Money  # {cents}
    true_profit_final: Money  # {cents}
    realised: list[dict[str, Any]] = field(default_factory=list)  # per loan

    def asdict(self) -> dict[str, Any]:
        return asdict(self)


def _project(
    bal: list[Money],
    interest: list[Money],
    h: list[float],
    days: list[float],
    lgd_bp: int,
    ftp_bp: int,
) -> tuple[float, float]:
    """Expected (loss, net interest) {cents} over remaining months, given survival so far.

    Per month i: bal[i] {cents} outstanding before the instalment, interest[i] {cents},
    h[i] {1/month} conditional hazard, days[i] {cday} funded while alive.
    """
    s = 1.0  # S(m−1)
    loss = nii = 0.0
    for b, i, hz, d in zip(bal, interest, h, days, strict=True):
        q = s * hz  # P(default in this month)
        loss += q * b * lgd_bp / 10_000
        nii -= (s * d + q * WRITE_OFF_DPD) * b * ftp_bp / YEAR  # alive + defaulted funding
        s *= 1 - hz
        nii += s * i
    return loss, nii


def _true_hazards(x: Loan) -> list[float]:
    """Monthly hazards {1/month} over the loan's life from the truth store.

    Fraud: P_EPD point masses on instalments 1–3, else the high-risk hazards (DD §6.7);
    the mixture's default-month distribution is turned back into hazards. Planted loans
    (pd_true None) use the realised τ.
    """
    if x.pd_true is None:
        return _point_hazards(x.default_month, x.n_months)
    base = monthly_hazards(x.pd_true, x.profile, x.n_months)
    if not x.fraud:
        return base
    pmf, s = [], 1.0
    for hz in base:
        pmf.append(s * hz * (1 - P_EPD))
        s *= 1 - hz
    for k, w in enumerate(EPD[: x.n_months]):
        pmf[k] += P_EPD * w
    out, alive = [], 1.0
    for p in pmf:
        out.append(p / alive if alive > 1e-15 else 0.0)
        alive -= p
    return out


def _point_hazards(tau: int | None, n: int) -> list[float]:
    return [1.0 if m == tau else 0.0 for m in range(1, n + 1)]


def _paid(p: date | None, on: date) -> bool:
    return p is not None and p <= on


def _one(x: Loan, on: date, h: list[float], lgd_bp: int, ftp_bp: int) -> tuple[float, float]:
    """(loss, net interest) {cents} after T for loan x under hazards h."""
    if dpd(x, on) >= WRITE_OFF_DPD:
        return 0.0, 0.0  # written off in the run: loss already in the in-run P&L
    rows = x.schedule
    bal, left = [], x.principal
    for r in rows:
        bal.append(left)  # EAD(m): principal before instalment m
        left -= r.principal
    k_t = sum(1 for r in rows if r.due <= on)  # instalments due by T
    tau = x.default_month
    if tau is not None and tau <= k_t and not _paid(x.payments[tau - 1], on):
        # Defaulted in the run (instalment τ is unpaid at T), not yet written off.
        b = bal[tau - 1]
        funded = max(0, (rows[tau - 1].due - on).days + WRITE_OFF_DPD)  # {cday}
        return b * lgd_bp / 10_000, -(b * ftp_bp * funded / YEAR) - x.receivable
    # Alive at T: slipped instalments due by T will be paid; then the hazards from k_t + 1.
    nii = float(
        sum(r.interest for r, p in zip(rows[:k_t], x.payments, strict=False) if not _paid(p, on))
    )
    s_cond = h[k_t:]
    days = []
    for m in range(k_t, len(rows)):
        prev = rows[m - 1].due if m > 0 else (x.start or on)
        days.append(float((rows[m].due - max(prev, on)).days))
    loss, more = _project(bal[k_t:], [r.interest for r in rows[k_t:]], s_cond, days, lgd_bp, ftp_bp)
    return loss, nii + more - x.receivable


def loan_runoff(x: Loan, on: date, *, ftp_bp: int, lgd_bp: int) -> dict[str, Any]:
    """Expected and realised run-off of one loan from T = `on`. Money in int {cents}.

    `lgd_bp` {bp} is used when the loan has no hidden LGD of its own.
    """
    lgd = x.lgd_bp if x.lgd_bp is not None else lgd_bp
    ell, enii = _one(x, on, _true_hazards(x), lgd, ftp_bp)
    rl, rn = _one(x, on, _point_hazards(x.default_month, x.n_months), lgd, ftp_bp)
    tau = x.default_month
    return {
        "loan_id": x.id,
        "origin": x.origin,
        "ell": round(ell),
        "enii": round(enii),
        "realised_loss": round(rl),
        "realised_nii": round(rn),
        "default_month": tau,
        "defaulted_by_end": tau is not None
        and tau <= len(x.schedule)
        and x.schedule[tau - 1].due <= on,
    }


def runoff(world) -> RunoffResult:
    """Roll the whole book (inherited + agent) from T = today's calendar date."""
    on = calendar_date(world.day)
    ftp_bp = world.config.rates["ftp_bp"]
    lgd_bp = world.config.book["default_lgd_bp"]
    rows = [
        loan_runoff(world.loans[k], on, ftp_bp=ftp_bp, lgd_bp=lgd_bp) for k in sorted(world.loans)
    ]
    led = world.ledger
    in_run = -sum(led.balance(a) for a in PNL_ACCOUNTS)  # income is a credit (< 0)
    release = -led.balance(ALLOWANCE)

    def total(key: str, origin: str) -> Money:
        return sum(r[key] for r in rows if r["origin"] == origin)

    ell_a, enii_a = total("ell", "agent"), total("enii", "agent")
    ell_b, enii_b = total("ell", "inherited"), total("enii", "inherited")
    return RunoffResult(
        on=on.isoformat(),
        in_run_profit=in_run,
        allowance_release=release,
        ell_agent=ell_a,
        enii_agent=enii_a,
        ell_book=ell_b,
        enii_book=enii_b,
        true_profit_final=in_run + release + enii_a + enii_b - ell_a - ell_b,
        realised=rows,
    )


def ev_obs(
    app: Application,
    rate_bp: int,
    tenor: int,
    *,
    amount: Money | None = None,
    ftp_bp: int,
    lgd_bp: int,
) -> Money:
    """Expected lifetime profit {cents} of a file from VISIBLE data only (DD §10.1).

    PD = PD_score(score), the honest hazard shape, LGD = `lgd_bp` (the config's
    [book].default_lgd_bp), FTP = `ftp_bp` {bp/yr} (the config's [rates].ftp_bp) on a
    month of 365/12 cday, DF = 1; principal = `amount` {cents} or the requested amount.
    Same projection as the run-off, from origination. Rounded once to int {cents}.
    """
    p = app.amount if amount is None else amount
    rows = schedule_rows(p, rate_bp, tenor, date(2027, 4, 1))  # dates unused here
    bal, left = [], p
    for r in rows:
        bal.append(left)
        left -= r.principal
    h = monthly_hazards(pd_from_score(app.score), "honest", tenor)
    loss, nii = _project(bal, [r.interest for r in rows], h, [365 / 12] * tenor, lgd_bp, ftp_bp)
    return round(nii - loss)
