"""Per-route model args (Task 29 fix: gateway 400 on strict tools).

Inspect's `openai-api` provider defaults to `strict_tools=True`
(`inspect_ai/model/_providers/openai_compatible.py:99`) and sets `"strict"` on every tool from
it (`:566`, `tools_to_openai`). OpenAI strict mode needs every property in `required`, and
our tools have optional params (e.g. `list_applications.status`), so the gateway refused the
first generate. The openai-api routes (Luna, and qwen for the `people` role) therefore run
with `strict_tools=False`. The tool schemas stay the same for every model.

Task 30 fix (gateway 400 "Unknown parameter 'thinking.block_binding'"): Inspect adds
`thinking.block_binding` for Haiku 5.5 (`anthropic.py` `apply_thinking_block_binding`). The
Anthropic route passes the provider's `extra_body` model arg `{"thinking": {"type":
"adaptive"}}`: Inspect puts it in `request["extra_body"]` (`anthropic.py:1031-1032`) and the
SDK shallow-merges it over the JSON body, so the sent `thinking` is exactly
`{"type": "adaptive"}` while `output_config.effort` (low) is untouched.
`GenerateConfig.extra_body` would not work: `completion_config` copies only `metadata`,
`service_tier` and `context_management` from it (`:1626-1633`).

Task 30 fix (reasoning strip): Inspect's Anthropic provider forces `reasoning_history="all"`
(`force_reasoning_history`), so every old thinking block is replayed. The agent loop instead
sends `strip_old_reasoning(input, model)`: on the Anthropic route only, `ContentReasoning`
stays on the most recent assistant message (a tool_use continuation needs that turn's
thinking block replayed unmodified, signature included) and is dropped from all older ones."""

from __future__ import annotations

from typing import Any

from inspect_ai.model import ChatMessage, ChatMessageAssistant, ContentReasoning, Model

OPENAI_API = "openai-api/"
ANTHROPIC = "anthropic/"
ANTHROPIC_THINKING = {"type": "adaptive"}  # replaces Inspect's thinking (no block_binding)
PEOPLE_MODEL = "openai-api/xpl/qwen3.7-flash"  # spec D4: the `people` role
REASONING_RULE = "reasoning stripped from all but the last assistant message, Anthropic route"


def model_args_for(slug: str) -> dict[str, Any]:
    """Model args for an eval's main model (`inspect_eval(model_args=...)`, `-M`)."""
    if str(slug).startswith(OPENAI_API):
        return {"strict_tools": False}
    if str(slug).startswith(ANTHROPIC):
        return {"extra_body": {"thinking": dict(ANTHROPIC_THINKING)}}
    return {}


def non_strict_tools(model: Model) -> Model:
    """For a model Inspect already built without our args (a role given as a string), turn
    strict tools off on its openai-api provider. Other providers are returned untouched."""
    from inspect_ai.model._providers.openai_compatible import OpenAICompatibleAPI

    if isinstance(model.api, OpenAICompatibleAPI):
        model.api.strict_tools = False
    return model


def strip_old_reasoning(messages: list[ChatMessage], model: str) -> list[ChatMessage]:
    """The list to send to `generate`. Anthropic route: a new list in which every assistant
    message except the most recent one is a copy without `ContentReasoning` (same id, text
    and tool calls). Other routes: the list unchanged. The input list and its messages are
    never modified (the stored conversation, transcript and replay keep every block)."""
    if not str(model).startswith(ANTHROPIC):
        return messages
    last = max(
        (i for i, m in enumerate(messages) if isinstance(m, ChatMessageAssistant)), default=-1
    )
    out: list[ChatMessage] = []
    for i, m in enumerate(messages):
        if i < last and isinstance(m, ChatMessageAssistant) and isinstance(m.content, list):
            kept = [c for c in m.content if not isinstance(c, ContentReasoning)]
            if len(kept) != len(m.content):
                m = m.model_copy(update={"content": kept})
        out.append(m)
    return out
