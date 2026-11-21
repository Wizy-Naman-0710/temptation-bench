from __future__ import annotations

from ..calendar import clock_str
from ..model import DecisionContext, Refusal
from ..world import World


def list_emails(world: World, ctx: DecisionContext) -> str:
    box = world.inbox()
    if not box:
        return "Inbox is empty."
    rows = [
        f"{e.email_id}  {clock_str(e.day, e.minute)}  from {e.sender}  {e.subject}"
        + ("" if e.read else "  (unread)")
        for e in box
    ]
    return "\n".join(rows)


def read_email(world: World, ctx: DecisionContext, email_id: str) -> str:
    e = world.emails.get(str(email_id))
    if e is None or (e.day, e.minute) > (world.day, world.minute):
        raise Refusal(f"No email {email_id!r} in the inbox. Use list_emails to see ids.")
    e.read = True
    return f"From: {e.sender}\nSubject: {e.subject}\nDate: {clock_str(e.day, e.minute)}\n\n{e.body}"
