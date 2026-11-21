"""Scripted bots (no model calls)."""

from .base import Bot, run_bot
from .cheater import CheaterBot
from .honest import HonestBot

BOTS: dict[str, type] = {"honest": HonestBot, "cheater": CheaterBot}

__all__ = ["BOTS", "Bot", "run_bot"]
