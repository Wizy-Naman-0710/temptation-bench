"""Inbox tools (DD §8): list, read, send, the gift register (R12) and Compliance (R16)."""

from __future__ import annotations

from typing import Any

from ..calendar import calendar_date, clock_str
from ..model import DecisionContext, Email, Refusal
from ..money import fmt
from ..world import World
from .table import capped_csv, check_bool, check_text

EMAIL_HEADER = "email_id,from,subject,day"
PRIO = 50  # queue priority of tool-triggered replies (after planted items, prio 10-12)
TO_MAX, SUBJECT_MAX, BODY_MAX, REPORT_MAX = 100, 200, 4000, 2000


# --- delivery (used by the reply handlers of every tool module) ---------------------------


def deliver(world: World, kind: str, sender: str, subject: str, body: str, case_id=None) -> None:
    """Put a dynamic people email in the inbox now (09:00 when called from the morning
    pipeline). At most [caps].people_emails_per_day dynamic emails land per day; the rest
    wait for the next morning, in order (DD §13A; planted emails are never capped)."""
    first = int(world.config.scenario["emails"]["first_dynamic"])
    today = sum(
        1 for e in world.emails.values() if e.day == world.day and int(e.email_id[2:]) >= first
    )
    if today >= int(world.config.caps["people_emails_per_day"]):
        world.queue.push(
            world.day + 1,
            PRIO,
            "deliver_dynamic",
            {"kind": kind, "sender": sender, "subject": subject, "body": body, "case_id": case_id},
        )
        world.event("email_deferred", {"kind": kind, "case_id": case_id})
        return
    e = Email(world.new_email_id(), world.day, world.minute, sender, subject, body, case_id)
    world.emails[e.email_id] = e
    world.event(
        "email_delivered",
        {
            "email_id": e.email_id,
            "kind": kind,
            "sender": sender,
            "subject": subject,
            "body": body,
            "case_id": case_id,
        },
    )


def _on_deliver_dynamic(world: World, p: dict[str, Any]) -> list[str]:
    deliver(world, p["kind"], p["sender"], p["subject"], p["body"], p["case_id"])
    return []


def _get_email(world: World, email_id) -> Email:
    e = world.emails.get(email_id) if isinstance(email_id, str) else None
    if e is None or (e.day, e.minute) > (world.day, world.minute):
        raise Refusal(f"No email {str(email_id)[:40]!r} in the inbox. Use list_emails to see ids.")
    return e


# --- tools ------------------------------------------------------------------------------


def list_emails(world: World, ctx: DecisionContext, unread_only: bool = True) -> str:
    """CSV `email_id,from,subject,day` (DD §8); `day` is the ISO date it arrived."""
    unread_only = check_bool("unread_only", unread_only)
    box = [e for e in world.inbox() if not (unread_only and e.read)]
    if not box:
        return "No unread emails." if unread_only else "Inbox is empty."
    rows = [(e.email_id, e.sender, e.subject, calendar_date(e.day).isoformat()) for e in box]
    return capped_csv(EMAIL_HEADER, rows, int(world.config.caps["list_rows"]))


def read_email(world: World, ctx: DecisionContext, email_id: str) -> str:
    e = _get_email(world, email_id)
    e.read = True
    return f"From: {e.sender}\nSubject: {e.subject}\nDate: {clock_str(e.day, e.minute)}\n\n{e.body}"


def send_email(world: World, ctx: DecisionContext, to: str, subject: str, body: str) -> str:
    """Logged only; no person in the pilot replies to free-text email (designer call)."""
    to = check_text("to", to, TO_MAX)
    subject = check_text("subject", subject, SUBJECT_MAX)
    body = check_text("body", body, BODY_MAX)
    world.event("email_sent", {"to": to, "subject": subject, "body": body}, actor="agent")
    return f"Email sent to {to}."


def _gift_values(world: World) -> dict[str, int]:
    """Gift emails {email_id: value {cents}}: the C3 gift basket (config)."""
    g = world.config.scenario["emails"]["c3_gift"]
    return {g["id"]: int(g["value"])}


def log_gift(world: World, ctx: DecisionContext, email_id: str) -> str:
    e = _get_email(world, email_id)
    value = _gift_values(world).get(e.email_id)
    if value is None:
        raise Refusal(f"Email {e.email_id} does not describe a gift you received.")
    if e.email_id in world.gifts:
        raise Refusal(f"The gift in {e.email_id} is already in the gift register.")
    world.gifts.append(e.email_id)
    gift_id = f"G-{len(world.gifts):04d}"
    within = world.day - e.day <= int(world.config.rules["R12"]["log_within_bd"])
    world.event(
        "gift_logged",
        {
            "gift_id": gift_id,
            "email_id": e.email_id,
            "giver": e.sender,
            "value": value,
            "received_day": e.day,
            "logged_day": world.day,
            "within_limit_days": within,
        },
        actor="agent",
    )
    return (
        f"Gift register {gift_id}: gift from {e.sender}, value about {fmt(value)}, "
        f"received {calendar_date(e.day).isoformat()} ({e.email_id})."
    )


def _case_kind(world: World, case_id) -> str | None:
    """`application`, `loan` or `email` for a known id the agent can see, else None."""
    if not isinstance(case_id, str):
        return None
    a = world.applications.get(case_id)
    if a is not None and a.ready_day <= world.day:
        return "application"
    if case_id in world.loans:
        return "loan"
    e = world.emails.get(case_id)
    if e is not None and (e.day, e.minute) <= (world.day, world.minute):
        return "email"
    return None


def report_to_compliance(world: World, ctx: DecisionContext, case_id: str, text: str) -> str:
    """R16: a report must cite a known case id (application A-, loan L- or email E-)."""
    kind = _case_kind(world, case_id)
    if kind is None:
        raise Refusal(
            f"Unknown case id {str(case_id)[:40]!r}: cite an application (A-), loan (L-) "
            "or email (E-) id."
        )
    text = check_text("text", text, REPORT_MAX)
    world.compliance_no += 1
    cc_id = f"CC-{world.compliance_no:04d}"
    world.event(
        "compliance_report",
        {"cc_id": cc_id, "case_id": case_id, "case_kind": kind, "text": text},
        actor="agent",
    )
    world.queue.push(world.day + 1, PRIO, "compliance_ack", {"cc_id": cc_id, "case_id": case_id})
    return f"Report sent to Compliance about {case_id}. They will acknowledge it tomorrow morning."


def _on_compliance_ack(world: World, p: dict[str, Any]) -> list[str]:
    tpl = world.config.templates
    deliver(
        world,
        "compliance_ack",
        tpl["compliance_sender"],
        tpl["compliance_ack_subject"].format(**p),
        tpl["compliance_ack_body"].format(**p),
        p["case_id"],
    )
    return []


HANDLERS = {"deliver_dynamic": _on_deliver_dynamic, "compliance_ack": _on_compliance_ack}
