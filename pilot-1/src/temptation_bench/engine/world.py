"""Private world state. Only the engine (and the oracle bot) may touch it."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import WorldConfig
from .eventlog import EventLog
from .model import Application, Email


@dataclass
class World:
    config: WorldConfig
    seed: int
    dose: int  # {cents}
    log_path: Path
    day: int = 1  # {bday}
    minute: int = 0  # {min} since 09:00
    cash: int = 0  # {cents}
    campaign: int = 0  # {cents} approved volume
    log: EventLog = field(default_factory=EventLog)
    applications: dict[str, Application] = field(default_factory=dict)
    emails: dict[str, Email] = field(default_factory=dict)
    reviewed: set[str] = field(default_factory=set)
    loans: dict[str, dict[str, Any]] = field(default_factory=dict)
    over: bool = False

    def event(
        self, type: str, data: dict[str, Any], *, actor="engine", visibility="hidden", cause=None
    ):
        return self.log.append(
            type, actor, data, day=self.day, minute=self.minute, visibility=visibility, cause=cause
        )

    def visible_apps(self) -> list[Application]:
        return [a for _, a in sorted(self.applications.items()) if a.arrive_day <= self.day]

    def inbox(self) -> list[Email]:
        return sorted(
            (e for e in self.emails.values() if (e.day, e.minute) <= (self.day, self.minute)),
            key=lambda e: (e.day, e.minute, e.email_id),
        )

    def unread(self) -> int:
        return sum(1 for e in self.inbox() if not e.read)
