"""Task 34 step 1 pre-work: the runner's `full_run` step.

Same safety as `test_budget.py`: a tmp `.env` with fake values, `httpx.MockTransport` for
the balance, module defaults pointed at missing files, and mockllm (or a fake
`inspect_eval`) in place of every real model. Nothing here reaches the gateway."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from inspect_ai.log import read_eval_log
from inspect_ai.model import get_model

from temptation_bench import budget, run
from temptation_bench.budget import STEP_CAPS, BudgetError
from temptation_bench.harness.routes import model_args_for
from temptation_bench.harness.task import temptation_bench
from tests.test_budget import FAKE_KEY, _mock_window, credits, never_called

SMOKE = {
    "step": "smoke",
    "actual": 0.014449245000001554,
    "runs": 1,
    "total_tokens": 434288,
    "models": [run.HAIKU],
}
FULL_TOKEN_LIMIT = 2 * 3 * 434_288  # 2,605,728: 2 x (3 x the smoke's tokens per run)


@pytest.fixture(autouse=True)
def no_real_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, "ENV_PATH", tmp_path / "missing" / ".env")
    monkeypatch.setattr(budget, "LEDGER_PATH", tmp_path / "missing" / "ledger.jsonl")
    monkeypatch.setenv("PEOPLE_PROSE_DIR", str(tmp_path / "people_prose"))
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))


@pytest.fixture
def env(tmp_path):
    p = tmp_path / "fake.env"
    p.write_text(f"XPL_API_KEY={FAKE_KEY}\nXPL_BASE_URL=https://gw.example.invalid/v1\n")
    return p


@pytest.fixture
def ledger(tmp_path):
    p = tmp_path / "ledger.jsonl"
    p.write_text(json.dumps(SMOKE) + "\n")
    return p


def _lines(ledger: Path) -> list[dict]:
    return [json.loads(x) for x in ledger.read_text().splitlines() if x.strip()]


def _kw(tmp_path, env, ledger, transport=None):
    return dict(
        log_root=tmp_path / "logs",
        env_path=env,
        ledger_path=ledger,
        transport=transport or credits(),
        display="none",
    )


def _fake_eval(monkeypatch, calls: list):
    def fake(task, **kw):
        calls.append({"task": task, **kw})
        return []

    monkeypatch.setattr(run, "inspect_eval", fake)


def test_full_run_plan_is_one_haiku_run_full_seed_1001_dose_30k():
    spec = run.STEPS["full_run"]
    assert spec.built and not spec.split_models
    p = spec.plan
    assert p.models == (run.HAIKU,) and p.variant == "full"
    assert p.seeds == "1001" and p.doses == "3000000" and p.people == "template"
    assert p.max_samples == 1 and p.retry_on_error == 1 and p.attempts == 2
    assert p.runs == 1


def test_full_run_defaults_cost_limit_half_dollar_and_its_own_token_limit(ledger):
    assert run.STEPS["full_run"].plan.token_limit == FULL_TOKEN_LIMIT == 2_605_728
    assert run.STEPS["full_run"].plan.sample_cost_limit == 0.50
    # $0.50, not 2 x the smoke actual (the mini_batch rule), and no smoke line needed
    assert run.default_sample_cost_limit("full_run", ledger) == 0.50
    ledger.write_text("")
    assert run.default_sample_cost_limit("full_run", ledger) == 0.50


def test_full_run_exposure_is_one_dollar_within_the_cap(ledger):
    p = run.STEPS["full_run"].plan
    assert run.exposure(p, 0.50) == pytest.approx(1.00)
    line = run.check_exposure("full_run", p, 0.50, FULL_TOKEN_LIMIT, spent=0.0)
    assert line == "$1.0000 (1 runs x $0.5000 x 2 attempts)"
    assert 1.00 <= STEP_CAPS["full_run"] == 1.50


def test_full_run_dry_run_prints_the_whole_plan(tmp_path, monkeypatch, capsys, env, ledger):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    assert run.run_step("full_run", 1.2, dry_run=True, **_kw(tmp_path, env, ledger)) is None
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "step:              full_run" in out
    assert "models:            anthropic/claude-haiku-5-5" in out
    assert "variant:           full (people=template)" in out
    assert "days:              D1-D30" in out
    assert "seeds x doses:     1001 x 3000000 = 1 cells" in out
    assert "runs:              1" in out
    assert "max_samples:       1" in out
    assert "retry_on_error:    1" in out
    assert "sample cost_limit: $0.5000 (step default)" in out
    assert (
        f"token_limit:       {FULL_TOKEN_LIMIT} (step default: 2 x 3 x the smoke's 434288 "
        "tokens per run, full mode)" in out
    )
    assert "time_limit:        10800 s (variant full)" in out
    assert "turn caps:         600 per run, 40 per day (variant full)" in out
    assert "exposure:          $1.0000 (1 runs x $0.5000 x 2 attempts)" in out
    assert "estimate / cap:    $1.2000 / $1.50" in out
    assert "local cache:       on, per-cell scope (as the smoke)" in out
    assert f"log dir:           {tmp_path / 'logs'}/full_run-" in out
    assert "template" in out and "D11" not in out  # no prose fallback note for template
    assert calls == [] and len(_lines(ledger)) == 1


def test_full_run_dry_run_notes_the_prose_fallback_past_d10(
    tmp_path, monkeypatch, capsys, env, ledger
):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    spec = run.STEPS["full_run"]
    monkeypatch.setitem(
        run.STEPS, "full_run", replace(spec, plan=replace(spec.plan, people="prose"))
    )
    monkeypatch.setattr(run, "check_prose", lambda plan: None)  # no pregen files in tmp
    run.run_step("full_run", 1.2, dry_run=True, **_kw(tmp_path, env, ledger))
    out = capsys.readouterr().out
    assert "variant:           full (people=prose)" in out
    assert "D11-D30 people messages use the template" in out


def test_full_run_token_limit_flag_overrides_the_step_default(
    tmp_path, monkeypatch, capsys, env, ledger
):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    run.run_step("full_run", 1.2, token_limit=2_000_000, dry_run=True, **_kw(tmp_path, env, ledger))
    assert "token_limit:       2000000 (--token-limit)" in capsys.readouterr().out


def test_full_run_launch_passes_the_limits_and_records_one_run(tmp_path, monkeypatch, env, ledger):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    entry = run.run_step("full_run", 1.2, **_kw(tmp_path, env, ledger))
    [c] = calls
    assert c["model"] == run.HAIKU and c["model_args"] == model_args_for(run.HAIKU)
    assert c["max_samples"] == 1 and c["retry_on_error"] == 1
    assert c["cost_limit"] == 0.50
    task = c["task"]
    assert task.token_limit == FULL_TOKEN_LIMIT
    assert task.time_limit == 10800
    assert len(task.dataset) == 1
    [sample] = task.dataset
    assert sample.metadata["variant"] == "full" and sample.metadata["seed"] == 1001
    assert sample.metadata["dose"] == 3_000_000 and sample.metadata["people"] == "template"
    assert Path(c["log_dir"]).parent == tmp_path / "logs"
    assert Path(c["log_dir"]).name.startswith("full_run-")
    [line] = _lines(ledger)[1:]
    assert line is not None and entry["runs"] == 1
    assert line["step"] == "full_run" and line["runs"] == 1 and line["models"] == [run.HAIKU]
    assert line["estimate"] == 1.2


def test_full_mode_task_time_limit_is_three_hours():
    assert temptation_bench(variant="full").time_limit == 10800
    assert temptation_bench(variant="window").time_limit == 3600


def test_full_run_sample_cost_limit_flag_overrides_and_is_still_checked(
    tmp_path, monkeypatch, env, ledger
):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    run.run_step("full_run", 1.2, sample_cost_limit=0.70, **_kw(tmp_path, env, ledger))
    assert calls[0]["cost_limit"] == 0.70  # 1 x 0.70 x 2 = 1.40 <= 1.50
    with pytest.raises(BudgetError, match="over the full_run cap"):  # 1 x 0.80 x 2 = 1.60
        run.run_step(
            "full_run", 1.2, sample_cost_limit=0.80, **_kw(tmp_path, env, ledger, never_called())
        )
    assert len(calls) == 1


def test_full_run_refuses_an_estimate_over_the_cap(tmp_path, monkeypatch, env, ledger):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    with pytest.raises(BudgetError, match="cap"):
        run.run_step("full_run", 1.6, **_kw(tmp_path, env, ledger))
    assert calls == [] and len(_lines(ledger)) == 1


def test_full_run_refuses_over_the_stop_line(tmp_path, monkeypatch, env, ledger):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    with ledger.open("a") as f:
        f.write(json.dumps({"step": "mini_batch", "actual": 8.6}) + "\n")  # 8.61 + 1.00 > 9.50
    with pytest.raises(BudgetError, match="stop line"):
        run.run_step("full_run", 0.5, **_kw(tmp_path, env, ledger, never_called()))
    assert calls == []


def test_full_run_counts_earlier_full_run_spend_against_its_cap(tmp_path, monkeypatch, env, ledger):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    with ledger.open("a") as f:
        f.write(json.dumps({"step": "full_run", "actual": 0.6, "runs": 1}) + "\n")
    with pytest.raises(BudgetError, match="already spent"):  # 0.60 + 1.00 > 1.50
        run.run_step("full_run", 0.5, **_kw(tmp_path, env, ledger, never_called()))
    assert calls == []


def test_full_run_rejects_the_model_selector(tmp_path, env, ledger):
    with pytest.raises(run.RunnerError, match="--model"):
        run.run_step(
            "full_run", 1.0, select_model=run.HAIKU, **_kw(tmp_path, env, ledger, never_called())
        )


@pytest.mark.slow
def test_full_run_mockllm_thirty_days_one_ledger_run(tmp_path, env, ledger):
    model = get_model("mockllm/model", custom_outputs=_mock_window(), memoize=False)
    entry = run.run_step("full_run", 1.2, model=model, **_kw(tmp_path, env, ledger))
    [line] = _lines(ledger)[1:]
    assert line["runs"] == 1 and entry["runs"] == 1 and line["models"] == ["mockllm/model"]
    [path] = line["eval_paths"]
    assert Path(path).parent.name.startswith("full_run-")
    log = read_eval_log(path)
    assert log.status == "success" and len(log.samples) == 1
    [s] = log.samples
    assert s.metadata["variant"] == "full" and s.metadata["seed"] == 1001
    assert log.eval.config.cost_limit == 0.50 and log.eval.config.retry_on_error == 1
    assert log.eval.config.max_samples == 1
    score = next(iter(s.scores.values()))
    assert score.metadata["t1_label"] is not None
