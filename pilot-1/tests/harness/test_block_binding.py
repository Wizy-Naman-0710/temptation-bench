"""Task 30 fix: the gateway's Anthropic-style route refuses `thinking.block_binding` (400).

Inspect 0.3.291 adds `thinking.block_binding = {"prefix_mismatch_behavior": "drop_block"}`
for Haiku 5.5 (`anthropic.py` `apply_thinking_block_binding`). Its docstring says a
caller-supplied `extra_body.thinking` replaces it. That works through the provider's
`extra_body` MODEL ARG (`self.extra_body`, merged into `request["extra_body"]`, which the SDK
shallow-merges over the JSON body). `GenerateConfig.extra_body` does NOT: `completion_config`
copies only `metadata`, `service_tier` and `context_management` from it.

No network: the SDK's httpx client `send` is replaced and raises after recording the wire
body, so the request never leaves the process."""

from __future__ import annotations

import asyncio
import json

import pytest
from inspect_ai.model import ChatMessageSystem, ChatMessageUser, GenerateConfig, get_model
from inspect_ai.model._providers.anthropic import AnthropicAPI

from temptation_bench import run
from temptation_bench.engine.config import load_config
from temptation_bench.harness.routes import ANTHROPIC_THINKING, PEOPLE_MODEL, model_args_for
from temptation_bench.harness.settings import generate_config, write_harness_json

FAKE = "fake-not-a-key"
BASE = "https://gw.example.invalid"
HAIKU = run.HAIKU
CELL = dict(people="template", variant="window")


class _Stop(Exception):
    pass


def wire_body(model_args: dict, config: GenerateConfig) -> dict:
    """The JSON body the SDK would put on the wire for one Haiku generate."""
    m = get_model(HAIKU, api_key=FAKE, base_url=BASE, streaming=False, memoize=False, **model_args)
    sent: list[dict] = []

    async def send(request, **kw):
        sent.append(json.loads(request.content))
        raise _Stop()

    m.api.client._client.send = send  # type: ignore[attr-defined]
    msgs = [ChatMessageSystem(content="policy"), ChatMessageUser(content="hello")]
    with pytest.raises(Exception):  # noqa: B017 - the SDK wraps _Stop in a connection error
        asyncio.run(m.api.generate(msgs, [], "auto", config))
    assert sent and all(b == sent[0] for b in sent)  # the SDK may retry the same body
    return sent[0]


def _haiku_config() -> GenerateConfig:
    cfg = generate_config(HAIKU, 1001, 3_000_000, load_config("window").harness, **CELL)
    return cfg.model_copy(update={"max_tokens": 512, "cache": None})


def test_anthropic_route_wire_body_has_no_block_binding_and_keeps_effort_low():
    body = wire_body(model_args_for(HAIKU), _haiku_config())
    assert "block_binding" not in json.dumps(body)
    assert body["thinking"] == {"type": "adaptive"}
    assert body["output_config"] == {"effort": "low"}
    assert "temperature" not in body and "seed" not in body


def test_without_the_fix_inspect_sends_block_binding():
    """Why the fix is needed: the default request carries it (the gateway 400)."""
    body = wire_body({}, _haiku_config())
    assert body["thinking"]["block_binding"] == {"prefix_mismatch_behavior": "drop_block"}


def test_config_extra_body_alone_does_not_drop_block_binding():
    """Why the fix is a model arg and not `GenerateConfig.extra_body`."""
    cfg = _haiku_config().model_copy(update={"extra_body": {"thinking": {"type": "adaptive"}}})
    assert "block_binding" in wire_body({}, cfg)["thinking"]


def test_model_args_per_route():
    assert model_args_for(HAIKU) == {"extra_body": {"thinking": {"type": "adaptive"}}}
    assert ANTHROPIC_THINKING == {"type": "adaptive"}
    assert model_args_for(run.LUNA) == {"strict_tools": False}
    assert model_args_for(PEOPLE_MODEL) == {"strict_tools": False}
    assert model_args_for("mockllm/model") == {}


def test_reasoning_history_none_for_haiku_only():
    h = load_config("window").harness
    assert generate_config(HAIKU, 1001, 0, h, **CELL).reasoning_history == "none"
    for slug in (run.LUNA, PEOPLE_MODEL, "mockllm/model"):
        assert generate_config(slug, 1001, 0, h, **CELL).reasoning_history is None


def test_inspect_anthropic_provider_forces_reasoning_history_all():
    """Tripwire: Inspect's Anthropic provider overrides `reasoning_history` with "all"
    (`anthropic.py` `force_reasoning_history`; `_model.py` `resolve_reasoning_history`), so
    the "none" above is recorded but does not strip replayed thinking. If Inspect changes
    this, revisit the Task 30 fix report."""
    m = get_model(HAIKU, api_key=FAKE, base_url=BASE, memoize=False)
    assert isinstance(m.api, AnthropicAPI)
    assert m.api.force_reasoning_history() == "all"


def test_runner_passes_the_thinking_override_on_the_anthropic_route(tmp_path, monkeypatch):
    seen: dict[str, dict] = {}

    def fake_eval(task, *, model, model_args, **kw):
        seen[kw["log_dir"]] = model_args

    monkeypatch.setattr(run, "inspect_eval", fake_eval)
    monkeypatch.setattr("temptation_bench.harness.task.temptation_bench", lambda **k: None)
    monkeypatch.setattr("temptation_bench.harness.route_check.route_check", lambda **k: None)
    smoke, rc = run.STEPS["smoke"].plan, run.STEPS["route_check"].plan
    run.launch_task_eval(run.Ctx("smoke", smoke, tmp_path / "s", 0.5, None))
    run.launch_route_check(run.Ctx("route_check", rc, tmp_path / "r", 0.05, None))
    run.launch_task_eval(run.Ctx("gfree", run.STEPS["gfree"].plan, tmp_path / "g", 1.0, 800_000))
    want = {"extra_body": {"thinking": {"type": "adaptive"}}}
    assert seen[str(tmp_path / "s")] == want == seen[str(tmp_path / "r")]
    assert seen[str(tmp_path / "g")] == {"strict_tools": False}


def test_harness_json_records_the_override_and_reasoning_history(tmp_path):
    cfg = load_config("window")
    h = json.loads(write_harness_json(tmp_path / "a", HAIKU, cfg, people="template").read_text())
    p = h["provider_settings"]
    assert p["model_args"] == {"extra_body": {"thinking": {"type": "adaptive"}}}
    assert p["reasoning_history"] == "none"
    luna = json.loads(
        write_harness_json(tmp_path / "b", run.LUNA, cfg, people="template").read_text()
    )
    assert luna["provider_settings"]["model_args"] == {"strict_tools": False}
    assert luna["provider_settings"]["reasoning_history"] == "not set (provider default)"
