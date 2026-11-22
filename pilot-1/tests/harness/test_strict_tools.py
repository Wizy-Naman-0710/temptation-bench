"""Task 29 fix: the openai-api routes (Luna; the `people` role model) send non-strict tools.

Inspect's `openai-api` provider defaults to `strict_tools=True` (`openai_compatible.py:99`)
and stamps `"strict": true` on every tool (`:566`). Strict mode needs every property in
`required`, so the gateway refused `list_applications` (optional `status`) with a 400. The
fix builds those models with `strict_tools=False`; the agent-facing schemas are unchanged.
No network: models are only built (fake key, `.invalid` URL), never called."""

from __future__ import annotations

from inspect_ai.model import get_model
from inspect_ai.tool import ToolDef, ToolInfo

from temptation_bench import run
from temptation_bench.harness import pregen_people
from temptation_bench.harness.routes import PEOPLE_MODEL, model_args_for, non_strict_tools
from temptation_bench.harness.tools import make_tools
from temptation_bench.harness.window import WindowTracker

FAKE = "fake-not-a-key"
BASE = "https://gw.example.invalid"


def _tool_infos(make_branch):
    defs = [ToolDef(t) for t in make_tools(make_branch(), WindowTracker())]
    return [ToolInfo(name=d.name, description=d.description, parameters=d.parameters) for d in defs]


def _strict_ok(schema: dict) -> bool:
    """OpenAI strict rules for one object schema: every property required, no extras."""
    props = schema.get("properties", {})
    return set(schema.get("required", [])) == set(props) and (
        schema.get("additionalProperties") is False
    )


def _assert_all_non_strict(api, infos):
    assert api.strict_tools is False
    sent = api.tools_to_openai(infos)
    assert len(sent) == 18
    for t in sent:
        assert t["function"]["strict"] is False, t["function"]["name"]


def test_runner_builds_luna_with_strict_tools_off(tmp_path, monkeypatch, make_branch):
    seen = {}

    def fake_eval(task, *, model, model_args, **kw):
        # what Inspect's `resolve_models` does with the eval's model + model_args
        seen["model"] = get_model(model, api_key=FAKE, base_url=BASE, **model_args)

    monkeypatch.setattr(run, "inspect_eval", fake_eval)
    plan = run.STEPS["gfree"].plan
    run.launch_task_eval(run.Ctx("gfree", plan, tmp_path, 1.0, 800_000))
    assert str(seen["model"]) == run.LUNA
    _assert_all_non_strict(seen["model"].api, _tool_infos(make_branch))


def test_runner_anthropic_route_gets_only_the_thinking_override(tmp_path, monkeypatch):
    """Task 30 fix: no strict-tools arg on the Anthropic route, only the thinking override
    (`tests/harness/test_block_binding.py`)."""
    seen = {}

    def fake_eval(task, *, model, model_args, **kw):
        seen["args"] = model_args

    monkeypatch.setattr(run, "inspect_eval", fake_eval)
    run.launch_task_eval(run.Ctx("smoke", run.STEPS["smoke"].plan, tmp_path, 0.5, None))
    want = {"extra_body": {"thinking": {"type": "adaptive"}}}
    assert seen["args"] == want == model_args_for(run.HAIKU)


def test_pregen_people_model_has_strict_tools_off(monkeypatch, make_branch):
    """The `people` role arrives as a string Inspect resolves with no args; the pregen
    solver's model seam turns strict tools off."""
    people = get_model(PEOPLE_MODEL, api_key=FAKE, base_url=BASE, memoize=False)
    assert people.api.strict_tools is True  # Inspect's default: the bug
    monkeypatch.setattr(pregen_people, "get_model", lambda **kw: people)
    model = pregen_people.people_model()
    assert model is people
    _assert_all_non_strict(model.api, _tool_infos(make_branch))


def test_non_strict_tools_ignores_other_providers():
    haiku = get_model("anthropic/claude-haiku-5-5", api_key=FAKE, base_url=BASE)
    assert non_strict_tools(haiku) is haiku and not hasattr(haiku.api, "strict_tools")
    assert model_args_for(PEOPLE_MODEL) == {"strict_tools": False}


def test_every_tool_schema_is_strict_valid_or_strict_is_off(make_branch):
    infos = _tool_infos(make_branch)
    for slug in (run.LUNA, PEOPLE_MODEL):
        api = get_model(slug, api_key=FAKE, base_url=BASE, memoize=False, **model_args_for(slug))
        for t in api.api.tools_to_openai(infos):
            f = t["function"]
            assert f["strict"] is False or _strict_ok(f["parameters"]), f["name"]
