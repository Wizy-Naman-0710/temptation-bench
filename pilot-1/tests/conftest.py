import os

import pytest

from temptation_bench.engine.branch import Branch
from temptation_bench.engine.config import load_config

# R25-1: Inspect refuses every non-mockllm model API under this switch
# (`inspect_ai/model/_model.py`, `verify_model_apis`). `inspect_ai.eval` loads the real
# `pilot-1/.env` into os.environ (`init_dotenv`, never overriding a set variable), so a
# test that built a real model could otherwise spend money. Set at import (before any test
# or fixture runs) and again for every test (in case a test removes it).
MODEL_API_SWITCH = "INSPECT_DISABLE_MODEL_API"
os.environ[MODEL_API_SWITCH] = "1"


@pytest.fixture(autouse=True)
def no_model_apis(monkeypatch):
    monkeypatch.setenv(MODEL_API_SWITCH, "1")


@pytest.fixture(autouse=True)
def strict_output(monkeypatch):
    """I15 is loud in CI: an over-long output raises instead of being clipped (paid runs
    keep the default, clip + hidden `output_clipped` event)."""
    monkeypatch.setattr(Branch, "strict_output", True, raising=False)


@pytest.fixture
def cfg():
    return load_config("window")


@pytest.fixture
def make_branch(tmp_path):
    def _make(seed=1001, dose=3_000_000, variant="window", **overrides):
        c = load_config(variant, **overrides)
        return Branch.new(c, seed, dose, log_path=tmp_path / f"run-{seed}-{dose}.jsonl")

    return _make


def advance_to(branch, day):
    while branch.day < day and not branch.over:
        branch.call("wait_for_next_day")


@pytest.fixture(autouse=True)
def inspect_cache_dir(monkeypatch, tmp_path):
    """Task 24 turns on Inspect's output cache for every run: keep test entries out of the
    user's cache directory (one fresh cache per test)."""
    monkeypatch.setenv("INSPECT_CACHE_DIR", str(tmp_path / "inspect_cache"))


@pytest.fixture(autouse=True)
def no_provider_count_tokens(monkeypatch):
    """Task 29 pre-work (rereview 22-26 out-of-scope 1): `INSPECT_DISABLE_MODEL_API` gates
    `generate` only, not `count_tokens`, and the Anthropic (and Google) providers count with
    a network API. Every non-mockllm count raises in tests: at `Model.count_tokens` (the
    path compaction uses) and on each loaded provider class that overrides the counter.
    `LocalCountModel` overrides `Model.count_tokens` with the local counter, so it still
    works."""
    from inspect_ai.model import Model
    from inspect_ai.model._model import ModelAPI
    from inspect_ai.model._providers.anthropic import AnthropicAPI
    from inspect_ai.model._providers.mockllm import MockLLM

    def blocked(where):
        async def boom(*a, **k):
            raise AssertionError(f"provider count_tokens API called in a test ({where})")

        return boom

    original = Model.count_tokens

    async def model_count_tokens(self, input, config=None):
        if isinstance(self.api, MockLLM):
            return await original(self, input, config)
        return await blocked(str(self))()

    monkeypatch.setattr(Model, "count_tokens", model_count_tokens)

    classes = {AnthropicAPI}
    try:
        from inspect_ai.model._providers.google import GoogleGenAIAPI

        classes.add(GoogleGenAIAPI)
    except Exception:  # the google SDK is not installed: nothing to block
        pass
    todo = list(ModelAPI.__subclasses__())
    while todo:  # every provider class loaded so far
        c = todo.pop()
        classes.add(c)
        todo.extend(c.__subclasses__())
    for cls in sorted(classes - {MockLLM}, key=lambda c: c.__qualname__):
        for name in ("count_tokens", "count_text_tokens"):
            if name in cls.__dict__:
                monkeypatch.setattr(cls, name, blocked(f"{cls.__name__}.{name}"))


@pytest.fixture
def allow_fake_client(monkeypatch):
    """Task 30 (opt-in). `INSPECT_DISABLE_MODEL_API` refuses every non-mockllm generate.
    Let through only a model whose SDK client `messages.create` is a local fake marked
    `fake_client` (`tests/harness/test_route_check.py` `fake_haiku`); every other model
    still refuses."""
    from inspect_ai.model import Model

    original = Model.verify_model_apis

    def verify(self):
        create = getattr(
            getattr(getattr(self.api, "client", None), "messages", None), "create", None
        )
        if getattr(create, "fake_client", False):
            return None
        return original(self)

    monkeypatch.setattr(Model, "verify_model_apis", verify)
