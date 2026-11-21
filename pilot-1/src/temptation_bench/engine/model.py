"""Small shared value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar


class Refusal(Exception):
    """A rule or argument error. The message is shown to the agent; state is unchanged."""


@dataclass(frozen=True)
class DecisionContext:
    """What the model could see at decision time (set by the harness; bots use PERFECT)."""

    latest_review_in_window: bool = True
    latest_portfolio_in_window: bool = True
    offer_email_in_window: bool = True

    PERFECT: ClassVar[DecisionContext]


DecisionContext.PERFECT = DecisionContext()


@dataclass(frozen=True)
class SealedLog:
    path: Path
    sha256: str
    truncated: bool


@dataclass
class Application:
    app_id: str
    applicant: str
    customer_id: str
    product: str
    purpose: str
    amount: int  # {cents}
    tenor_m: int  # {months}
    score: int
    income_sources: list[int | None]  # {cents/month}: payslip, statement, tax (None=delayed)
    debt_m: int  # {cents/month}
    arrive_day: int
    ready_day: int
    officer_note: str = ""
    status: str = "pending"  # pending | approved | rejected | escalated | withdrawn
    is_t1: bool = False
    customer: object = None  # hidden Customer; never rendered
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Email:
    email_id: str
    day: int
    minute: int
    sender: str
    subject: str
    body: str
    case_id: str | None = None
    read: bool = False
