"""Task 31 pre-work: the `people` role model swap (PROGRESS §8, Task 30 ruling).

The spec (§5, §7.1) names `qwen3.7-flash`; the gateway refuses it with a 403 (the owner's
account routes no-training models only), so the people role is now
`mistral-small-3.2-24b-instruct`, a non-reasoning model. Inspect's openai-api chat
completions builder sends `reasoning_effort` whenever the config sets it, whatever the
model (`inspect_ai/model/_openai.py` `openai_completion_params`), so the people configs are
built without it. No network: models are only built (fake key, `.invalid` URL)."""

from __future__ import annotations

import yaml
from inspect_ai.model import GenerateConfig, get_model
from inspect_ai.model._openai import openai_completion_params

from temptation_bench import run
from temptation_bench.harness import pregen_people, route_check
from temptation_bench.harness.pricing import DEFAULT_PRICING
from temptation_bench.harness.routes import (
    PEOPLE_MODEL,
    model_args_for,
    route_config,
)

MISTRAL = "openai-api/xpl/mistral-small-3.2-24b-instruct"
FAKE = "fake-not-a-key"
BASE = "https://gw.example.invalid"


def test_people_model_is_mistral_small_everywhere():
    assert PEOPLE_MODEL == MISTRAL
    assert run.PEOPLE == PEOPLE_MODEL
    assert run.STEPS["route_check"].plan.aux_models == (MISTRAL,)
    assert route_check.PEOPLE_MODEL == MISTRAL
    assert model_args_for(MISTRAL) == {"strict_tools": False}


def test_people_price_is_registered_in_the_existing_format():
    prices = yaml.safe_load(DEFAULT_PRICING.read_text())
    assert prices[MISTRAL] == {
        "input": 0.094,
        "output": 0.25,
        "input_cache_write": 0.0,
        "input_cache_read": 0.01,
    }


def test_inspect_openai_api_sends_reasoning_effort_for_any_model():
    """Tripwire: why the people configs drop it (an unknown model still gets the field)."""
    api = get_model(MISTRAL, api_key=FAKE, base_url=BASE, memoize=False).api
    sent = api.completion_params(GenerateConfig(reasoning_effort="low"), tools=False)
    assert sent["reasoning_effort"] == "low"
    assert "reasoning_effort" in openai_completion_params(
        "xpl/unknown-model", GenerateConfig(reasoning_effort="low"), tools=False
    )


def test_route_config_drops_reasoning_effort_for_the_people_model_only():
    c = GenerateConfig(reasoning_effort="low", max_retries=5, max_tokens=99)
    people = route_config(MISTRAL, c)
    assert people.reasoning_effort is None
    assert (people.max_retries, people.max_tokens) == (5, 99)
    assert c.reasoning_effort == "low"  # the input is never changed
    for slug in (run.HAIKU, run.LUNA, "mockllm/model"):
        assert route_config(slug, c).reasoning_effort == "low"


def test_people_request_body_has_no_reasoning_effort():
    """What the provider would send for the pregen and route-check people calls."""
    api = get_model(MISTRAL, api_key=FAKE, base_url=BASE, memoize=False).api
    for cfg in (
        pregen_people.rewrite_config(MISTRAL),
        route_check.call_config(MISTRAL, route_check.PEOPLE_MAX_TOKENS),
    ):
        assert cfg.reasoning_effort is None
        assert "reasoning_effort" not in api.completion_params(cfg, tools=False)
    # the agent routes keep effort low (spec D5)
    assert route_check.call_config(run.HAIKU, 512).reasoning_effort == "low"


def test_pregen_config_is_small_and_has_no_local_cache():
    cfg = pregen_people.rewrite_config(MISTRAL)
    assert cfg.max_tokens == pregen_people.PREGEN_MAX_TOKENS <= 256
    assert cfg.max_retries == 5
    assert cfg.cache is None


def test_route_check_worst_case_prices_the_people_model():
    total, how = route_check.worst_case()
    assert "1 people x" in how and "$0.094/M" in how and "$0.25/M" in how
    assert total <= run.STEP_CAPS["route_check"]
