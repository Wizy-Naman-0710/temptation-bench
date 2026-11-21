"""Notes and reminders (DD §8, spec P2): engine-side, deterministic, size-capped."""

from __future__ import annotations

from ..calendar import clock_str
from ..model import DecisionContext, Refusal
from ..world import World
from .table import check_text

REMINDER_MAX = 200


def _notes_used(world: World) -> int:
    return sum(len(n["text"]) for n in world.notes)


def write_note(world: World, ctx: DecisionContext, text: str) -> str:
    text = check_text("text", text, int(world.config.caps["notes_chars"]))
    cap = int(world.config.caps["notes_chars"])
    used = _notes_used(world)
    if used + len(text) > cap:
        raise Refusal(
            f"Notes are full: {used:,} of {cap:,} characters used; this note needs {len(text):,}."
        )
    world.notes.append({"day": world.day, "minute": world.minute, "text": text})
    return f"Note saved ({used + len(text):,} of {cap:,} characters used)."


def read_notes(world: World, ctx: DecisionContext) -> str:
    """Oldest first. If the list would pass the output cap, the oldest notes are left out."""
    if not world.notes:
        return "No notes yet."
    budget = int(world.config.caps["output_chars"]) - 1000  # room for status and notices
    lines: list[str] = []
    size = 0
    for n in reversed(world.notes):
        line = f"[{clock_str(n['day'], n['minute'])}] {n['text']}"
        if size + len(line) + 1 > budget:
            break
        lines.append(line)
        size += len(line) + 1
    lines.reverse()
    hidden = len(world.notes) - len(lines)
    head = [f"+{hidden} older notes not shown"] if hidden else []
    return "\n".join(head + lines)


def set_reminder(world: World, ctx: DecisionContext, day: int, text: str) -> str:
    """Shown in the morning briefing of business day `day` (a later day, up to day 30)."""
    last = world.config.horizon_days
    if isinstance(day, bool) or not isinstance(day, int):
        raise Refusal("day must be a whole business day number, for example 8.")
    if not world.day < day <= last:
        raise Refusal(f"day must be a later business day, from {world.day + 1} to {last}.")
    text = check_text("text", text, REMINDER_MAX)
    cap = int(world.config.caps["open_reminders"])
    if sum(1 for r in world.reminders if r["due_day"] > world.day) >= cap:
        raise Refusal(f"You already have {cap} open reminders.")
    rid = f"R-{len(world.reminders) + 1}"
    world.reminders.append({"id": rid, "due_day": day, "text": text, "set_day": world.day})
    return f"Reminder set for day {day} ({clock_str(day, 0)[:14]})."
