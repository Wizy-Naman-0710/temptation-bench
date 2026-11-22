"""Task 31 (carried from the Task 27-28 re-review): `build_report` lists every failed
attempt with its error text, even when the sample has a successful re-run.

Batch: eval A, where cell s1001-d3000000 ends in error (the model fails from call 3 on,
no rerun), then eval B, a re-run of the same cell whose first attempt fails once and whose
automatic rerun (`retry_on_error=1`) succeeds. Before the fix, A's copy was listed only as a
"re-run" under replays and both error texts were lost."""

from __future__ import annotations

import json
import re

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

from temptation_bench.analysis.load import load_batch
from temptation_bench.analysis.report import build_report
from temptation_bench.bots import run_bot
from temptation_bench.engine.config import load_config
from temptation_bench.harness.task import temptation_bench
from tests.test_budget import _mock_window

PERSISTENT = "persistent upstream failure"
TRANSIENT = "transient upstream failure"  # _mock_window's error text


def _always_fails_from(n_fail: int):
    state = {"n": 0}

    def fn(input, tools, tool_choice, config):
        state["n"] += 1
        if state["n"] >= n_fail:
            raise RuntimeError(PERSISTENT)
        return ModelOutput.for_tool_call("mockllm/model", "wait_for_next_day", {})

    return fn


@pytest.fixture(scope="module")
def batch(tmp_path_factory):
    root = tmp_path_factory.mktemp("t31_attempts")
    logs = root / "batch" / "logs"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("INSPECT_DISABLE_MODEL_API", "1")
        mp.setenv("INSPECT_CACHE_DIR", str(root / "inspect_cache"))
        mp.setenv("RUNS_DIR", str(root / "runs"))
        task = dict(variant="window", seeds="1001", doses="3000000")
        bad = get_model("mockllm/model", custom_outputs=_always_fails_from(3), memoize=False)
        [a] = inspect_eval(
            temptation_bench(**task),
            model=bad,
            log_dir=str(logs),
            display="none",
            retry_on_error=0,
            fail_on_error=False,
        )
        good = get_model("mockllm/model", custom_outputs=_mock_window(fail_at=3), memoize=False)
        [b] = inspect_eval(
            temptation_bench(**task),
            model=good,
            log_dir=str(logs),
            display="none",
            retry_on_error=1,
        )
    ledger = root / "ledger.jsonl"
    ledger.write_text(json.dumps({"step": "smoke", "actual": 0.0}) + "\n")
    bots = root / "bots"
    run_bot("honest", load_config("window"), 1001, 3_000_000, bots)  # the report needs bots
    report = build_report(root / "batch", bots, results_dir=root / "results", ledger_path=ledger)
    replays: list = []
    runs = load_batch(root / "batch", replays=replays)
    return {"a": a, "b": b, "md": report.read_text(), "runs": runs, "replays": replays}


def _section(md: str, head: str) -> str:
    sec = md[md.index(head) :]
    return sec[: sec.index("\n## ", 1)] if "\n## " in sec[1:] else sec


def test_fixture_has_an_errored_sample_and_a_retried_rerun(batch):
    [sa], [sb] = batch["a"].samples, batch["b"].samples
    assert sa.error is not None and PERSISTENT in sa.error.message
    assert sb.error is None and len(sb.error_retries or []) == 1
    assert TRANSIENT in sb.error_retries[0].message
    assert sa.id == sb.id  # the same cell


def test_every_failed_attempt_is_listed_with_its_error_text(batch):
    sec = _section(batch["md"], "## Failed attempts and errored samples")
    assert "Every failed attempt" in sec
    table = sec[sec.index("Every failed attempt") :]
    assert PERSISTENT in table  # the errored copy that has a successful re-run
    assert TRANSIENT in table  # the automatic rerun's failed first attempt
    assert re.search(r"Every failed attempt[^\n]*: 2\b", sec)


def test_errored_copy_is_not_called_a_re_run(batch):
    sec = _section(batch["md"], "## Replays and duplicate samples")
    rows = [ln for ln in sec.splitlines() if ln.startswith("| s1001")]
    assert rows and all("| re-run |" not in ln for ln in rows)
    assert any("errored attempt" in ln and PERSISTENT in ln for ln in rows)


def test_the_cell_counts_once_in_n(batch):
    agent = [r for r in batch["runs"] if r.meta.get("sample_id")]
    assert len(agent) == 1 and agent[0].labels
    # the kept run is the clean re-run, not the errored copy (which goes to replays)
    assert agent[0].meta.get("sample_error") is None
    assert agent[0].meta.get("attempt_errors") and TRANSIENT in agent[0].meta["attempt_errors"][0]
    [dup] = batch["replays"]
    assert PERSISTENT in dup.meta["sample_error"]
