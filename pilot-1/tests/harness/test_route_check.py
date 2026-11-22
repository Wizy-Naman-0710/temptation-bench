"""Task 30: the route check (spec §6/§7 route-check row, §7.1, §7.2).

No test reaches a network. The Haiku calls that must produce a real Anthropic request go
through Inspect's real `AnthropicAPI` request builder with its SDK client's
`messages.create` replaced by a local fake (`fake_haiku`), so the logged
`ModelEvent.call.request` is exactly what Inspect would send. The qwen call is mockllm."""

from __future__ import annotations

import re

import pytest
from anthropic.types import Message
from inspect_ai import eval as inspect_eval
from inspect_ai.event import ModelEvent
from inspect_ai.log import read_eval_log
from inspect_ai.model import CachePolicy, Model, ModelOutput, get_model
from inspect_ai.model._tokens import count_text_tokens

from temptation_bench.engine.config import load_config
from temptation_bench.harness import route_check as rc
from temptation_bench.harness.routes import model_args_for

FAKE = "fake-not-a-key"
BASE = "https://gw.example.invalid"
HAIKU = "anthropic/claude-haiku-5-5"
BANNED = re.compile(r"(test|evaluat|benchmark|bribe|cheat|simulat)", re.IGNORECASE)


def fake_haiku(calls: list[dict], cache_reads=(0, 6000), text="Section 3.") -> Model:
    """A Haiku model whose SDK `messages.create` is local: it records the request and
    returns a canned message with the given cache reads per call. `streaming=False` so
    the SDK's non-streaming `create` is the path (the request dict is the same)."""
    m = get_model(
        HAIKU, api_key=FAKE, base_url=BASE, streaming=False, memoize=False, **model_args_for(HAIKU)
    )

    async def create(**req):
        n = len(calls)
        calls.append(req)
        read = cache_reads[min(n, len(cache_reads) - 1)]
        return Message.model_validate(
            {
                "id": f"msg_{n}",
                "type": "message",
                "role": "assistant",
                "model": "claude-haiku-5-5",
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {
                    "input_tokens": 40,
                    "output_tokens": 5,
                    "cache_read_input_tokens": read,
                    "cache_creation_input_tokens": 6000 if read == 0 else 0,
                },
            }
        )

    create.fake_client = True  # type: ignore[attr-defined]
    m.api.client.messages.create = create  # type: ignore[attr-defined]
    return m


def _eval(tmp_path, model, *, reuse_cache=False, people_model="mockllm/model"):
    [log] = inspect_eval(
        rc.route_check(people_model=people_model, reuse_cache=reuse_cache),
        model=model,
        log_dir=str(tmp_path / "logs"),
        display="none",
        retry_on_error=0,
    )
    return read_eval_log(log.location, resolve_attachments=True)


def _events(log):
    [sample] = log.samples
    return [e for e in sample.events if isinstance(e, ModelEvent)]


# ---- the prompt --------------------------------------------------------------------------


def test_prefix_is_at_least_5k_local_tokens():
    assert count_text_tokens(rc.policy_prefix()) >= rc.MIN_PREFIX_TOKENS == 5000


def test_prefix_is_fixed():
    assert rc.policy_prefix() == rc.policy_prefix()


def test_route_check_texts_hold_no_banned_word():
    texts = [rc.policy_prefix(), *rc.QUESTIONS, rc.PEOPLE_PROMPT, rc.TOOL.description]
    texts += [p.description or "" for p in rc.TOOL.parameters.properties.values()]
    texts.append(rc.SAMPLE_INPUT)
    for t in texts:
        assert not BANNED.search(t), BANNED.search(t)


# ---- settings ----------------------------------------------------------------------------


def test_call_config_is_the_harness_config_without_the_response_cache():
    h = load_config("window").harness
    c = rc.call_config(rc.HAIKU, 512)
    assert c.reasoning_effort == "low" == h["reasoning_effort"]
    assert c.temperature is None and c.seed is None
    assert c.cache_prompt == "auto"
    assert c.max_retries == int(h["max_retries"])
    assert c.max_tokens == 512
    assert c.cache is None


def test_response_cache_off_by_default_and_fixed_scope_on_reuse():
    assert rc.response_cache(False) is False
    on = rc.response_cache(True)
    assert isinstance(on, CachePolicy)
    assert on.scopes == rc.REUSE_SCOPE == rc.response_cache(True).scopes
    assert on.expiry == load_config("window").harness["cache_expiry"]


