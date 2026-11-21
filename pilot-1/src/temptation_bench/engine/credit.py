"""Credit maths (DD §6.7). Exact rational arithmetic; results in int {cents} / {bp}."""

from __future__ import annotations

import math
from fractions import Fraction

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
