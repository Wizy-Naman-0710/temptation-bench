"""Append-only double-entry ledger. Amounts are int {cents}; debit > 0, credit < 0."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .money import Money

CASH = 1000
LOANS = 1100  # principal outstanding (sub-ledger: sum of book.outstanding)
INTEREST_RECEIVABLE = 1150  # accrued interest not yet settled by an instalment (proposal)
ALLOWANCE = 1190
DEPOSITS = 2000
EQUITY = 3000
INTEREST_INCOME = 4000
DEPOSIT_MARGIN = 4100  # constant FTP credit on the fixed deposit base (proposal)
FUNDING_COST = 5000
PROVISION_EXPENSE = 5100
WRITE_OFF_EXPENSE = 5200
EXTERNAL = 9000
ACCOUNTS = frozenset(
    {
        CASH,
        LOANS,
        INTEREST_RECEIVABLE,
        ALLOWANCE,
        DEPOSITS,
        EQUITY,
        INTEREST_INCOME,
        DEPOSIT_MARGIN,
        FUNDING_COST,
        PROVISION_EXPENSE,
        WRITE_OFF_EXPENSE,
        EXTERNAL,
    }
)


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    id: int
    event_seq: int
    lines: tuple[tuple[int, Money], ...]
    memo: str


class Ledger:
    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._balances: dict[int, Money] = {a: 0 for a in ACCOUNTS}

    def post(self, lines: list[tuple[int, Money]], *, event_seq: int, memo: str) -> LedgerEntry:
        if not lines:
            raise ValueError("empty posting")
        for acct, amt in lines:
            if acct not in ACCOUNTS:
                raise ValueError(f"unknown account {acct}")
            if isinstance(amt, bool) or not isinstance(amt, int):
                raise ValueError("amounts must be int cents")
        if sum(a for _, a in lines) != 0:
            raise ValueError("unbalanced posting")
        e = LedgerEntry(len(self._entries), event_seq, tuple((a, m) for a, m in lines), memo)
        self._entries.append(e)
        for acct, amt in lines:
            self._balances[acct] += amt
        return e

    def balance(self, account: int) -> Money:
        return self._balances[account]

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._entries)

    def prefix_hash(self, n: int) -> str:
        h = hashlib.sha256()
        for e in self._entries[:n]:
            h.update(json.dumps([e.id, e.event_seq, e.lines, e.memo]).encode())
        return h.hexdigest()
