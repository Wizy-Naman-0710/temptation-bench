"""Accounting invariants (DD §7). check_all raises InvariantError on the first failure."""

from __future__ import annotations

from .ledger import ACCOUNT_TYPE, ACCOUNTS, Ledger


class InvariantError(AssertionError):
    def __init__(self, name: str, detail: str) -> None:
        super().__init__(f"{name}: {detail}")
        self.name = name
        self.detail = detail


def check_ledger(led: Ledger) -> None:
    """I1, I4, I2, the journal replay check and I3 on the live ledger."""
    replay = {a: 0 for a in ACCOUNTS}
    for e in led.entries:
        if sum(m for _, m in e.lines) != 0:  # I1
            raise InvariantError("I1", f"entry {e.id} unbalanced")
        for acct, amt in e.lines:
            if isinstance(amt, bool) or not isinstance(amt, int):  # I4
                raise InvariantError("I4", f"entry {e.id} non-int amount")
            replay[acct] += amt
    if sum(replay.values()) != 0:  # I2
        raise InvariantError("I2", "balances do not sum to 0")
    for a in sorted(ACCOUNTS):  # journal replay = live balances (integrity note §6)
        if replay[a] != led.balance(a):
            raise InvariantError(
                "ledger_replay", f"account {a} replay {replay[a]} != live {led.balance(a)}"
            )
    check_balance_sheet(led)


def check_balance_sheet(led: Ledger) -> None:
    """I3: Assets = Liabilities + Equity + (Income − Expenses), on live balances.

    Balances are signed (debit > 0), so liabilities, equity and income are negated. With
    I1 this also means nothing is parked in the 9000 boundary account.
    """
    by_type: dict[str, int] = {}
    for a in sorted(ACCOUNTS):
        t = ACCOUNT_TYPE[a]
        by_type[t] = by_type.get(t, 0) + led.balance(a)
    assets = by_type.get("asset", 0)
    rhs = (
        -by_type.get("liability", 0)
        - by_type.get("equity", 0)
        + (-by_type.get("income", 0) - by_type.get("expense", 0))
    )
    if assets != rhs:
        raise InvariantError("I3", f"assets {assets} != L + E + (I - X) {rhs}")


def check_personal_benefits(world) -> None:
    """I13: bribes / personal benefits never touch the branch ledger.

    No ledger entry may be caused by a `personal_benefit` event, and the off-ledger total
    must equal the sum of those events (so it is never netted against an account).
    """
    pb = [e for e in world.log.events if e.type == "personal_benefit"]
    seqs = {e.seq for e in pb}
    for entry in world.ledger.entries:
        if entry.event_seq in seqs:
            raise InvariantError("I13", f"entry {entry.id} linked to a personal benefit")
    total = sum(int(e.data["amount"]) for e in pb)
    if world.personal_benefits != total:
        raise InvariantError(
            "I13", f"personal_benefits {world.personal_benefits} != logged {total}"
        )


def check_records(world) -> None:
    """I9: every record version has a log event (version 1 = `application_created`,
    every later version = one `record_edit` with that version number)."""
    created = {e.data["app_id"] for e in world.log.events if e.type == "application_created"}
    edits: dict[str, list[int]] = {}
    for e in world.log.events:
        if e.type == "record_edit":
            edits.setdefault(e.data["app_id"], []).append(int(e.data["version"]))
    for app_id in world.records.app_ids():
        n = world.records.version(app_id)
        if app_id not in created or edits.get(app_id, []) != list(range(2, n + 1)):
            raise InvariantError("I9", f"record {app_id} versions do not match the log")


def check_all(world) -> None:
    check_ledger(world.ledger)
    check_personal_benefits(world)
    check_records(world)
    check_reports(world)


def check_reports(world) -> None:
    """I12: filed reports are frozen. Each stored report equals what its `report_filed`
    event recorded at filing time, in filing order, and none was added or removed."""
    filed = [e.data for e in world.log.events if e.type == "report_filed"]
    if len(filed) != len(world.reports):
        raise InvariantError("I12", "number of filed reports does not match the log")
    for rep, ev in zip(world.reports, filed, strict=True):
        if (
            rep.report_id != ev["report_id"]
            or rep.csv != ev["csv"]
            or dict(rep.values) != ev["reported"]
            or rep.cutoff_day != ev["cutoff_day"]
            or world.report_truth.get(rep.report_id) != ev["truth"]
        ):
            raise InvariantError("I12", f"report {rep.report_id} changed after filing")
