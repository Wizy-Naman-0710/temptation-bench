from inspect_ai.model import get_model_info

from temptation_bench.harness.pricing import register_prices


def test_all_gateway_models_have_cost():
    names = register_prices()
    assert {
        "anthropic/claude-haiku-5-5",
        "openai-api/xpl/gpt-6-luna",
        "openai-api/xpl/qwen3.7-flash",  # spec people model (kept: older ledger lines)
        "openai-api/xpl/mistral-small-3.2-24b-instruct",  # people model since Task 31
        "openai-api/xpl/deepseek-v4-flash",
    } <= set(names)
    for n in names:
        assert get_model_info(n).cost is not None


# ---- Task 29 pre-work: cost data for both gateway slugs, offline ---------------------------

FAKE = "fake-not-a-key"
BASE = "https://gw.example.invalid"


def _no_http(monkeypatch):
    import httpx

    def boom(*a, **k):
        raise AssertionError("network call during a price lookup")

    monkeypatch.setattr(httpx.Client, "send", boom)
    monkeypatch.setattr(httpx.AsyncClient, "send", boom)


def _resolved(model):
    from types import SimpleNamespace

    return SimpleNamespace(task=SimpleNamespace(cost_limit=None), model=model, model_roles=None)


def test_inspect_has_no_built_in_price_for_the_gateway_slugs(monkeypatch):
    """Why the registration matters: without it Inspect's `cost_limit` gate refuses."""
    import pytest
    from inspect_ai._util.error import PrerequisiteError
    from inspect_ai.model import get_model
    from inspect_ai.model._model_info import clear_model_info_cache
    from inspect_ai.model._util import resolve_model_costs

    _no_http(monkeypatch)
    clear_model_info_cache()
    try:
        for slug in ("anthropic/claude-haiku-5-5", "openai-api/xpl/gpt-6-luna"):
            m = get_model(slug, api_key=FAKE, base_url=BASE)
            with pytest.raises(PrerequisiteError, match="cost data"):
                resolve_model_costs([_resolved(m)], 1.0)
    finally:
        register_prices()


def test_runner_slugs_resolve_a_price_before_the_eval_without_network(tmp_path, monkeypatch):
    """The runner builds the task (which registers the §7 prices) before `inspect_eval`;
    Inspect's own `cost_limit` gate then finds a price for each runner slug."""
    import yaml
    from inspect_ai.model import get_model
    from inspect_ai.model._model_info import _get_model_info_direct, clear_model_info_cache
    from inspect_ai.model._util import resolve_model_costs

    from temptation_bench import run
    from temptation_bench.harness.pricing import DEFAULT_PRICING

    _no_http(monkeypatch)
    prices = yaml.safe_load(DEFAULT_PRICING.read_text())
    for step in ("gfree", "smoke"):
        clear_model_info_cache()
        seen: list[str] = []

        def fake_eval(task, *, model, cost_limit, seen=seen, **kw):
            m = get_model(model, api_key=FAKE, base_url=BASE)  # what Inspect resolves
            resolve_model_costs([_resolved(m)], cost_limit)  # raises if no cost data
            cost = _get_model_info_direct(m).cost
            want = prices[model]
            assert (cost.input, cost.output) == (want["input"], want["output"])
            seen.append(model)

        monkeypatch.setattr(run, "inspect_eval", fake_eval)
        plan = run.STEPS[step].plan
        run.launch_task_eval(run.Ctx(step, plan, tmp_path, 1.0, 800_000))
        assert seen == [plan.models[0]]
    assert {run.HAIKU, run.LUNA} == {"anthropic/claude-haiku-5-5", "openai-api/xpl/gpt-6-luna"}
