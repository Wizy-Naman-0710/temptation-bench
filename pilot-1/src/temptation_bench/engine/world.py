"""Private world state. Only the engine (and the oracle bot) may touch it."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
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
from .records import AppRecord, Records


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
    applications: dict[str, Application] = field(default_factory=dict)  # fixed file fields
    records: Records = field(default_factory=Records)  # editable fields, versioned (I9)
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
    notes: list[dict[str, Any]] = field(default_factory=list)  # {day, minute, text}
    reports: list[Any] = field(default_factory=list)  # FiledReport (frozen; I12)
    # Hidden truth snapshot per filed report id, at its cut-off. Never rendered.
    report_truth: dict[str, dict[str, Any]] = field(default_factory=dict)
    gifts: list[str] = field(default_factory=list)  # email ids in the gift register
    compliance_no: int = 0  # last CC-#### case number given out
    queue: EventQueue = field(default_factory=EventQueue)
    handlers: dict[str, Callable[..., list[str]]] = field(default_factory=dict)  # queue kinds
    # Direct hooks a tool fires by name (same shape as handlers), so tools never import the
    # module that registers them (e.g. scenario's "t1_approved").
    hooks: dict[str, Callable[..., list[str]]] = field(default_factory=dict)
    ftp_carry: int = 0  # FTP remainder {cents·bp}
    month_start_entry: int = 0  # ledger entry index where the current month's P&L starts
    scenario: Any = None  # the ScenarioPlan (scenario.py); hidden like the truth store
    planned_emails: dict[str, Any] = field(default_factory=dict)  # composed before the run
    # Dynamic emails E-0101, E-0102, ...: starts at [scenario.emails].first_dynamic.
    next_email_no: int = field(init=False)

    def __post_init__(self) -> None:
        self.next_email_no = int(self.config.scenario["emails"]["first_dynamic"])

    def new_email_id(self) -> str:
        n = self.next_email_no
        self.next_email_no += 1
        return f"E-{n:04d}"

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

    def add_applicant(
        self, app: Application, record: AppRecord, ev: Evidence, cust: Customer | None
    ) -> None:
        """Store a new file, its version-1 record and its evidence (and hidden customer).
        Evidence and truth are write-once; the record starts at version 1, logged here (I9)."""
        if app.app_id in self.applications or app.app_id in self.evidence:
            raise ValueError(f"duplicate application {app.app_id}")
        if cust is not None:
            if cust.customer_id in self.customers or cust.customer_id != app.customer_id:
                raise ValueError(f"bad customer {cust.customer_id}")
            self.customers[cust.customer_id] = cust
        self.evidence[app.app_id] = ev
        self.applications[app.app_id] = app
        self.records.create(app.app_id, record, day=self.day, minute=self.minute)
        self.event(
            "application_created",
            {
                "app_id": app.app_id,
                "is_t1": app.is_t1,
                "score": app.score,
                "amount": app.amount,
                "tenor_m": app.tenor_m,
                "income_sources": app.income_sources,
                "version": 1,
                "record": asdict(record),
            },
        )

    def visible_apps(self) -> list[Application]:
        """Files the agent can see: those the officer has prepared (ready). A file that
        arrives during the day is prepared overnight, so planted and ordinary files go
        through the same states (Task 17: no planted file is ever seen "in preparation")."""
        return [a for _, a in sorted(self.applications.items()) if a.ready_day <= self.day]

    def inbox(self) -> list[Email]:
        return sorted(
            (e for e in self.emails.values() if (e.day, e.minute) <= (self.day, self.minute)),
            key=lambda e: (e.day, e.minute, e.email_id),
        )

    def unread(self) -> int:
        return sum(1 for e in self.inbox() if not e.read)
