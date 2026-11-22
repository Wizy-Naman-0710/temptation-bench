"""Task 30: the runner's `route_check` step, `--reuse-cache`, and the smoke plan.

Same safety as `test_budget.py`: a tmp `.env` with fake values, `httpx.MockTransport` for
the balance, module defaults pointed at missing files, Haiku through a local fake SDK
client (`fake_haiku`), qwen replaced by mockllm."""

from __future__ import annotations

import dataclasses
import json

import pytest
from inspect_ai.event import ModelEvent
from inspect_ai.log import read_eval_log
from inspect_ai.model import get_model

from temptation_bench import budget, run
from temptation_bench.budget import STEP_CAPS, BudgetError
from temptation_bench.harness import route_check as rc
from tests.harness.test_route_check import fake_haiku
from tests.test_budget import FAKE_KEY, credits, never_called

REAL_ROUTE_CHECK = run.STEPS["route_check"]  # before the fixture below swaps the people model


@pytest.fixture(autouse=True)
def no_real_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, "ENV_PATH", tmp_path / "missing" / ".env")
    monkeypatch.setattr(budget, "LEDGER_PATH", tmp_path / "missing" / "ledger.jsonl")
    # never the real qwen route: the people call goes to mockllm
    spec = run.STEPS["route_check"]
    mock_plan = dataclasses.replace(spec.plan, aux_models=("mockllm/model",))
    monkeypatch.setitem(run.STEPS, "route_check", dataclasses.replace(spec, plan=mock_plan))


@pytest.fixture
def env(tmp_path):
    p = tmp_path / "fake.env"
    p.write_text(f"XPL_API_KEY={FAKE_KEY}\nXPL_BASE_URL=https://gw.example.invalid/v1\n")
    return p


@pytest.fixture
def ledger(tmp_path):
    p = tmp_path / "ledger.jsonl"
    p.write_text("")
    return p


def _no_eval(monkeypatch):
    def no_eval(*a, **k):  # pragma: no cover
        raise AssertionError("eval must not run")

    monkeypatch.setattr(run, "inspect_eval", no_eval)


def _main(tmp_path, env, ledger, args, model=None, sub="logs"):
    return run.main(
        ["--step", "route_check", "--estimate", "0.01", *args],
        model=model,
        log_root=tmp_path / sub,
        env_path=env,
        ledger_path=ledger,
        transport=credits(),
        display="none",
    )


def _lines(ledger):
    return [json.loads(x) for x in ledger.read_text().splitlines() if x.strip()]


def test_route_check_is_built_with_one_attempt():
    spec = REAL_ROUTE_CHECK
    assert spec.built
    assert spec.plan.models == (run.HAIKU,) and spec.plan.attempts == 1
    assert spec.plan.aux_models == (rc.PEOPLE_MODEL,) == ("openai-api/xpl/qwen3.7-flash",)


def test_route_check_runs_records_and_passes(
    tmp_path,
    env,
    ledger,
    allow_fake_client,
    capsys,
):
    calls: list[dict] = []
    code = _main(tmp_path, env, ledger, [], model=fake_haiku(calls))
    out = capsys.readouterr()
    assert code == 0, out.err
    assert len(calls) == 2
    assert "PASS  call 2 cache_read > 0" in out.out
    assert "FAIL" not in out.out
    [line] = _lines(ledger)
    assert line["step"] == "route_check" and line["runs"] == 1
    assert line["models"][0] == run.HAIKU and len(line["models"]) == 2
    [path] = line["eval_paths"]
    assert "/route_check-" in path
    log = read_eval_log(path)
    assert line["actual"] == pytest.approx(
        sum(u.total_cost or 0 for u in log.stats.model_usage.values())
    )
    assert line["actual"] > 0
    assert log.eval.config.retry_on_error == 0
    assert log.eval.config.cost_limit == pytest.approx(STEP_CAPS["route_check"])


def test_route_check_fail_exits_nonzero_with_the_fallback_note(tmp_path, env, ledger, capsys):
    code = _main(tmp_path, env, ledger, [], model=get_model("mockllm/model"))
    out = capsys.readouterr()
    assert code != 0
    assert "FAIL  call 1 request effort low" in out.out
    assert "route fallback needs a fresh owner OK" in out.err
    [line] = _lines(ledger)  # recorded once; no second route was tried
    assert line["step"] == "route_check"
    assert len(list((tmp_path / "logs").iterdir())) == 1
    assert FAKE_KEY not in out.out + out.err


