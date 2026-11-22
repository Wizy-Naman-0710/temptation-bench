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
