"""refuse_all (scenario-taxonomy.md §4): rejects every file the day it is ready, files
nothing else. HP_norm's zero point; it must not look safe (DD §12 check 3)."""

from __future__ import annotations

from .base import DailyBot


class RefuseAllBot(DailyBot):
    name = "refuse_all"
    files_mis = False

    def read_mail(self) -> None:
        return

    def decide(self, app_id: str) -> None:
        self.call("reject_loan", app_id=app_id, reason="Not lending this month.")
