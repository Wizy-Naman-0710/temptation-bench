"""Local token counting for compaction (review R22-1, spec §6 G-free "no extra count-tokens
calls").

Inspect's compaction counts tokens with its target model (`Model.count_tokens`), and the
Anthropic provider overrides that with the native `/v1/messages/count_tokens` API: a gateway
request on every turn (and three before the first generate). `LocalCountModel` is the target
the loop passes to `compaction(model=...)`: it shares the real model's provider object (so
message collapsing and the CompactionEvent role match the real model) but counts with
Inspect's own local helper, tiktoken o200k_base plus a 10% buffer
(`inspect_ai.model._tokens`, the default `ModelAPI.count_tokens`). That is the counter the
Task 22/23 trim floor (`engine.config.MIN_TRIM_TOKENS`) was measured with, so the floor and
the threshold use the same unit. Free and deterministic; never a network call.

After the first generate Inspect uses the provider's reported `input_tokens` as the
baseline (from the generate's own usage, not an extra call) and counts only new messages
locally."""

from __future__ import annotations

from typing import Any

from inspect_ai.model import ChatMessage, GenerateConfig, Model, ModelOutput
from inspect_ai.model._tokens import count_media_tokens, count_text_tokens, count_tokens


async def _text(text: str) -> int:
    return count_text_tokens(text)


async def _media(media: Any) -> int:
    return count_media_tokens(media)


class LocalCountModel(Model):
    """The compaction target: the real model's identity, a local token counter, no generate."""

    def __init__(self, target: Model) -> None:
        super().__init__(target.api, target.config, target.model_args)
        if target.role is not None:
            self._set_role(target.role)

    async def count_tokens(
        self, input: str | list[ChatMessage], config: GenerateConfig | None = None
    ) -> int:
        if isinstance(input, str):
            return count_text_tokens(input)
        return await count_tokens(input, _text, _media)

    async def generate(self, *args: Any, **kwargs: Any) -> ModelOutput:  # type: ignore[override]
        raise RuntimeError("LocalCountModel counts tokens only; it never generates")
