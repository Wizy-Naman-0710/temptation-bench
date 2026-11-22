"""approve_all (scenario-taxonomy.md §4): reviews every file and approves it at the
requested amount and tenor at the table rate, with no exception declared."""

from __future__ import annotations

from .base import DailyBot


class ApproveAllBot(DailyBot):
    name = "approve_all"
    files_mis = False

    def read_mail(self) -> None:
        return

    def decide(self, app_id: str) -> None:
        rv = self.review(app_id)
        if rv is not None:
            self.call("approve_loan", app_id=app_id, amount=rv.amount // 100, tenor_m=rv.tenor)
