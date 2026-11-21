"""Tool registry. Each tool is `fn(world, ctx, **kw) -> str`; it raises Refusal on bad input."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..model import DecisionContext
from ..world import World

ToolFn = Callable[..., str]


@dataclass(frozen=True)
class ToolSpec:
    """A registered tool. Its clock cost lives only in configs/world.toml [minutes]."""

    name: str
    fn: ToolFn
    decision: bool = False


def _build() -> dict[str, ToolSpec]:
    from . import applications, decisions, email, memory, reports, status, time

    fns: list[tuple[str, ToolFn, bool]] = [
        ("get_status", status.get_status, False),
        ("list_applications", applications.list_applications, False),
        ("list_emails", email.list_emails, False),
        ("read_email", email.read_email, False),
        ("review_application", applications.review_application, False),
        ("edit_application", applications.edit_application, False),
        ("approve_loan", decisions.approve_loan, True),
        ("reject_loan", decisions.reject_loan, True),
        ("escalate_to_rcc", decisions.escalate_to_rcc, True),
        ("get_portfolio_report", reports.get_portfolio_report, False),
        ("file_report", reports.file_report, True),
        ("send_email", email.send_email, False),
        ("log_gift", email.log_gift, False),
        ("report_to_compliance", email.report_to_compliance, False),
        ("write_note", memory.write_note, False),
        ("read_notes", memory.read_notes, False),
        ("set_reminder", memory.set_reminder, False),
        ("wait_for_next_day", time.wait_for_next_day, False),
    ]
    return {n: ToolSpec(n, f, d) for n, f, d in fns}


TOOLS: dict[str, ToolSpec] = _build()


def _handlers() -> dict[str, Callable[..., list[str]]]:
    """Queue handlers for the replies tools schedule (RCC, Compliance, boss MIS reply)."""
    from . import decisions, email, reports

    return {**email.HANDLERS, **decisions.HANDLERS, **reports.HANDLERS}


HANDLERS = _handlers()

__all__ = ["HANDLERS", "TOOLS", "ToolSpec", "DecisionContext", "World"]
