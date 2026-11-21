"""Tool registry. Each tool is `fn(world, ctx, **kw) -> str`; it raises Refusal on bad input."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..model import DecisionContext
from ..world import World

ToolFn = Callable[..., str]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    minutes: int  # {min}; -1 = jump to next day
    fn: ToolFn
    decision: bool = False


def _build() -> dict[str, ToolSpec]:
    from . import applications, decisions, email, status, time

    fns: list[tuple[str, ToolFn, bool]] = [
        ("get_status", status.get_status, False),
        ("list_applications", applications.list_applications, False),
        ("list_emails", email.list_emails, False),
        ("read_email", email.read_email, False),
        ("review_application", applications.review_application, False),
        ("approve_loan", decisions.approve_loan, True),
        ("reject_loan", decisions.reject_loan, True),
        ("wait_for_next_day", time.wait_for_next_day, False),
    ]
    return {n: ToolSpec(n, 0, f, d) for n, f, d in fns}


TOOLS: dict[str, ToolSpec] = _build()

__all__ = ["TOOLS", "ToolSpec", "DecisionContext", "World"]
