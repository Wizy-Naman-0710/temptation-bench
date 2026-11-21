from inspect_ai.model import get_model_info

from temptation_bench.harness.pricing import register_prices


def test_all_gateway_models_have_cost():
    names = register_prices()
    assert {
        "anthropic/claude-haiku-5-5",
        "openai-api/xpl/gpt-6-luna",
        "openai-api/xpl/qwen3.7-flash",
        "openai-api/xpl/deepseek-v4-flash",
    } <= set(names)
    for n in names:
        assert get_model_info(n).cost is not None
