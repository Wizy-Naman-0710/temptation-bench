"""R22-1: compaction counts tokens locally and never calls a provider's `count_tokens` API.

Inspect's compaction counts with its target model (`Model.count_tokens`), and the Anthropic
provider overrides that with the native `/v1/messages/count_tokens` API (a gateway request
per turn). The loop instead gives `compaction(model=...)` a wrapper whose count is Inspect's
local helper (tiktoken o200k_base + 10%): the same counter the Task 22/23 trim floor was
measured with. No network: the Anthropic model below is only built, never called."""

from __future__ import annotations

import asyncio

import pytest
from inspect_ai.model import ChatMessageSystem, ChatMessageUser, Model, get_model
from inspect_ai.model._providers.anthropic import AnthropicAPI
from inspect_ai.model._tokens import count_media_tokens, count_text_tokens, count_tokens
from inspect_ai.tool import ToolInfo, ToolParams

from temptation_bench.harness.counting import LocalCountModel
from tests.harness.test_e2e_mockllm import _run
from tests.harness.test_window import SMALL_TRIM, TRIM_SCRIPT, _decision, _variant

FAKE = "fake-not-a-key"
BASE = "https://gw.example.invalid"
MESSAGES = [
    ChatMessageSystem(content="You are the manager of a branch."),
    ChatMessageUser(content="Your first day starts now. Loan A-0001 asks for $40,000."),
]


def _no_provider_count(monkeypatch):
    async def boom(self, *a, **k):
        raise AssertionError("provider count_tokens API called")

    monkeypatch.setattr(AnthropicAPI, "count_tokens", boom)


def test_local_count_never_calls_the_anthropic_count_api(monkeypatch):
    _no_provider_count(monkeypatch)
    haiku = get_model("anthropic/claude-haiku-5-5", api_key=FAKE, base_url=BASE)
    with pytest.raises(AssertionError, match="provider count_tokens"):  # the spy works
        asyncio.run(haiku.count_tokens(MESSAGES))
    local = LocalCountModel(haiku)
    expected = asyncio.run(count_tokens(MESSAGES, _text, _media))
    assert asyncio.run(local.count_tokens(MESSAGES)) == expected
    assert asyncio.run(local.count_tokens("hello there")) == count_text_tokens("hello there")
    tool = ToolInfo(name="get_status", description="Branch status.", parameters=ToolParams())
    assert asyncio.run(local.count_tool_tokens([tool])) > 0


def test_local_count_model_keeps_the_target_identity():
    haiku = get_model("anthropic/claude-haiku-5-5", api_key=FAKE, base_url=BASE)
    local = LocalCountModel(haiku)
    assert str(local) == str(haiku)
    assert local.api is haiku.api  # same provider rules for message collapsing
    with pytest.raises(RuntimeError, match="counts tokens only"):
        asyncio.run(local.generate("hello"))


def test_compacted_run_makes_no_model_count_tokens_call(tmp_path, monkeypatch):
    """Every compaction count of the target model goes through `Model.count_tokens` (which
    hands it to the provider). Make that raise: a trimmed run must still finish."""

    async def boom(self, *a, **k):
        raise AssertionError("Model.count_tokens called: would reach the provider")

    monkeypatch.setattr(Model, "count_tokens", boom)
    log = _run(tmp_path, monkeypatch, TRIM_SCRIPT, variant=_variant(tmp_path, SMALL_TRIM))
    assert log.status == "success", log.error
    [sample] = log.samples
    assert sample.error is None
    assert any(e.event == "compaction" for e in sample.events)
    assert _decision(sample)["review_in_window"] is False


async def _text(t: str) -> int:
    return count_text_tokens(t)


async def _media(m) -> int:
    return count_media_tokens(m)
