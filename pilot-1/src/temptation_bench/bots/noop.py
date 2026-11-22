"""The noop bot: does nothing but wait (integrity note §7). Weak KPI, no crash."""

from __future__ import annotations

from ..engine.branch import Branch
from .base import finish_days


class NoopBot:
    name = "noop"

    def run(self, branch: Branch) -> None:
        finish_days(branch)
