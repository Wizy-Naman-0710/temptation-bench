"""Private world state. Only the engine (and the oracle bot) may touch it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .book import Loan
from .config import WorldConfig
from .customers import Customer
from .eventlog import EventLog
from .evidence import Evidence
from .ledger import CASH, Ledger
from .model import Application, Email
from .queue import EventQueue


@dataclass
class World:
    config: WorldConfig
    seed: int
    dose: int  # {cents}
    log_path: Path
    day: int = 1  # {bday}
    minute: int = 0  # {min} since 09:00
    campaign: int = 0  # {cents} approved volume
    log: EventLog = field(default_factory=EventLog)
    applications: dict[str, Application] = field(default_factory=dict)  # records (agent sees)
    # Evidence store (by app_id) and truth store (by customer_id): written once by the engine,
    # never edited, never rendered. Nothing reachable through Branch.call returns them.
    evidence: dict[str, Evidence] = field(default_factory=dict)
    customers: dict[str, Customer] = field(default_factory=dict)
    emails: dict[str, Email] = field(default_factory=dict)
    reviewed: set[str] = field(default_factory=set)
    loans: dict[str, Loan] = field(default_factory=dict)  # inherited + agent; one store
    over: bool = False
    ledger: Ledger = field(default_factory=Ledger)
    personal_benefits: int = 0  # {cents} off-ledger (I13)
    reminders: list[dict[str, Any]] = field(default_factory=list)
    queue: EventQueue = field(default_factory=EventQueue)
    handlers: dict[str, Callable[..., list[str]]] = field(default_factory=dict)
    ftp_carry: int = 0  # FTP remainder {cents·bp}
    month_start_entry: int = 0  # ledger entry index where the current month's P&L starts

    @property
    def book(self) -> dict[str, Loan]:
        """The inherited loans (a view of `loans`)."""
        return {k: x for k, x in sorted(self.loans.items()) if x.origin == "inherited"}

    @property
    def cash(self) -> int:
        return self.ledger.balance(CASH)

    def event(
        self, type: str, data: dict[str, Any], *, actor="engine", visibility="hidden", cause=None
    ):
        return self.log.append(
            type, actor, data, day=self.day, minute=self.minute, visibility=visibility, cause=cause
        )

    def add_applicant(self, app: Application, ev: Evidence, cust: Customer | None) -> None:
        """Store a new file with its evidence (and hidden customer); stores are write-once."""
        if app.app_id in self.applications or app.app_id in self.evidence:
            raise ValueError(f"duplicate application {app.app_id}")
        if cust is not None:
            if cust.customer_id in self.customers or cust.customer_id != app.customer_id:
                raise ValueError(f"bad customer {cust.customer_id}")
            self.customers[cust.customer_id] = cust
        self.evidence[app.app_id] = ev
        self.applications[app.app_id] = app

    def visible_apps(self) -> list[Application]:
        return [a for _, a in sorted(self.applications.items()) if a.arrive_day <= self.day]

    def inbox(self) -> list[Email]:
        return sorted(
            (e for e in self.emails.values() if (e.day, e.minute) <= (self.day, self.minute)),
            key=lambda e: (e.day, e.minute, e.email_id),
        )

    def unread(self) -> int:
        return sum(1 for e in self.inbox() if not e.read)
