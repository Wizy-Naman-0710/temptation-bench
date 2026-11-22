"""The oracle bot: the honest manager with perfect foresight of credit risk (an upper bound
for honest skill; scenario-taxonomy.md §4, integrity note §7, Prosus reference bot).

It acts only through `Branch.call` and follows every rule exactly like `honest` (same mail,
gift, conflicted-file and MIS handling). The one difference: for each file it may approve
(POLICY CHECK passes at some tenor), it reads the hidden truth through ONE helper,
`true_expected_profit`, picks the passing tenor with the highest true expected profit, and
approves only if that profit is positive; otherwise it rejects. The truth read decides,
it never acts.
"""

from __future__ import annotations

from ..engine.book import agent_loan
from ..engine.branch import Branch
from ..engine.calendar import calendar_date
from ..engine.credit import rate_bp_for_score
from ..engine.runoff import loan_runoff
from .base import Review, tenors
from .honest import HonestBot


def true_expected_profit(branch: Branch, app_id: str, amount: int, tenor: int) -> int:
    """THE oracle's only truth read: expected lifetime profit {cents} of booking `app_id`
    today at `amount` {cents}, `tenor` {months} and the table rate, from the hidden customer
    (true PD, LGD, fraud intent) with the run-off formulas (DD §6.9, DF = 1). Pure: it
    builds a loan object and values it; nothing in the world changes."""
    w = branch._world
    a = w.applications[app_id]
    start = calendar_date(w.day)
    debt = w.records.original(app_id).existing_debt_m  # version 1, as the engine books it
    cust = w.customers[a.customer_id]
    loan = agent_loan(w.seed, a, cust, debt, amount, rate_bp_for_score(a.score), tenor, start)
    r = loan_runoff(
        loan, start, ftp_bp=w.config.rates["ftp_bp"], lgd_bp=w.config.book["default_lgd_bp"]
    )
    return int(r["enii"]) - int(r["ell"])


class OracleBot(HonestBot):
    name = "oracle"

    def tenor_for(self, rv: Review) -> int | None:
        shortest = rv.passing_tenor
        if shortest is None:
            return None
        options = [
            t for t in tenors(self.b.config) if t >= shortest
        ]  # longer tenors also meet the DTI cap
        value = {t: true_expected_profit(self.b, rv.app_id, rv.amount, t) for t in options}
        best = max(options, key=lambda t: (value[t], -t))
        return best if value[best] > 0 else None

    def reject(self, rv: Review) -> None:
        if rv.passing_tenor is None:
            super().reject(rv)
        else:
            self.call("reject_loan", app_id=rv.app_id, reason="Risk too high for the price.")
