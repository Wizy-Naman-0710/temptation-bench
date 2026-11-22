"""Task 22: compaction (CompactionTrim) and real `in_window` tracking.

The e2e tests drive the real agent loop with mockllm; the unit tests pin WindowTracker."""

from pathlib import Path

from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    ModelOutput,
)
from inspect_ai.tool import ToolCall, ToolCallError

from temptation_bench.engine.config import CONFIG_DIR
from temptation_bench.engine.eventlog import EventLog
from temptation_bench.harness.window import WindowTracker
from tests.harness.test_e2e_mockllm import _run, _store, tc

# --- e2e: the loop trims the input and the engine logs what was still visible ---------


def _variant(tmp_path: Path, trim_tokens: int) -> str:
    """gfree (D1-D3) with a custom trim threshold, as a variant file."""
    path = tmp_path / f"trim_{trim_tokens}.toml"
    gfree = (CONFIG_DIR / "variants" / "gfree.toml").resolve()
    path.write_text(f'extends = "{gfree}"\n\n[harness]\ntrim_tokens = {trim_tokens}\n')
    return str(path)


def _decision(sample, app_id="A-0001"):
    path = Path(_store(sample)["jsonl_path"])
    [dec] = [
        e for e in EventLog.read_jsonl(path) if e.type == "decision" and e.data["app_id"] == app_id
    ]
    return dec.data


# Tools (~2.3k tokens) + system prompt and first message (~1.3k) are counted against the
# threshold before any conversation (Inspect counts them; it raises if they alone exceed it),
# so a ~2k-token conversation budget is a threshold of about 6k.
SMALL_TRIM = 6000

TRIM_SCRIPT = [
    tc("wait_for_next_day"),
    tc("wait_for_next_day"),
    tc("review_application", app_id="A-0001"),
    *[tc("get_status") for _ in range(40)],
    tc("reject_loan", app_id="A-0001", reason="DTI above cap"),
    tc("wait_for_next_day"),
]


def test_in_window_false_after_trim(tmp_path, monkeypatch):
    log = _run(tmp_path, monkeypatch, TRIM_SCRIPT, variant=_variant(tmp_path, SMALL_TRIM))
    [sample] = log.samples
    assert any(e.event == "compaction" for e in sample.events)
    dec = _decision(sample)
    assert dec["reviewed"] is True
    assert dec["review_in_window"] is False


def test_in_window_true_without_trim(tmp_path, monkeypatch):
    log = _run(tmp_path, monkeypatch, TRIM_SCRIPT, variant=_variant(tmp_path, 10**6))
    [sample] = log.samples
    assert not any(e.event == "compaction" for e in sample.events)
    dec = _decision(sample)
    assert dec["reviewed"] is True
    assert dec["review_in_window"] is True


def _overflow() -> ModelOutput:
    return ModelOutput.from_content("mockllm/model", "", stop_reason="model_length")


def test_model_length_forces_compaction_and_retries(tmp_path, monkeypatch):
    script = [*TRIM_SCRIPT[:3], _overflow(), *TRIM_SCRIPT[3:]]
    log = _run(tmp_path, monkeypatch, script, variant=_variant(tmp_path, 10**6))
    [sample] = log.samples
    forced = [e for e in sample.events if e.event == "compaction"]
    assert [e.metadata["trigger"] for e in forced] == ["forced"]
    assert _store(sample)["truncated"] is False  # the retry carried on to the end
    assert _decision(sample)["action"] == "reject"


def test_second_model_length_ends_run_sealed_and_scored(tmp_path, monkeypatch):
    script = [*TRIM_SCRIPT[:3], _overflow(), _overflow(), *TRIM_SCRIPT[3:]]
    log = _run(tmp_path, monkeypatch, script, variant=_variant(tmp_path, 10**6))
    [sample] = log.samples
    assert log.status == "success"
    st = _store(sample)
    assert st["truncated"] is True
    score = next(iter(sample.scores.values()))
    assert score.value["truncated"] == 1
    assert EventLog.read_jsonl(Path(st["jsonl_path"]))[-1].type == "sealed"


