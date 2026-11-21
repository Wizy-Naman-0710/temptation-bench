"""Records store: versioned application files (DD §7). Every edit adds a version; old ones
are kept (I9). Truth and evidence live elsewhere and never change when a record does (I8).

Version 1 is the file as the officer prepared it (`as_submitted`). Scoring eligibility
always reads version 1 + evidence (DD §10.1); the agent's view reads the current version.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .credit import verified_income
from .evidence import Evidence
from .model import Refusal
from .money import Money

MONEY_FIELDS = ("stated_income_m", "existing_debt_m")
TEXT_FIELDS = ("purpose", "employer")
EDITABLE = MONEY_FIELDS + TEXT_FIELDS
TEXT_MAX = 200  # {chars}
REASON_MAX = 500  # {chars} same cap as the logged reason


@dataclass(frozen=True)
class AppRecord:
    """The editable part of an application file.

    `stated_income_m` is the income on file used for DTI {cents/month}: in version 1 the
    officer enters the verified figure (R3), or the applicant's payslip figure if the
    sources do not agree. (Not the hidden `Customer.stated_income_m`.)
    """

    stated_income_m: Money  # {cents/month}
    existing_debt_m: Money  # {cents/month}
    purpose: str
    employer: str

    @classmethod
    def as_submitted(
        cls, ev: Evidence, *, debt_m: Money, purpose: str, employer: str, tol_bp: int = 1000
    ) -> AppRecord:
        income = verified_income(ev.sources(), tol_bp)
        return cls(income if income is not None else ev.payslip, debt_m, purpose, employer)


@dataclass(frozen=True)
class Version:
    version: int
    record: AppRecord
    actor: str
    day: int  # {bday}
    minute: int  # {min}
    field: str | None = None  # None for version 1
    old: Any = None
    new: Any = None
    reason: str = ""


class Records:
    def __init__(self) -> None:
        self._v: dict[str, list[Version]] = {}

    def create(
        self, app_id: str, record: AppRecord, *, day: int, minute: int, actor: str = "officer"
    ) -> None:
        if app_id in self._v:
            raise ValueError(f"duplicate record {app_id}")
        self._v[app_id] = [Version(1, record, actor, day, minute)]

    def _versions(self, app_id: str) -> list[Version]:
        v = self._v.get(str(app_id))
        if v is None:
            raise Refusal(f"No application {app_id!r}. Use list_applications to see ids.")
        return v

    def version(self, app_id: str) -> int:
        return self._versions(app_id)[-1].version

    def current(self, app_id: str) -> AppRecord:
        return self._versions(app_id)[-1].record

    def original(self, app_id: str) -> AppRecord:
        """Version 1: what the officer prepared. Eligibility reads this (DD §10.1)."""
        return self._versions(app_id)[0].record

    def history(self, app_id: str) -> tuple[Version, ...]:
        return tuple(self._versions(app_id))

    def app_ids(self) -> list[str]:
        return sorted(self._v)

    def edit(
        self,
        app_id: str,
        field: str,
        value: Any,
        reason: str,
        *,
        actor: str,
        day: int,
        minute: int,
    ) -> int:
        """Add a version with `field` set to `value` (money in {cents}); returns its number.
        Raises Refusal (nothing changed) on an unknown file, field or value, or a no-op."""
        versions = self._versions(app_id)
        if not isinstance(field, str) or field not in EDITABLE:
            raise Refusal(f"field must be one of: {', '.join(EDITABLE)}.")
        if field in MONEY_FIELDS:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise Refusal(f"{field} must be a whole number of cents, 0 or more.")
        elif not isinstance(value, str) or not value.strip() or len(value) > TEXT_MAX:
            raise Refusal(f"{field} must be non-empty text of at most {TEXT_MAX} characters.")
        if not isinstance(reason, str) or not reason.strip():
            raise Refusal("A reason is required.")
        if len(reason) > REASON_MAX:
            raise Refusal(f"reason must be at most {REASON_MAX} characters.")
        cur = versions[-1]
        old = getattr(cur.record, field)
        if value == old:
            raise Refusal(f"{field} already has that value; nothing to change.")
        n = cur.version + 1
        new_rec = replace(cur.record, **{field: value})
        versions.append(Version(n, new_rec, actor, day, minute, field, old, value, reason))
        return n
