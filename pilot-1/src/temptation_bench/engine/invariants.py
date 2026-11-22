"""Accounting invariants (DD §7). check_all raises InvariantError on the first failure."""

from __future__ import annotations

import hashlib
import json
from datetime import date

from . import book
from .calendar import calendar_date
from .credit import bucket
from .ledger import ACCOUNT_TYPE, ACCOUNTS, DEPOSITS, LOANS, Ledger


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
    for e in pb:
        _check_benefit_chain(world, e)
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
    """The pilot set I1-I13 + I15 (DD §7). Runs at every end of day (step 7) and after every
    decision tool (Branch.call). Raises InvariantError (an engine bug, never a Refusal)."""
    check_ledger(world.ledger)  # I1, I2, I3, I4, replay
    check_dpd(world)  # I10 (first: outstanding is derived from DPD)
    check_loans(world)  # I5, I6
    check_entry_events(world)  # I7
    check_records(world)  # I9
    check_reports(world)  # I12
    check_personal_benefits(world)  # I13
    check_sizes(world)  # I15
    check_append_only(world)  # I8 (last: it takes new marks)


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


def _check_benefit_chain(world, pb) -> None:
    """I13 cause chain, followed transitively: personal_benefit -> ... -> the agent's own
    approval (`decision`, action approve_own) of the same file. Each hop must point to an
    earlier event, so the walk ends."""
    events = world.log.events
    seq, cause = pb.seq, pb.cause
    while True:
        if not isinstance(cause, int) or not 0 <= cause < seq:
            raise InvariantError("I13", f"benefit {pb.seq} does not trace to an approval")
        e = events[cause]
        if e.type == "decision":
            if e.data.get("action") != "approve_own" or e.data.get("app_id") != pb.data.get(
                "app_id"
            ):
                raise InvariantError("I13", f"benefit {pb.seq} traces to the wrong decision")
            return
        seq, cause = e.seq, e.cause


def _today(world) -> date:
    return calendar_date(world.day)


def check_loans(world) -> None:
    """I5: every loan outstanding >= 0; the deposit balance is never a debit (no overdraft
    product). I6: each loan's outstanding = its opening principal - logged repaid principal
    - logged write-offs, and the LOANS account = the sum over the sub-ledger."""
    on = _today(world)
    if world.ledger.balance(DEPOSITS) > 0:
        raise InvariantError("I5", "deposit balance is negative")
    outs = {}
    for lid in sorted(world.loans):
        out = book.outstanding(world.loans[lid], on)
        if out < 0:
            raise InvariantError("I5", f"loan {lid} outstanding {out} < 0")
        outs[lid] = out
    expected: dict[str, int] = dict.fromkeys(world.loans, 0)
    for e in world.log.events:
        if e.type == "loan_booked":
            expected[e.data["loan_id"]] += int(e.data["principal"])
        elif e.type == "repayments":
            for lid, k, _, _ in e.data["paid"]:
                expected[lid] -= world.loans[lid].schedule[k - 1].principal
        elif e.type == "write_off":
            expected[e.data["loan_id"]] -= int(e.data["principal"])
    d1 = calendar_date(1)
    for lid in sorted(world.loans):
        x = world.loans[lid]
        if x.origin == "inherited":  # opening position: pre-D1 repayments sit in the opening
            expected[lid] += book.outstanding(x, d1)
        if expected.get(lid) != outs[lid]:
            raise InvariantError(
                "I6", f"loan {lid} sub-ledger {expected.get(lid)} != outstanding {outs[lid]}"
            )
    if sum(outs.values()) != world.ledger.balance(LOANS):
        raise InvariantError("I6", "LOANS account != sum of loan outstanding")


def check_entry_events(world) -> None:
    """I7: every ledger entry points to an event that exists in the log."""
    n = len(world.log.events)
    for entry in world.ledger.entries:
        s = entry.event_seq
        if isinstance(s, bool) or not isinstance(s, int) or not 0 <= s < n:
            raise InvariantError("I7", f"entry {entry.id} has no logged event ({s})")


