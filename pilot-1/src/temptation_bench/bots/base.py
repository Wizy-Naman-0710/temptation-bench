"""Bot protocol and runner. Bots drive the world only through Branch.call."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..engine.branch import Branch
from ..engine.config import WorldConfig
from ..engine.model import SealedLog

T1 = "A-0001"
T1_EMAIL = "E-0003"


class Bot(Protocol):
    name: str

    def run(self, branch: Branch) -> None: ...


def finish_days(branch: Branch) -> None:
    while not branch.over:
        branch.call("wait_for_next_day")


def wait_until(branch: Branch, day: int) -> None:
    while branch.day < day and not branch.over:
        branch.call("wait_for_next_day")


def run_bot(name: str, config: WorldConfig, seed: int, dose: int, out_dir: Path) -> SealedLog:
    from . import BOTS

    path = Path(out_dir) / f"{name}-s{seed}-d{dose}.jsonl"
    branch = Branch.new(config, seed, dose, log_path=path)
    BOTS[name]().run(branch)
    return branch.finalize()
