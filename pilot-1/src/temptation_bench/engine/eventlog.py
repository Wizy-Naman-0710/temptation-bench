"""Append-only engine event log, written as JSON Lines with a SHA-256 digest."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
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
        # Same output as json.dumps(asdict(self), ...) without asdict's deep copy (I8 hashes
        # the whole log after every decision, so this is on the hot path).
        d = {
            "seq": self.seq,
            "day": self.day,
            "minute": self.minute,
            "type": self.type,
            "actor": self.actor,
            "visibility": self.visibility,
            "data": self.data,
            "cause": self.cause,
        }
        return json.dumps(d, sort_keys=True, separators=(",", ":"))


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


# run_config fields that name the code, not what it did (left out of the behaviour hash)
CODE_ONLY_RUN_CONFIG = ("engine_sha",)


def behaviour_sha256(events: list[Event]) -> str:
    """SHA-256 of the JSONL lines with `run_config.engine_sha` blanked: equal for two runs
    that logged the same thing, whatever the engine source text (golden-hash test)."""
    h = hashlib.sha256()
    for e in events:
        if e.type == "run_config":
            data = {k: ("" if k in CODE_ONLY_RUN_CONFIG else v) for k, v in e.data.items()}
            e = Event(e.seq, e.day, e.minute, e.type, e.actor, e.visibility, data, e.cause)
        h.update((e.to_json() + "\n").encode())
    return h.hexdigest()