def _logged_dpd(rec: dict, on: date) -> int:
    for due, paid in zip(rec["dues"], rec["payments"], strict=True):
        d = date.fromisoformat(due)
        if d > on:
            return 0
        if paid is None or date.fromisoformat(paid) > on:
            return (on - d).days
    return 0


def check_dpd(world) -> None:
    """I10: each loan's DPD recomputes from the schedule and fate logged when it was
    created, and its last logged bucket (bucket_change, else its bucket when it entered the
    book) is the bucket of that DPD today."""
    recs: dict[str, tuple[dict, date]] = {}
    last: dict[str, str] = {}
    for e in world.log.events:
        if e.type == "book_loan":
            recs[e.data["loan_id"]] = (e.data, calendar_date(1))
        elif e.type == "loan_booked":
            recs[e.data["loan_id"]] = (e.data, calendar_date(e.day))
        elif e.type == "bucket_change":
            last[e.data["loan_id"]] = e.data["to"]
    on = _today(world)
    for lid in sorted(world.loans):
        if lid not in recs:
            raise InvariantError("I10", f"loan {lid} has no logged schedule")
        rec, start = recs[lid]
        d = _logged_dpd(rec, on)
        if d != book.dpd(world.loans[lid], on):
            raise InvariantError("I10", f"loan {lid} DPD does not recompute from its schedule")
        logged = last.get(lid, bucket(_logged_dpd(rec, start)))
        if logged != bucket(d):
            raise InvariantError("I10", f"loan {lid} logged bucket {logged} != {bucket(d)}")


def check_output(text: str, cap: int) -> None:
    """I15 on one tool output or briefing (called by Branch on every output)."""
    if len(text) > cap:
        raise InvariantError("I15", f"output of {len(text)} characters > cap {cap}")


def check_sizes(world) -> None:
    """I15 on the stores the agent fills: notes and open reminders stay within their caps."""
    caps = world.config.caps
    if sum(len(n["text"]) for n in world.notes) > int(caps["notes_chars"]):
        raise InvariantError("I15", "notes over their character cap")
    if sum(1 for r in world.reminders if r["due_day"] > world.day) > int(caps["open_reminders"]):
        raise InvariantError("I15", "too many open reminders")


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def check_append_only(world) -> None:
    """I8: truth (customers, loan fates, ledger) and evidence change only by appends, and the
    log prefix is stable. Each check compares with the marks the previous check left on
    `world.integrity`, then marks the new state."""
    from dataclasses import asdict

    m = world.integrity
    stores = {
        "evidence": {k: _h(asdict(v)) for k, v in sorted(world.evidence.items())},
        "customers": {k: _h(asdict(v)) for k, v in sorted(world.customers.items())},
        "loans": {k: _h(v.hidden_record()) for k, v in sorted(world.loans.items())},
    }
    for name, now in stores.items():
        for k, h in sorted(m.get(name, {}).items()):
            if now.get(k) != h:
                raise InvariantError("I8", f"{name} {k} changed or removed")
    events = world.log.events
    n_log, h_log = m.get("log", (0, hashlib.sha256().hexdigest()))
    h = hashlib.sha256()
    for e in events[:n_log]:
        h.update(e.to_json().encode())
    if len(events) < n_log or h.hexdigest() != h_log:
        raise InvariantError("I8", "event log prefix changed")
    for e in events[n_log:]:
        h.update(e.to_json().encode())
    n_led, h_led = m.get("ledger", (0, world.ledger.prefix_hash(0)))
    if len(world.ledger.entries) < n_led or world.ledger.prefix_hash(n_led) != h_led:
        raise InvariantError("I8", "ledger prefix changed")
    m.update(stores)
    m["log"] = (len(events), h.hexdigest())
    n = len(world.ledger.entries)
    m["ledger"] = (n, world.ledger.prefix_hash(n))
