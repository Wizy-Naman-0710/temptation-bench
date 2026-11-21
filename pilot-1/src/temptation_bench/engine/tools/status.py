from __future__ import annotations

from ..model import DecisionContext
from ..money import fmt, fmt_whole
from ..world import World


def get_status(world: World, ctx: DecisionContext) -> str:
    c = world.config
    pending = [a for a in world.visible_apps() if a.status == "pending"]
    lines = [
        f"Branch 014 status — day {world.day} of {c.horizon_days}",
        f"Cash: {fmt(world.cash)}",
        f"Campaign lending: {fmt_whole(world.campaign)} of "
        f"{fmt_whole(c.campaign['target'])} target",
        f"Applications pending: {len(pending)}",
        f"Unread emails: {world.unread()}",
        c.texts["pay_line"],
    ]
    return "\n".join(lines)
