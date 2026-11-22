"""Task 30: the smoke estimate (DD §13.3), from measured logs or given numbers. No network."""

from __future__ import annotations

import pytest
import yaml
from inspect_ai import Task
from inspect_ai import eval as inspect_eval
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput, ModelUsage, get_model
from inspect_ai.solver import solver

from temptation_bench import estimate, run

USAGES = [  # (input new, cache read, cache write, output)
    (100, 0, 2000, 50),
    (10, 2000, 300, 70),
    (20, 2300, 400, 90),
]


def _out(i, cr, cw, o):
    out = ModelOutput.from_content("mockllm/model", "ok")
    out.usage = ModelUsage(
        input_tokens=i,
        output_tokens=o,
        input_tokens_cache_read=cr,
        input_tokens_cache_write=cw,
        total_tokens=i + cr + cw + o,
    )
    return out


@solver
def _three_turns():
    async def solve(state, generate):
        for _ in USAGES:
            state = await generate(state)
        return state

    return solve


def _log(tmp_path, variant="gfree"):
    model = get_model("mockllm/model", custom_outputs=[_out(*u) for u in USAGES], memoize=False)
    task = Task(
        dataset=[Sample(input="hello", metadata={"variant": variant})], solver=_three_turns()
    )
    [log] = inspect_eval(task, model=model, log_dir=str(tmp_path), display="none")
    return log.location


def test_formula_by_hand():
    p = {"input": 0.10, "output": 0.50, "input_cache_write": 0.125, "input_cache_read": 0.01}
    dollars, lines = estimate.smoke_estimate(40, 5000, 100, 0.8, p)
    per_turn = 5000 * (0.8 * 0.01 + 0.2 * 0.125) + 100 * 0.50  # $/M
    assert dollars == pytest.approx(40 * per_turn / 1e6)
    text = "\n".join(lines)
    assert "T x [I*(h*p_cr + (1-h)*p_miss) + O*p_out]" in text
    assert "p_miss = max(p_in, p_cw) = 0.125" in text


def test_haiku_prices_come_from_pricing_yaml():
    want = yaml.safe_load(estimate.PRICING.read_text())["anthropic/claude-haiku-5-5"]
    assert estimate.haiku_prices() == want


def test_measure_log_reads_turns_tokens_and_hit_share(tmp_path):
    m = estimate.measure_log(_log(tmp_path))
    ins = [i + cr + cw for i, cr, cw, _ in USAGES]
    assert m.turns == 3
    assert m.mean_input == pytest.approx(sum(ins) / 3)
    assert m.mean_output == pytest.approx((50 + 70 + 90) / 3)
    assert m.hit_share == pytest.approx((0 + 2000 + 2300) / sum(ins))
    assert m.days == 3  # gfree last_day


def test_smoke_turns_scale_to_the_window_days(tmp_path):
    m = estimate.measure_log(_log(tmp_path))
    assert estimate.window_turns(m) == pytest.approx(3 * 10 / 3)


def test_cli_from_log_prints_the_arithmetic(tmp_path, capsys):
    path = _log(tmp_path)
    assert run.main(["--estimate-smoke", "--from-log", str(path)]) == 0
    out = capsys.readouterr().out
    assert "turns 3 over 3 days" in out and "T = 10.0" in out
    assert "smoke estimate: $" in out


def test_cli_given_numbers_and_overrides(capsys):
    args = ["--estimate-smoke", "--turns", "40", "--mean-input", "5000"]
    args += ["--mean-output", "100", "--hit-share", "0.8"]
    assert run.main(args) == 0
    out = capsys.readouterr().out
    p = estimate.haiku_prices()
    dollars, _ = estimate.smoke_estimate(40, 5000, 100, 0.8, p)
    assert f"smoke estimate: ${dollars:.4f}" in out


def test_cli_needs_a_log_or_all_four_numbers(capsys):
    assert run.main(["--estimate-smoke", "--turns", "40"]) != 0
    assert "--from-log" in capsys.readouterr().err


def test_cli_refuses_a_hit_share_outside_0_1(capsys):
    args = ["--estimate-smoke", "--turns", "4", "--mean-input", "5", "--mean-output", "1"]
    assert run.main([*args, "--hit-share", "1.5"]) != 0
