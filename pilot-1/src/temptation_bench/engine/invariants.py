"""Accounting invariants (DD §7). check_all raises InvariantError on the first failure."""

from __future__ import annotations

from .ledger import ACCOUNTS, Ledger


class InvariantError(AssertionError):
    def __init__(self, name: str, detail: str) -> None:
        super().__init__(f"{name}: {detail}")
        self.name = name
        self.detail = detail


def check_ledger(led: Ledger) -> None:
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
    for a in ACCOUNTS:  # replay = live
        if replay[a] != led.balance(a):
            raise InvariantError("I3", f"account {a} replay {replay[a]} != live {led.balance(a)}")


def check_all(world) -> None:
    check_ledger(world.ledger)
    if world.personal_benefits and any(  # I13
        e.memo.startswith("personal") for e in world.ledger.entries
    ):
        raise InvariantError("I13", "personal benefit posted to branch ledger")
