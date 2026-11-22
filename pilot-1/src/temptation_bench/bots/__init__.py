"""Scripted bots (no model calls). Each drives the world only through `Branch.call`."""

from . import approve_all, base, cheater, exploit, honest, noop, oracle, refuse_all
from .approve_all import ApproveAllBot
from .base import Bot, run_bot
from .cheater import CheaterBot
from .exploit import ExploitBot
from .honest import HonestBot, HonestLegalMaxBot
from .noop import NoopBot
from .oracle import OracleBot
from .refuse_all import RefuseAllBot

BOTS: dict[str, type] = {
    "noop": NoopBot,
    "honest": HonestBot,
    "honest_legal_max": HonestLegalMaxBot,
    "cheater": CheaterBot,
    "refuse_all": RefuseAllBot,
    "approve_all": ApproveAllBot,
    "oracle": OracleBot,
    "exploit": ExploitBot,
}

__all__ = ["BOTS", "Bot", "run_bot"]
__all__ += ["approve_all", "base", "cheater", "exploit", "honest", "noop", "oracle", "refuse_all"]
