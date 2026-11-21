"""Append-only engine event log, written as JSON Lines with a SHA-256 digest."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Visibility = Literal["agent", "hidden"]


@dataclass(frozen=True)
class Event:
    seq: int
    day: int  # {bday}
    minute: int  # {min} since 09:00
    type: str
    actor: str
    visibility: Visibility
    data: dict[str, Any] = field(default_factory=dict)
    cause: int | None = None  # seq of the event that led to this one

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


class EventLog:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def append(
        self,
        type: str,
        actor: str,
        data: dict[str, Any],
        *,
        day: int,
        minute: int,
        visibility: Visibility = "hidden",
        cause: int | None = None,
    ) -> Event:
        # Round-trip through JSON so the in-memory event equals what is written.
        clean = json.loads(json.dumps(data, sort_keys=True))
        e = Event(len(self.events), day, minute, type, actor, visibility, clean, cause)
        self.events.append(e)
        return e

    def write_jsonl(self, path: Path | str) -> str:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = "".join(e.to_json() + "\n" for e in self.events).encode()
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def read_jsonl(path: Path | str) -> list[Event]:
        out = []
        for line in Path(path).read_text().splitlines():
            if line.strip():
                out.append(Event(**json.loads(line)))
        return out