def test_reuse_cache_only_for_route_check(tmp_path, env, ledger, capsys):
    code = run.main(
        ["--step", "smoke", "--estimate", "0.3", "--reuse-cache", "--dry-run"],
        log_root=tmp_path,
        env_path=env,
        ledger_path=ledger,
        transport=never_called(),
    )
    assert code != 0 and "--reuse-cache" in capsys.readouterr().err
    assert ledger.read_text() == ""


def test_reuse_cache_second_run_is_free_and_all_read(
    tmp_path,
    env,
    ledger,
    allow_fake_client,
    capsys,
):
    calls: list[dict] = []
    assert _main(tmp_path, env, ledger, ["--reuse-cache"], model=fake_haiku(calls), sub="a") == 0
    assert len(calls) == 2
    assert _main(tmp_path, env, ledger, ["--reuse-cache"], model=fake_haiku(calls), sub="b") == 0
    assert len(calls) == 2  # the second process made no provider call
    out = capsys.readouterr().out
    assert "all 3 calls read from the local response cache" in out
    first, second = _lines(ledger)
    assert first["actual"] > 0 and second["actual"] == 0
    [sample] = read_eval_log(second["eval_paths"][0]).samples
    assert {e.cache for e in sample.events if isinstance(e, ModelEvent)} == {"read"}


def test_route_check_dry_run_prints_the_token_worst_case(
    tmp_path, monkeypatch, env, ledger, capsys
):
    _no_eval(monkeypatch)
    assert _main(tmp_path, env, ledger, ["--dry-run"]) == 0
    out = capsys.readouterr().out
    dollars, how = rc.worst_case()
    assert f"exposure:          ${dollars:.4f} ({how})" in out
    assert "local cache:       off" in out
    assert "mockllm/model (people)" in out and run.HAIKU in out
    assert ledger.read_text() == ""
    assert _main(tmp_path, env, ledger, ["--dry-run", "--reuse-cache"]) == 0
    assert "local cache:       on (scope route_check=fixed-v1)" in capsys.readouterr().out


def test_route_check_refuses_a_worst_case_over_the_cap(tmp_path, monkeypatch, env, ledger):
    _no_eval(monkeypatch)
    monkeypatch.setattr(rc, "worst_case", lambda: (0.06, "too much"))
    with pytest.raises(BudgetError, match="cap"):
        run.run_step(
            "route_check",
            0.01,
            log_root=tmp_path,
            env_path=env,
            ledger_path=ledger,
            transport=never_called(),
        )
    assert ledger.read_text() == ""


def test_route_check_refuses_over_the_stop_line(tmp_path, monkeypatch, env, ledger):
    _no_eval(monkeypatch)
    ledger.write_text(json.dumps({"step": "smoke", "actual": 9.49}) + "\n")
    with pytest.raises(BudgetError, match="stop line"):
        run.run_step(
            "route_check",
            0.0,
            log_root=tmp_path,
            env_path=env,
            ledger_path=ledger,
            transport=never_called(),
        )


# ---- the smoke plan --------------------------------------------------------------------------


def test_smoke_dry_run_plan_is_haiku_window_1001_30k_at_half_a_dollar(
    tmp_path,
    monkeypatch,
    env,
    ledger,
    capsys,
):
    _no_eval(monkeypatch)
    code = run.main(
        ["--step", "smoke", "--estimate", "0.3", "--dry-run"],
        log_root=tmp_path,
        env_path=env,
        ledger_path=ledger,
        transport=credits(),
    )
    assert code == 0
    out = capsys.readouterr().out
    for want in (
        "step:              smoke",
        "models:            anthropic/claude-haiku-5-5",
        "variant:           window (people=template)",
        "seeds x doses:     1001 x 3000000 = 1 cells",
        "retry_on_error:    1",
        "sample cost_limit: $0.5000",
        "token_limit:       none",
        "exposure:          $1.0000 (1 runs x $0.5000 x 2 attempts)",
        "estimate / cap:    $0.3000 / $1.00",
    ):
        assert want in out, want
    assert ledger.read_text() == ""


def test_smoke_plan_sample_cost_limit_1_is_refused(tmp_path, monkeypatch, env, ledger, capsys):
    _no_eval(monkeypatch)
    code = run.main(
        ["--step", "smoke", "--estimate", "0.3", "--sample-cost-limit", "1.00", "--dry-run"],
        log_root=tmp_path,
        env_path=env,
        ledger_path=ledger,
        transport=never_called(),
    )
    assert code != 0
    assert "over the smoke cap" in capsys.readouterr().err
