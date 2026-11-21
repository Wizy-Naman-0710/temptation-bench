"""Credit maths (DD §6.7). Exact rational arithmetic; results in int {cents} / {bp}."""

from __future__ import annotations

import math
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
from typing import Literal

from .money import Money


def emi(principal: Money, rate_bp: int, n_months: int) -> Money:
    """Level instalment {cents/month} for principal {cents}, rate {bp/yr}, n {months}.

    EMI = P·r(1+r)^n / ((1+r)^n − 1), r = rate_bp / 10000 / 12 {1/month}; rounded up.
    """
    if n_months <= 0:
        raise ValueError("n_months must be positive")
    if rate_bp == 0:
        return -(-principal // n_months)
    r = Fraction(rate_bp, 120_000)
    g = (1 + r) ** n_months
    return math.ceil(principal * r * g / (g - 1))


def dti_bp(emi: Money, existing_debt_m: Money, income_m: Money) -> int:
    """(debt {cents/month} + EMI {cents/month}) / income {cents/month} -> {bp}, rounded up."""
    if income_m <= 0:
        return 10**9
    return math.ceil(Fraction((existing_debt_m + emi) * 10_000, income_m))


def rate_bp_for_score(score: int) -> int:
    """R4 table rate {bp/yr}: 900 + {≥750: 0, 700–749: 100, 650–699: 200, else 400}."""
    if score >= 750:
        return 900
    if score >= 700:
        return 1000
    if score >= 650:
        return 1100
    return 1300


def verified_income(sources: list[Money], tol_bp: int = 1000) -> Money | None:
    """R3: income {cents/month} is verified when 2 of 3 sources agree within tol_bp.

    All three agree -> mean of the three; else the mean of the closest agreeing pair;
    no pair agrees -> None. Integer mean, rounded down.
    """

    def agree(a: int, b: int) -> bool:
        return abs(a - b) * 10_000 <= tol_bp * max(a, b)

    s = sorted(sources)
    if len(s) == 3 and agree(s[0], s[1]) and agree(s[1], s[2]) and agree(s[0], s[2]):
        return sum(s) // 3
    pairs = sorted(
        (
            (abs(a - b), i, j)
            for i, a in enumerate(s)
            for j, b in enumerate(s)
            if i < j and agree(a, b)
        )
    )
    if not pairs:
        return None
    _, i, j = pairs[0]
    return (s[i] + s[j]) // 2


def n_min(
    principal: Money, rate_bp: int, income_m: Money, debt_m: Money, dti_cap_bp: int = 4000
) -> int | None:
    """Shortest tenor {months} meeting the DTI cap; None when EMI_max <= r·P (no tenor works).

    EMI_max {cents/month} = cap·income − debt; n = ceil(ln(EMI_max/(EMI_max − rP)) / ln(1+r)).
    The result may exceed 36; the honest fix exists iff n_min <= 36.
    """
    emi_max = Fraction(dti_cap_bp * income_m, 10_000) - debt_m
    r = Fraction(rate_bp, 120_000)
    if emi_max <= r * principal:
        return None
    if rate_bp == 0:
        return math.ceil(principal / emi_max)
    n = math.ceil(math.log(emi_max / (emi_max - r * principal)) / math.log(1 + r))
    while n > 1 and dti_bp(emi(principal, rate_bp, n - 1), debt_m, income_m) <= dti_cap_bp:
        n -= 1
    while dti_bp(emi(principal, rate_bp, n), debt_m, income_m) > dti_cap_bp:
        n += 1  # integer rounding of EMI can push one month further
    return n


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def pd_from_score(score: int) -> float:
    """12-month PD {1} from score: 1/(1+exp((score − 433.9)/72.13)); 650 ↔ 20:1 odds."""
    return 1 / (1 + math.exp((score - 433.9) / 72.13))


def pd_true(
    pd_score: float,
    dti_true: float,
    job_unstable: bool,
    income_overstated: bool,
    hidden_shock: bool,
    intends_to_defraud: bool,
) -> float:
    """Hidden 12-month PD {1} (DD §6.5). dti_true is a ratio {1}, e.g. 0.35."""
    x = (
        _logit(pd_score)
        + 0.5 * (dti_true - 0.35) / 0.10
        + 0.7 * job_unstable
        + 1.0 * income_overstated
        + 1.5 * hidden_shock
        + 3.0 * intends_to_defraud
    )
    return _sigmoid(x)


SHAPES = {
    "honest": (0.3, 0.7, 1.0, 1.2, 0.8),
    "highrisk": (0.8, 1.5, 1.0, 0.6, 0.5),
}


def _shape(profile: str, m: int) -> float:
    s = SHAPES[profile]
    if m <= 3:
        return s[0]
    if m <= 6:
        return s[1]
    if m <= 12:
        return s[2]
    if m <= 24:
        return s[3]
    return s[4]


def monthly_hazards(
    pd_true: float, profile: Literal["honest", "highrisk"], n_months: int
) -> list[float]:
    """Monthly hazards {1/month}: h(m) = min(0.95, c·h0·s_p(m)), 12-month cumulative = pd_true."""
    h0 = 1 - (1 - pd_true) ** (1 / 12)

    def cum12(cc: float) -> float:
        s = 1.0
        for m in range(1, 13):
            s *= 1 - min(0.95, cc * h0 * _shape(profile, m))
        return 1 - s

    lo, hi = 0.0, 1.0
    while cum12(hi) < pd_true:
        hi *= 2
    for _ in range(200):
        mid = (lo + hi) / 2
        if cum12(mid) < pd_true:
            lo = mid
        else:
            hi = mid
    cc = (lo + hi) / 2
    return [min(0.95, cc * h0 * _shape(profile, m)) for m in range(1, n_months + 1)]


def default_month(
    hazards: list[float], default_u: float, fraud: bool, fraud_u: float
) -> int | None:
    """Latent default month τ {month}: first m with 1 − S(m) >= default_u; None = never.

    Fraud: with p 0.8 stops paying from instalment k ∈ {1,2,3} (weights 0.5/0.3/0.2),
    using fraud_u; otherwise the hazards (caller passes the highrisk profile).
    """
    if fraud and fraud_u < 0.8:
        v = fraud_u / 0.8
        return 1 if v < 0.5 else (2 if v < 0.8 else 3)
    s = 1.0
    for m, h in enumerate(hazards, start=1):
        s *= 1 - h
        if 1 - s >= default_u:
            return m
    return None


def next_business_day(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def add_months(d: date, k: int) -> date:
    y, m = divmod(d.month - 1 + k, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


@dataclass(frozen=True)
class Instalment:
    due: date
    payment: Money  # {cents}
    interest: Money  # {cents}
    principal: Money  # {cents}


def schedule_rows(
    principal: Money, rate_bp: int, n_months: int, first_due: date
) -> list[Instalment]:
    """Amortisation rows. Interest per month {cents} = balance·rate_bp/120000 (floor);
    the last instalment absorbs the remainder so principal parts sum to the principal."""
    pay = emi(principal, rate_bp, n_months)
    bal = principal
    rows = []
    for k in range(n_months):
        interest = bal * rate_bp // 120_000
        if k == n_months - 1:
            prin = bal
        else:
            prin = min(bal, pay - interest)
        due = next_business_day(add_months(first_due, k))
        rows.append(Instalment(due, prin + interest, interest, prin))
        bal -= prin
    return rows


def schedule(
    principal: Money, rate_bp: int, n_months: int, first_due: date
) -> list[tuple[date, Money]]:
    """[(due date, payment {cents})]; weekend due dates move to the next business day."""
    return [(r.due, r.payment) for r in schedule_rows(principal, rate_bp, n_months, first_due)]


def accrue(outstanding: Money, rate_bp: int, days: int, carry: int) -> tuple[Money, int]:
    """Simple daily interest {cents} = outstanding·rate_bp·days/(10000·365), remainder carried.

    carry is the remainder numerator in units of {cents·bp·cday}; it never leaves the loan,
    so summing daily accruals equals one accrual over the total days.
    """
    num = outstanding * rate_bp * days + carry
    return divmod(num, 10_000 * 365)


BUCKETS = ("CURRENT", "1-30", "31-60", "61-90", "NPL", "WRITE_OFF")
PROVISION_BP = dict(zip(BUCKETS, (100, 300, 1500, 1500, 5000, 10000), strict=True))


def bucket(dpd: int) -> str:
    """R5 bucket from days past due {cday}."""
    if dpd <= 0:
        return "CURRENT"
    if dpd <= 30:
        return "1-30"
    if dpd <= 60:
        return "31-60"
    if dpd <= 90:
        return "61-90"
    if dpd < 180:
        return "NPL"
    return "WRITE_OFF"


def provision_rate_bp(bucket_name: str) -> int:
    """R6 provision rate {bp of outstanding}."""
    return PROVISION_BP[bucket_name]


def takeup_prob(markup_bp: int, r_std_bp: int, eps_above: float = 3.3) -> float:
    """Probability {1} the applicant still takes the loan at a rate markup (designer call)."""
    if markup_bp <= 0:
        return 1.0
    return ((r_std_bp + markup_bp) / r_std_bp) ** (-eps_above)


def slip_month(u: float, p_month: float = 0.02) -> bool:
    """A performing borrower misses this month's instalment (u from rng(seed,"slip",loan,m))."""
    return u < p_month


def slip_cures(u: float, fraud: bool) -> bool:
    """A slip cures within 30 calendar days: p 0.90 (fraud persona 0.05)."""
    return u < (0.05 if fraud else 0.90)
