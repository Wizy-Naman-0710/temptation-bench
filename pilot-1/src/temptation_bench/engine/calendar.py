"""Sim calendar: D1 = Mon 2027-03-01, business days only, no holidays."""

from __future__ import annotations

from datetime import date, timedelta

START = date(2027, 3, 1)
DAY_START_MIN = 9 * 60  # {min} 09:00


def date_of(day: int) -> date:
    """Business day number {bday} (1-based) -> calendar date."""
    if day < 1:
        raise ValueError("day starts at 1")
    weeks, rem = divmod(day - 1, 5)
    return START + timedelta(days=7 * weeks + rem)


def clock_str(day: int, minute: int) -> str:
    """(day {bday}, minute {min} since 09:00) -> "Wed 2027-03-03 10:45"."""
    d = date_of(day)
    t = DAY_START_MIN + minute
    return f"{d.strftime('%a')} {d.isoformat()} {t // 60:02d}:{t % 60:02d}"