# ---- worst case --------------------------------------------------------------------------


def test_worst_case_fits_the_route_check_cap():
    dollars, how = rc.worst_case()
    assert 0 < dollars <= 0.05
    assert "Haiku" in how and "qwen" in how and "attempts" in how


def test_worst_case_arithmetic_from_pricing():
    prices = {
        rc.HAIKU: {"input": 1.0, "output": 2.0, "input_cache_write": 3.0, "input_cache_read": 0.5},
        rc.PEOPLE_MODEL: {"input": 1.0, "output": 1.0},
    }
    dollars, _ = rc.worst_case(prices=prices, max_retries=0)
    h_in = rc.INPUT_MARGIN * rc.haiku_input_tokens()
    q_in = rc.INPUT_MARGIN * rc.people_input_tokens()
    want = 2 * (h_in * 3.0 + rc.HAIKU_MAX_TOKENS * 2.0) + (q_in * 1.0 + rc.PEOPLE_MAX_TOKENS)
    assert dollars == pytest.approx(want / 1e6)
    d5, _ = rc.worst_case(prices=prices, max_retries=5)
    assert d5 == pytest.approx(6 * dollars)


# ---- the three calls (mockllm) -----------------------------------------------------------


def test_mockllm_run_makes_exactly_three_calls_without_the_response_cache(tmp_path):
    model = get_model("mockllm/model")
    log = _eval(tmp_path, model)
    assert log.status == "success"
    evs = _events(log)
    assert len(evs) == 3
    h1, h2, q = evs
    for e in (h1, h2):
        assert e.input[0].role == "system" and e.input[0].text == rc.policy_prefix()
        assert [t.name for t in e.tools] == [rc.TOOL.name]
        assert e.config.reasoning_effort == "low" and e.config.max_tokens == rc.HAIKU_MAX_TOKENS
    assert h1.input[-1].text != h2.input[-1].text  # same prefix, a different question
    assert q.tools == [] and q.config.max_tokens == rc.PEOPLE_MAX_TOKENS
    assert {e.cache for e in evs} == {None}  # rule 2: no local response cache


def test_check_fails_on_mockllm_no_effort_and_no_cache_read(tmp_path):
    log = _eval(tmp_path, get_model("mockllm/model"))
    rows = {r.name: r for r in rc.check_log(log, reuse_cache=False)}
    assert not rows["call 2 cache_read > 0"].ok
    assert not rows["call 1 request effort low"].ok
    assert rows["qwen answered (non-empty text)"].ok
    assert not rc.passed(list(rows.values()))


# ---- the three calls (real Anthropic request builder, fake client) ------------------------


def test_real_anthropic_request_carries_output_config_effort_low(tmp_path, allow_fake_client):
    calls: list[dict] = []
    log = _eval(tmp_path, fake_haiku(calls))
    assert len(calls) == 2
    for req in calls:  # what the SDK was asked to send
        assert req["output_config"] == {"effort": "low"}
        # the SDK shallow-merges extra_body over the body: thinking loses block_binding
        assert req["extra_body"]["thinking"] == {"type": "adaptive"}
        assert rc.effective_request(req)["thinking"] == {"type": "adaptive"}
        assert req["max_tokens"] == rc.HAIKU_MAX_TOKENS
        assert "temperature" not in req and "seed" not in req
        assert req["system"][-1]["cache_control"]["type"] == "ephemeral"
        assert len(req["tools"]) == 1
    h1, h2, _ = _events(log)
    for e in (h1, h2):  # and what the log holds
        assert e.call is not None and e.call.request["output_config"]["effort"] == "low"
    assert h2.output.usage.input_tokens_cache_read == 6000


def test_check_passes_on_a_good_route(tmp_path, allow_fake_client, capsys):
    log = _eval(tmp_path, fake_haiku([]))
    rows = rc.check_log(log, reuse_cache=False)
    assert rc.passed(rows), rc.table(rows)
    out = rc.table(rows)
    assert "PASS" in out and "FAIL" not in out


def test_check_fails_without_cache_read_on_call_2(tmp_path, allow_fake_client):
    log = _eval(tmp_path, fake_haiku([], cache_reads=(0, 0)))
    rows = {r.name: r for r in rc.check_log(log, reuse_cache=False)}
    assert not rows["call 2 cache_read > 0"].ok
    assert rows["call 1 request effort low"].ok and rows["call 2 request effort low"].ok


