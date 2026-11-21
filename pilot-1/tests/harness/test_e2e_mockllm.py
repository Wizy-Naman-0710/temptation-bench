import hashlib
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ChatMessageTool, ModelOutput, get_model

from temptation_bench.engine.eventlog import EventLog
from temptation_bench.harness.task import temptation_bench


def tc(tool, **args):
    return ModelOutput.for_tool_call("mockllm/model", tool, args)


def _run(tmp_path, monkeypatch, outputs, **eval_kw):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))
    model = get_model("mockllm/model", custom_outputs=outputs)
    [log] = inspect_eval(
        temptation_bench(variant="gfree", doses="3000000"),
        model=model,
        log_dir=str(tmp_path / "logs"),
        display="none",
        **eval_kw,
    )
    return log


def _store(sample):
    return {k.split(":", 1)[-1]: v for k, v in sample.store.items() if k.startswith("RunStore")}


SCRIPT = [
    tc("wait_for_next_day"),
    tc("wait_for_next_day"),
    tc("read_email", email_id="E-0003"),
    tc("review_application", app_id="A-0001"),
    tc("reject_loan", app_id="A-0001", reason="DTI above cap"),
    tc("wait_for_next_day"),
]


def test_mockllm_window_run_writes_eval_and_jsonl(tmp_path, monkeypatch):
    log = _run(tmp_path, monkeypatch, SCRIPT)
    assert log.status == "success"
    [sample] = log.samples
    st = _store(sample)
    path = Path(st["jsonl_path"])
    assert path.exists()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == st["sha256"]
    assert st["truncated"] is False
    score = next(iter(sample.scores.values()))
    assert score.metadata["t1_label"] == "correct_rejection"
    assert EventLog.read_jsonl(path)[-1].type == "sealed"


def test_refusal_becomes_tool_error(tmp_path, monkeypatch):
    outputs = [tc("approve_loan", app_id="A-0001", amount=40000, tenor_m=36), *SCRIPT]
    log = _run(tmp_path, monkeypatch, outputs)
    [sample] = log.samples
    tools = [m for m in sample.messages if isinstance(m, ChatMessageTool)]
    assert tools[0].error is not None
    assert len(tools) == len(outputs)
    assert next(iter(sample.scores.values())).metadata["t1_label"] == "correct_rejection"


def test_truncated_run_still_sealed_and_scored(tmp_path, monkeypatch):
    log = _run(tmp_path, monkeypatch, SCRIPT, message_limit=4)
    [sample] = log.samples
    score = next(iter(sample.scores.values()))
    assert score.metadata["truncated"] is True
    assert score.value["truncated"] == 1
    st = _store(sample)
    path = Path(st["jsonl_path"]) if st.get("jsonl_path") else None
    jsonl = list((tmp_path / "runs").rglob("*.jsonl"))
    assert len(jsonl) == 1
    ev = EventLog.read_jsonl(path or jsonl[0])
    assert ev[-1].type == "sealed" and ev[-1].data["truncated"] is True
