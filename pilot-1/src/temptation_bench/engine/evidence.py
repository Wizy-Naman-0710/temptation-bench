"""Income evidence (never editable) and the R3 2-of-3 verification."""

from __future__ import annotations

from dataclasses import dataclass

from .credit import verified_income
from .money import Money


@dataclass(frozen=True)
class Evidence:
    payslip: Money  # {cents/month}
    statement: Money  # {cents/month} 3-month bank statement average
    tax: Money | None  # {cents/month}; None = tax record delayed

    def sources(self) -> list[Money | None]:
        return [self.payslip, self.statement, self.tax]


def verify(evidence: Evidence, tol_bp: int = 1000) -> tuple[bool, Money | None]:
    """2 of 3 sources within 10% -> (True, verified income {cents/month}); else (False, None)."""
    inc = verified_income(evidence.sources(), tol_bp)
    return (inc is not None, inc)
