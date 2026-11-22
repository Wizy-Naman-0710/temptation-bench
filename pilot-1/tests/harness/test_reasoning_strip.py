"""Task 30 fix ruling: before each generate (after compaction), the Anthropic route sends
`ContentReasoning` only on the most recent assistant message. Interleaved thinking with tool
use needs the latest assistant turn's thinking block (with its signature) replayed as is;
older ones are dropped. Other routes get the list unchanged. The stored conversation is never
edited: the stripped list is a new list of copies (same message ids)."""

from __future__ import annotations

import asyncio

from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    ContentReasoning,
    ContentText,
    ModelOutput,
)
from inspect_ai.tool import ToolCall

from temptation_bench import run
from temptation_bench.harness import agent
from temptation_bench.harness.routes import strip_old_reasoning
from temptation_bench.harness.window import WindowTracker

HAIKU = run.HAIKU


def _assistant(n: int) -> ChatMessageAssistant:
    return ChatMessageAssistant(
        content=[
            ContentReasoning(reasoning=f"thought {n}", signature=f"sig-{n}"),
            ContentText(text=f"step {n}"),
        ],
        tool_calls=[ToolCall(id=f"c{n}", function="get_portfolio_report", arguments={})],
    )


def scripted() -> list:
    msgs = [ChatMessageSystem(content="sys"), ChatMessageUser(content="start")]
    for n in (1, 2, 3):
        msgs.append(_assistant(n))
        msgs.append(ChatMessageTool(content=f"report {n}", tool_call_id=f"c{n}"))
    return msgs


def _reasoning(m) -> list[str]:
    if isinstance(m.content, str):
        return []
    return [c.reasoning for c in m.content if isinstance(c, ContentReasoning)]


def test_anthropic_route_keeps_reasoning_only_on_the_last_assistant_turn():
    msgs = scripted()
    out = strip_old_reasoning(msgs, HAIKU)
    asst = [m for m in out if isinstance(m, ChatMessageAssistant)]
    assert [_reasoning(m) for m in asst] == [[], [], ["thought 3"]]
    last = asst[-1].content[0]
    assert last.signature == "sig-3"  # replayed as is (signature kept)
    # text and tool calls of the stripped turns stay
    assert [m.text for m in asst] == ["step 1", "step 2", "step 3"]
    assert [m.tool_calls[0].id for m in asst] == ["c1", "c2", "c3"]
    # same message ids, same order, nothing else changed
    assert [m.id for m in out] == [m.id for m in msgs]
    assert [type(m) for m in out] == [type(m) for m in msgs]


def test_stored_conversation_is_not_mutated():
    msgs = scripted()
    before = [m.model_dump() for m in msgs]
    out = strip_old_reasoning(msgs, HAIKU)
    assert out is not msgs
    assert [m.model_dump() for m in msgs] == before


def test_other_routes_get_the_list_unchanged():
    for slug in (run.LUNA, "mockllm/model", "openai-api/xpl/qwen3.7-flash"):
        msgs = scripted()
        out = strip_old_reasoning(msgs, slug)
        assert [m.model_dump() for m in out] == [m.model_dump() for m in msgs]


def test_no_assistant_or_text_content_is_fine():
    msgs = [ChatMessageSystem(content="sys"), ChatMessageUser(content="hi")]
    assert strip_old_reasoning(msgs, HAIKU) == msgs
    plain = [*msgs, ChatMessageAssistant(content="a"), ChatMessageAssistant(content="b")]
    assert [m.model_dump() for m in strip_old_reasoning(plain, HAIKU)] == [
        m.model_dump() for m in plain
    ]


class _Model:
    def __init__(self, name: str) -> None:
        self.name, self.inputs = name, []

    def __str__(self) -> str:
        return self.name

    async def generate(self, input, **kw):
        self.inputs.append(list(input))
        return ModelOutput.from_content(model=self.name, content="ok")


class _Compact:
    """A trim: compact_input drops the oldest assistant turn and its tool result."""

    async def compact_input(self, messages, force=False):
        return [*messages[:2], *messages[4:]], None

    async def record_output(self, input, output):
        self.recorded = input


class _State:
    def __init__(self, messages):
        self.messages, self.output = messages, None


def _loop_once(monkeypatch, slug: str):
    model = _Model(slug)
    monkeypatch.setattr(agent, "get_model", lambda: model)
    window = WindowTracker()
    seen = []
    orig = window.update
    monkeypatch.setattr(window, "update", lambda inp: (seen.append(list(inp)), orig(inp)))
    state = _State(scripted())
    stored = [m.model_dump() for m in state.messages]
    asyncio.run(agent._generate(state, _Compact(), window, [], None))
    return model, seen, state, stored


def test_loop_sends_the_stripped_list_on_the_anthropic_route(monkeypatch):
    model, seen, state, stored = _loop_once(monkeypatch, HAIKU)
    sent = model.inputs[0]
    asst = [m for m in sent if isinstance(m, ChatMessageAssistant)]
    # stripped after compaction: the trimmed input has turns 2 and 3 only
    assert [m.text for m in asst] == ["step 2", "step 3"]
    assert [_reasoning(m) for m in asst] == [[], ["thought 3"]]
    assert seen == [sent]  # the window tracker sees exactly what was sent
    # stored conversation keeps every reasoning block (transcript and replay intact)
    assert [m.model_dump() for m in state.messages[: len(stored)]] == stored


def test_loop_sends_the_list_unchanged_on_other_routes(monkeypatch):
    model, seen, state, stored = _loop_once(monkeypatch, "mockllm/model")
    assert [m.model_dump() for m in model.inputs[0]] == [*stored[:2], *stored[4:]]
    assert seen == model.inputs
