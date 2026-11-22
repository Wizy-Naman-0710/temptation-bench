"""Tracks which tool results are still inside the model's input window (DD §9, M1).

The loop calls `observe` after each tool round (records successful outputs) and `update`
with the compacted input right before each generate. `context` turns that into the plain
bools the engine logs with a decision or a filed report."""

from __future__ import annotations

from typing import Literal

from inspect_ai.model import ChatMessage, ChatMessageAssistant, ChatMessageTool

from ..engine.model import DecisionContext

Kind = Literal["review", "portfolio", "email"]
PORTFOLIO_KEY = "portfolio"


def _kind_key(function: str, arguments: dict) -> tuple[Kind, str] | None:
    if function == "review_application":
        return "review", str(arguments.get("app_id", ""))
    if function == "get_portfolio_report":
        return "portfolio", PORTFOLIO_KEY
    if function == "read_email":
        return "email", str(arguments.get("email_id", ""))
    return None


class WindowTracker:
    def __init__(self, offer_email_id: str = "E-0003") -> None:
        self._offer_email_id = offer_email_id
        self._latest: dict[tuple[Kind, str], str] = {}  # (kind, key) -> tool_call_id
        self._visible: set[str] = set()  # tool_call_ids in the last input sent

    def record(self, tool_call_id: str, kind: Kind, key: str) -> None:
        """A successful output of `kind` for `key` came back as tool message `tool_call_id`."""
        self._latest[(kind, key)] = tool_call_id

    def observe(self, assistant: ChatMessageAssistant, results: list[ChatMessage]) -> None:
        """Record the successful (non-refused) results of one tool round."""
        calls = {c.id: c for c in assistant.tool_calls or []}
        for m in results:
            if not isinstance(m, ChatMessageTool) or m.error is not None:
                continue
            call = calls.get(m.tool_call_id or "")
            kk = _kind_key(call.function, call.arguments) if call else None
            if kk is not None:
                self.record(call.id, *kk)

    def update(self, input_messages: list[ChatMessage]) -> None:
        """The (compacted) input about to be sent to the model."""
        self._visible = {
            m.tool_call_id
            for m in input_messages
            if isinstance(m, ChatMessageTool) and m.tool_call_id
        }

    def _in_window(self, kind: Kind, key: str) -> bool:
        call_id = self._latest.get((kind, key))
        return call_id is not None and call_id in self._visible

    def context(self, app_id: str | None = None) -> DecisionContext:
        return DecisionContext(
            latest_review_in_window=bool(app_id) and self._in_window("review", str(app_id)),
            latest_portfolio_in_window=self._in_window("portfolio", PORTFOLIO_KEY),
            offer_email_in_window=self._in_window("email", self._offer_email_id),
        )
