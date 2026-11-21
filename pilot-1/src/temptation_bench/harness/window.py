"""Tracks what is still inside the model's input window (stub until Task 22)."""

from __future__ import annotations

from ..engine.model import DecisionContext


class WindowTracker:
    def context(self, kind_key: str = "") -> DecisionContext:
        return DecisionContext.PERFECT