def test_check_fails_when_the_request_lost_effort(tmp_path, allow_fake_client):
    log = _eval(tmp_path, fake_haiku([]))
    h1, h2, _ = _events(log)
    h2.call.request.pop("output_config")
    rows = {r.name: r for r in rc.check_log(log, reuse_cache=False)}
    assert rows["call 1 request effort low"].ok
    assert not rows["call 2 request effort low"].ok


def test_check_fails_on_empty_qwen_text(tmp_path, allow_fake_client):
    log = _eval(tmp_path, fake_haiku([]))
    _, _, q = _events(log)
    q.output = ModelOutput.from_content("mockllm/model", "   ")
    rows = {r.name: r for r in rc.check_log(log, reuse_cache=False)}
    assert not rows["qwen answered (non-empty text)"].ok


def test_check_fails_when_a_call_is_missing(tmp_path, allow_fake_client):
    log = _eval(tmp_path, fake_haiku([]))
    [sample] = log.samples
    sample.events = [e for e in sample.events if isinstance(e, ModelEvent)][:2]
    rows = rc.check_log(log, reuse_cache=False)
    assert not rc.passed(rows)
    assert not {r.name: r for r in rows}["3 model calls logged"].ok


def test_check_fails_if_the_local_cache_was_used_without_reuse(tmp_path, allow_fake_client):
    log = _eval(tmp_path, fake_haiku([]))
    for e in _events(log):
        e.cache = "write"
    rows = {r.name: r for r in rc.check_log(log, reuse_cache=False)}
    assert not rows["local response cache off"].ok


# ---- --reuse-cache: a second process reads every call from the local cache -----------------


def test_reuse_cache_second_run_reads_all_three_from_the_local_cache(tmp_path, allow_fake_client):
    calls: list[dict] = []
    first = _eval(tmp_path / "a", fake_haiku(calls), reuse_cache=True)
    assert {e.cache for e in _events(first)} == {"write"}
    rows1 = rc.check_log(first, reuse_cache=True)
    assert rc.passed(rows1), rc.table(rows1)  # a populating run is a full provider check
    assert len(calls) == 2
    second = _eval(tmp_path / "b", fake_haiku(calls), reuse_cache=True)
    assert len(calls) == 2  # no provider call
    assert {e.cache for e in _events(second)} == {"read"}
    rows2 = rc.check_log(second, reuse_cache=True)
    assert rc.passed(rows2), rc.table(rows2)
    assert "all 3 calls read from the local response cache" in rc.table(rows2)
    assert not second.stats.model_usage or all(
        (u.total_cost or 0) == 0 for u in second.stats.model_usage.values()
    )


def test_reuse_cache_partial_hit_fails(tmp_path, allow_fake_client):
    log = _eval(tmp_path, fake_haiku([]), reuse_cache=True)
    evs = _events(log)
    evs[0].cache = "read"
    evs[0].call = None
    assert not rc.passed(rc.check_log(log, reuse_cache=True))


def test_table_lists_every_row():
    rows = [rc.Row("a", True, "x"), rc.Row("b", False, "y")]
    out = rc.table(rows)
    assert re.search(r"PASS\s+a", out) and re.search(r"FAIL\s+b", out)
    assert not rc.passed(rows) and rc.passed(rows[:1])


def test_check_fails_when_block_binding_would_be_sent(tmp_path, allow_fake_client):
    log = _eval(tmp_path, fake_haiku([]))
    rows = {r.name: r for r in rc.check_log(log, reuse_cache=False)}
    assert rows["call 1 thinking has no block_binding"].ok
    _, h2, _ = _events(log)
    h2.call.request.pop("extra_body")  # as without the Task 30 fix
    rows = {r.name: r for r in rc.check_log(log, reuse_cache=False)}
    assert rows["call 1 thinking has no block_binding"].ok
    assert not rows["call 2 thinking has no block_binding"].ok


def test_effort_row_reads_the_merged_request():
    req = {
        "output_config": {"effort": "medium"},
        "extra_body": {"output_config": {"effort": "low"}},
    }
    assert rc.effective_request(req)["output_config"] == {"effort": "low"}
    assert rc.effective_request({"thinking": {"type": "adaptive"}}) == {
        "thinking": {"type": "adaptive"}
    }


def test_call_config_per_route():
    assert rc.call_config(rc.HAIKU, 512).reasoning_history == "none"
    assert rc.call_config(rc.PEOPLE_MODEL, 1024).reasoning_history is None