# --- unit: WindowTracker --------------------------------------------------------------


def _tool_msg(call_id: str, fn: str, error: str | None = None) -> ChatMessageTool:
    err = ToolCallError(type="unknown", message=error) if error else None
    return ChatMessageTool(content="out", tool_call_id=call_id, function=fn, error=err)


def _turn(*calls: tuple[str, str, dict], errors: dict[str, str] | None = None):
    """An assistant message with tool calls and its tool result messages."""
    errors = errors or {}
    assistant = ChatMessageAssistant(
        content="",
        tool_calls=[ToolCall(id=i, function=f, arguments=a) for i, f, a in calls],
    )
    results = [_tool_msg(i, f, errors.get(i)) for i, f, _ in calls]
    return assistant, results


PREFIX = [ChatMessageSystem(content="sys"), ChatMessageUser(content="first")]


def test_nothing_recorded_means_not_in_window():
    w = WindowTracker()
    w.update(PREFIX)
    ctx = w.context("A-0001")
    assert not ctx.latest_review_in_window
    assert not ctx.latest_portfolio_in_window
    assert not ctx.offer_email_in_window


def test_review_in_window_only_while_its_tool_message_is_sent():
    w = WindowTracker()
    w.record("c1", "review", "A-0001")
    assert not w.context("A-0001").latest_review_in_window  # not yet sent to the model
    w.update([*PREFIX, _tool_msg("c1", "review_application")])
    assert w.context("A-0001").latest_review_in_window
    assert not w.context("A-0002").latest_review_in_window  # keyed by app_id
    assert not w.context(None).latest_review_in_window
    w.update(PREFIX)  # trimmed out
    assert not w.context("A-0001").latest_review_in_window


def test_latest_of_several_reviews_counts():
    w = WindowTracker()
    w.record("c1", "review", "A-0001")
    w.record("c2", "review", "A-0001")
    w.update([*PREFIX, _tool_msg("c1", "review_application")])
    assert not w.context("A-0001").latest_review_in_window  # only an older review is visible
    w.update([*PREFIX, _tool_msg("c2", "review_application")])
    assert w.context("A-0001").latest_review_in_window


def test_observe_maps_tools_to_kinds():
    w = WindowTracker(offer_email_id="E-0003")
    assistant, results = _turn(
        ("c1", "review_application", {"app_id": "A-0001"}),
        ("c2", "get_portfolio_report", {"as_of": "now"}),
        ("c3", "read_email", {"email_id": "E-0003"}),
        ("c4", "get_status", {}),
    )
    w.observe(assistant, results)
    w.update([*PREFIX, assistant, *results])
    ctx = w.context("A-0001")
    assert ctx.latest_review_in_window
    assert ctx.latest_portfolio_in_window
    assert ctx.offer_email_in_window


def test_other_email_is_not_the_offer_email():
    w = WindowTracker(offer_email_id="E-0003")
    assistant, results = _turn(("c1", "read_email", {"email_id": "E-0001"}))
    w.observe(assistant, results)
    w.update([*PREFIX, assistant, *results])
    assert not w.context("A-0001").offer_email_in_window


def test_refused_call_is_not_recorded():
    w = WindowTracker()
    assistant, results = _turn(("c1", "review_application", {"app_id": "A-0001"}))
    w.observe(assistant, results)
    bad_assistant, bad = _turn(
        ("c2", "review_application", {"app_id": "A-0001"}), errors={"c2": "No application"}
    )
    w.observe(bad_assistant, bad)  # a refusal does not replace the latest good review
    w.update([*PREFIX, assistant, *results])
    assert w.context("A-0001").latest_review_in_window
    w.update([*PREFIX, bad_assistant, *bad])
    assert not w.context("A-0001").latest_review_in_window
