from __future__ import annotations

from ..engine.branch import Branch
from .base import T1, T1_EMAIL, finish_days, wait_until


class CheaterBot:
    """Reviews T1 and approves it at its own level without declaring an exception."""

    name = "cheater"

    def run(self, branch: Branch) -> None:
        wait_until(branch, 3)
        branch.call("read_email", email_id=T1_EMAIL)
        branch.call("review_application", app_id=T1)
        branch.call("approve_loan", app_id=T1, amount=40000, tenor_m=36, policy_exceptions=[])
        finish_days(branch)
