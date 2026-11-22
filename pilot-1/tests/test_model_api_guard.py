"""R25-1: no test may reach a real model API.

`inspect_ai.eval` loads the nearest `.env` (the real `pilot-1/.env`) into `os.environ`, so a
test that built a real provider model could make a paid call. `tests/conftest.py` sets
`INSPECT_DISABLE_MODEL_API` for the whole session and again for every test: Inspect then
refuses every non-mockllm `generate` (`inspect_ai/model/_model.py`, `verify_model_apis`).
Building a real-provider `Model` (no call) keeps working."""

from __future__ import annotations

import asyncio
import os

import pytest
from inspect_ai.model import ModelOutput, get_model

SWITCH = "INSPECT_DISABLE_MODEL_API"
FAKE = "fake-not-a-key"  # passed as an argument only; never set in the environment
BASE = "https://gw.example.invalid"


def test_model_api_switch_is_on():
    assert os.environ.get(SWITCH) is not None


def test_non_mockllm_model_refuses_under_switch():
    assert os.environ.get(SWITCH) is not None  # never attempt a real call without it
    model = get_model("anthropic/claude-haiku-5-5", api_key=FAKE, base_url=BASE)
    with pytest.raises(RuntimeError, match="Model APIs disabled"):
        asyncio.run(model.generate("hello"))


def test_mockllm_still_runs_under_switch():
    ok = ModelOutput.from_content("mockllm/model", "ok")
    model = get_model("mockllm/model", custom_outputs=[ok])
    assert asyncio.run(model.generate("hello")).completion == "ok"
