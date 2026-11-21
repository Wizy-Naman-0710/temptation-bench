"""People backend seam (spec §5): who writes the prose of the few exogenous texts.

Only V1's C3 gift note and T1's D8 "any news?" email go through `compose` (plus, later,
ordinary purposes). Every agent-dependent text, the D3 bribe-slot email, the boss emails
and all notices are template-only and never reach a backend. `ProsePeople` (Task 26) looks
up pre-generated text and falls back to the draft.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PeopleBackend(Protocol):
    def compose(self, person: str, msg_key: str, facts: dict[str, Any], draft: str) -> str:
        """Return the text `person` sends for `msg_key`. `facts` are the numbers, dates and
        ids that must appear verbatim; `draft` is the template text."""
        ...


class TemplatePeople:
    """Template text, unchanged (tests, bots and `people = "template"`)."""

    name = "template"

    def compose(self, person: str, msg_key: str, facts: dict[str, Any], draft: str) -> str:
        return draft
