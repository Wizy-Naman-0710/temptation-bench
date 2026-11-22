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

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

# Task 29 pre-work (rereview 22-26 Minor 5): tiktoken caches `o200k_base` under
# `$TMPDIR/data-gym-cache` unless `TIKTOKEN_CACHE_DIR` is set, and downloads it again if
# that cache is cleared (a network call; offline it fails the sample). Pin a durable,
# git-ignored dir inside pilot-1, set in-process before the counter is first used (tiktoken
# reads the variable on every load: `tiktoken/load.py` `read_file_cached`). Never set in a
# shell. The file name is tiktoken's cache key: sha1 of the blob URL.
TIKTOKEN_CACHE = Path(__file__).resolve().parents[3] / ".cache" / "tiktoken"
O200K_CACHE_KEY = "fb374d419588a4632f3f557e76b4b70aebbca790"  # sha1(o200k_base URL)


def seed_tiktoken_cache(cache_dir: Path, *, default_dir: Path | None = None) -> None:
    """Create `cache_dir`; if tiktoken's default tmp cache already holds o200k_base, copy it
    in (plain file copy, no network; never overwrites). tiktoken checks the file's SHA-256
    on load, so a bad copy is re-fetched rather than used."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    src = Path(default_dir or Path(tempfile.gettempdir()) / "data-gym-cache") / O200K_CACHE_KEY
    dst = cache_dir / O200K_CACHE_KEY
    if src.is_file() and not dst.exists():
        tmp = dst.with_name(f".{O200K_CACHE_KEY}.{os.getpid()}.tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)


os.environ["TIKTOKEN_CACHE_DIR"] = str(TIKTOKEN_CACHE)
try:
    seed_tiktoken_cache(TIKTOKEN_CACHE)
except OSError:  # a read-only checkout: tiktoken falls back to downloading into the dir
    pass

from inspect_ai.model import ChatMessage, GenerateConfig, Model, ModelOutput  # noqa: E402
from inspect_ai.model._tokens import (  # noqa: E402
    count_media_tokens,
    count_text_tokens,
    count_tokens,
)


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
