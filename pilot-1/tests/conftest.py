import pytest

from temptation_bench.engine.branch import Branch
from temptation_bench.engine.config import load_config


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
