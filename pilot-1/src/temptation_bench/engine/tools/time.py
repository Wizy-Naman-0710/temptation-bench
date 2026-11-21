from __future__ import annotations

from ..model import DecisionContext
from ..world import World


def wait_for_next_day(world: World, ctx: DecisionContext) -> str:
    # The Branch performs the day roll; this returns the line shown before the briefing.
    return "The branch closes for the day."
