"""The run tag: the hidden first event of every log (`run_config`) and the engine hash."""

from __future__ import annotations

import functools
import hashlib
from pathlib import Path
from typing import Any


@functools.cache
def engine_sha() -> str:
    """SHA-256 over every engine .py file, sorted by relative path (path bytes, then file)."""
    root = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.py"), key=lambda q: q.relative_to(root).as_posix()):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def people_name(people: Any) -> str:
    """The backend actually used: its `name`, else its class name (never cfg.people)."""
    return str(getattr(people, "name", type(people).__name__))


def run_config(cfg, seed: int, dose: int, people: Any) -> dict[str, Any]:
    """Which cell this run belongs to. `people` is the backend the run really uses."""
    return {
        "seed": seed,
        "dose": dose,
        "pressure": cfg.factors["pressure"],
        "observation": cfg.factors["observation"],
        "people": people_name(people),
        "mode": cfg.mode,
        "variant": cfg.variant,
        "last_day": cfg.last_day,
        "engine_sha": engine_sha(),
    }
