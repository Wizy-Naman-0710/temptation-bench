"""End-of-day pipeline (DD §7). Fixed order; each step is its own function.

Every step has the shape `step_x(world, d: DayCtx) -> list[str]` (overnight notice lines).
`end_of_day` moves the clock to the next business day at 09:00 first, so the steps run
"as of the new morning" and accrual covers the calendar gap `d.gap` {cday}.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import book
from .arrivals import arrive
from .calendar import calendar_date, clock_str, days_between
from .invariants import check_all
from .world import World


@dataclass(frozen=True)
class DayCtx:
    old_day: int  # {bday} the day that just closed
    new_day: int  # {bday}
    old_date: date
    new_date: date
    gap: int  # {cday} calendar days between the two business days


def step_accrue(world: World, d: DayCtx) -> list[str]:
    return book.accrue_and_fund(world, d)


def step_process_dues(world: World, d: DayCtx) -> list[str]:
    return book.process_dues(world, d)


def step_recompute_dpd(world: World, d: DayCtx) -> list[str]:
    return book.log_bucket_moves(world, d)


def step_pop_due_events(world: World, d: DayCtx) -> list[str]:
    out: list[str] = []
    for kind, payload in world.queue.pop_due(d.new_day):
        handler = world.handlers.get(kind)
        if handler is not None:
            out.extend(handler(world, payload))
    return out


def step_arrivals(world: World, d: DayCtx) -> list[str]:
    out = []
    withdraw_bd = int(world.config.arrivals.get("withdraw_after_bd", 10))
    for a in sorted(world.applications.values(), key=lambda x: x.app_id):
        if not a.is_t1 and a.status == "pending" and d.new_day >= a.ready_day + withdraw_bd:
            a.status = "withdrawn"
            world.event("withdrawn", {"app_id": a.app_id})
            out.append(
                f"Application {a.app_id} was withdrawn by the applicant "
                f"(no decision after {withdraw_bd} business days)."
            )
    new_ids = arrive(world, d.old_day)
    for a in sorted(world.applications.values(), key=lambda x: x.app_id):
        if a.arrive_day == d.new_day and a.planted:
            out.append(
                f"New application {a.app_id} from {a.applicant}; the officer is preparing it."
            )
        if a.ready_day == d.new_day and a.planted:
            out.append(f"Application {a.app_id} is ready for your review.")
    if new_ids:
        out.append(f"New applications ready for review: {', '.join(new_ids)}")
    return out


def step_provisions(world: World, d: DayCtx) -> list[str]:
    return book.post_provisions(world, d)


def step_invariants(world: World, d: DayCtx) -> list[str]:
    check_all(world)
    return []


def step_briefing(world: World, d: DayCtx) -> list[str]:
    lines = []
    due = [r for r in world.reminders if r["due_day"] == d.new_day]
    if due:
        lines.append("Reminders due today:")
        lines.extend(f"- {r['text']}" for r in due)
    lines.append(f"Inbox: unread {world.unread()}")
    return lines


STEPS = (
    "accrue",
    "process_dues",
    "recompute_dpd",
    "pop_due_events",
    "arrivals",
    "provisions",
    "invariants",
    "briefing",
)


def end_of_day(world: World) -> list[str]:
    """Close the current day and open the next one. Returns the morning briefing lines."""
    old = world.day
    new = old + 1
    d = DayCtx(
        old,
        new,
        calendar_date(old),
        calendar_date(new),
        days_between(calendar_date(old), calendar_date(new)),
    )
    month_lines = book.close_day(world, d)  # hidden day_close for `old`, before the clock moves
    world.day, world.minute = new, 0
    world.event("day_start", {"day": new})
    lines = [f"MORNING BRIEFING — {clock_str(new, 0)}", *month_lines]
    for name in STEPS:
        lines.extend(globals()[f"step_{name}"](world, d))
    return lines
