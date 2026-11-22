"""Task 31 pre-work: the runner's `pregen` and `mini_batch` steps.

Same safety as `test_budget.py`: a tmp `.env` with fake values, `httpx.MockTransport` for
the balance, module defaults pointed at missing files, and mockllm (or a fake
`inspect_eval`) in place of every real model. Nothing here reaches the gateway."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from inspect_ai.event import ModelEvent
from inspect_ai.log import read_eval_log
from inspect_ai.model import get_model

from temptation_bench import budget, run
from temptation_bench.budget import STEP_CAPS, BudgetError
from temptation_bench.engine.config import load_config
from temptation_bench.engine.people import prose_jobs
from temptation_bench.harness import pregen_people
from tests.harness.test_pregen import _people_mock, _prose_file
from tests.test_budget import FAKE_KEY, _mock_window, credits, never_called

SEEDS = (1001, 1002, 1003)
SMOKE = {
    "step": "smoke",
    "actual": 0.014449245000001554,
    "runs": 1,
    "total_tokens": 434288,
    "models": [run.HAIKU],
}


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


@pytest.fixture
def prose(tmp_path):
    d = tmp_path / "people_prose"
    for seed in SEEDS:
        _prose_file(d, seed)
    return d


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


def _fake_eval(monkeypatch, calls: list, fail_first: bool = False):
    def fake(task, **kw):
        calls.append(kw)
        if fail_first and len(calls) == 1:
            raise RuntimeError("upstream down")
        return []

    monkeypatch.setattr(run, "inspect_eval", fake)


# ---- pregen ---------------------------------------------------------------------------------


def _n_jobs() -> int:
    cfg = load_config("window")
    return sum(len(prose_jobs(cfg, s, pregen_people.PREGEN_DAYS)) for s in SEEDS)


def test_pregen_is_built_for_three_seeds_with_the_people_model():
    spec = run.STEPS["pregen"]
    assert spec.built
    p = spec.plan
    assert p.models == (run.PEOPLE,) and p.seeds == "1001,1002,1003"
    assert p.retry_on_error == 0 and p.attempts == 1
    assert p.runs == _n_jobs() == 39  # one sample per text (13 + 16 + 10)


def test_pregen_worst_case_fits_its_cap():
    total, how = run.STEPS["pregen"].exposure()
    assert 0 < total <= STEP_CAPS["pregen"]
    assert f"{_n_jobs()} samples" in how and f"{pregen_people.PREGEN_MAX_TOKENS} out" in how
    assert "$0.094/M" in how and "$0.25/M" in how and "attempts" in how


def test_pregen_dry_run_prints_the_plan_and_launches_nothing(
    tmp_path, monkeypatch, capsys, env, ledger
):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    assert run.run_step("pregen", 0.01, dry_run=True, **_kw(tmp_path, env, ledger)) is None
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "step:              pregen" in out
    assert f"models:            {run.PEOPLE} (people)" in out
    assert "samples:           39 (D1-D10 exogenous texts" in out
    assert "local cache:       off" in out and "retry_on_error:    0" in out
    assert "token_limit:       none" in out
    assert "configs/people_prose" in out or "people_prose" in out
    assert calls == [] and len(_lines(ledger)) == 1


def test_pregen_launch_sets_the_people_role_and_no_rerun(tmp_path, monkeypatch, env, ledger):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    with pytest.raises(run.CheckFailed):  # the fake eval writes no seed file
        run.run_step("pregen", 0.01, **_kw(tmp_path, env, ledger))
    entry = _lines(ledger)[-1]
    [kw] = calls
    assert kw["model"] == run.PEOPLE and kw["model_roles"] == {"people": run.PEOPLE}
    assert kw["model_args"] == {"strict_tools": False}
    assert kw["retry_on_error"] == 0 and kw["max_samples"] == 2
    assert kw["cost_limit"] == pytest.approx(STEP_CAPS["pregen"] / 39)
    assert entry["step"] == "pregen" and entry["runs"] == 39 and entry["models"] == [run.PEOPLE]


def test_pregen_refuses_over_its_cap(tmp_path, monkeypatch, env, ledger):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    with pytest.raises(BudgetError, match="cap"):
        run.run_step("pregen", 0.06, **_kw(tmp_path, env, ledger))
    assert calls == [] and len(_lines(ledger)) == 1


def test_pregen_mockllm_writes_three_seed_files_and_records(tmp_path, env, ledger, capsys):
    people = get_model("mockllm/model", custom_outputs=_people_mock, memoize=False)
    entry = run.run_step("pregen", 0.01, model=people, **_kw(tmp_path, env, ledger))
    out_dir = tmp_path / "people_prose"
    for seed in SEEDS:
        doc = json.loads((out_dir / f"seed_{seed}.json").read_text())
        assert doc["seed"] == seed and doc["texts"]
    assert entry["runs"] == 39 and entry["step"] == "pregen"
    [path] = entry["eval_paths"]
    log = read_eval_log(path)
    assert log.status == "success" and len(log.samples) == 39
    assert log.eval.config.retry_on_error == 0
    events = [e for s in log.samples for e in s.events if isinstance(e, ModelEvent)]
    assert len(events) == 39 and all(e.cache is None for e in events)  # local cache off
    out = capsys.readouterr().out
    assert "pregen: seed_1001.json" in out and "rejected" in out


def test_pregen_verify_fails_when_a_seed_file_is_missing(tmp_path, monkeypatch, env, ledger):
    calls: list = []
    _fake_eval(monkeypatch, calls)  # writes no file
    code = run.main(["--step", "pregen", "--estimate", "0.01"], **_kw(tmp_path, env, ledger))
    assert code == 1 and len(_lines(ledger)) == 2  # recorded, then the check failed


# ---- mini_batch ------------------------------------------------------------------------------


def test_mini_batch_plan_is_two_models_window_prose_three_seeds_two_doses():
    spec = run.STEPS["mini_batch"]
    assert spec.built and spec.split_models
    p = spec.plan
    assert p.models == (run.HAIKU, run.LUNA)
    assert (p.variant, p.people, p.seeds, p.doses) == (
        "window",
        "prose",
        "1001,1002,1003",
        "0,3000000",
    )
    assert p.max_samples == 2 and p.retry_on_error == 1
    assert p.runs == 12


def test_luna_is_priced():
    import yaml

    from temptation_bench.harness.pricing import DEFAULT_PRICING

    prices = yaml.safe_load(DEFAULT_PRICING.read_text())
    assert prices[run.LUNA]["input"] > 0 and prices[run.LUNA]["output"] > 0


def test_mini_batch_cost_limit_is_twice_the_smoke_actual(ledger):
    assert run.default_sample_cost_limit("mini_batch", ledger) == pytest.approx(2 * SMOKE["actual"])
    assert run.default_token_limit(ledger) == 868_576


def test_mini_batch_dry_run_prints_both_evals(tmp_path, monkeypatch, capsys, env, ledger, prose):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    run.run_step("mini_batch", 1.0, dry_run=True, **_kw(tmp_path, env, ledger))
    out = capsys.readouterr().out
    limit = 2 * SMOKE["actual"]
    assert out.count("sample cost_limit: $0.0289") == 2
    assert f"exposure:          ${12 * limit * 2:.4f} (12 runs x ${limit:.4f} x 2 attempts)" in out
    assert "eval 1 of 2: anthropic/claude-haiku-5-5" in out
    assert "eval 2 of 2: openai-api/xpl/gpt-6-luna" in out
    assert out.count("seeds x doses:     1001,1002,1003 x 0,3000000 = 6 cells") == 2
    assert out.count("variant:           window (people=prose)") == 2
    assert out.count("token_limit:       868576 (2 x smoke mean)") == 2
    assert out.count("max_samples:       2") == 2
    assert calls == [] and len(_lines(ledger)) == 1


def test_mini_batch_runs_one_eval_per_model_and_records_each(
    tmp_path, monkeypatch, env, ledger, prose
):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    run.run_step("mini_batch", 1.0, **_kw(tmp_path, env, ledger))
    assert [c["model"] for c in calls] == [run.HAIKU, run.LUNA]
    assert calls[1]["model_args"] == {"strict_tools": False}
    for c in calls:
        assert c["max_samples"] == 2 and c["retry_on_error"] == 1
        assert c["cost_limit"] == pytest.approx(2 * SMOKE["actual"])
    assert calls[0]["log_dir"] != calls[1]["log_dir"]
    lines = _lines(ledger)[1:]
    assert [ln["models"] for ln in lines] == [[run.HAIKU], [run.LUNA]]
    assert [ln["runs"] for ln in lines] == [6, 6]
    assert all(ln["step"] == "mini_batch" for ln in lines)
    assert sum(ln["estimate"] for ln in lines) == pytest.approx(1.0)


def test_mini_batch_model_selector_runs_only_that_eval(tmp_path, monkeypatch, env, ledger, prose):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    code = run.main(
        ["--step", "mini_batch", "--estimate", "0.5", "--model", run.LUNA],
        **_kw(tmp_path, env, ledger),
    )
    assert code == 0
    assert [c["model"] for c in calls] == [run.LUNA]
    [line] = _lines(ledger)[1:]
    assert line["models"] == [run.LUNA] and line["runs"] == 6 and line["estimate"] == 0.5


def test_model_selector_refuses_an_unknown_model_or_step(tmp_path, monkeypatch, env, ledger, prose):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    with pytest.raises(run.RunnerError, match="not a model of"):
        run.run_step(
            "mini_batch",
            0.5,
            select_model="openai-api/xpl/other",
            **_kw(tmp_path, env, ledger, never_called()),
        )
    with pytest.raises(run.RunnerError, match="--model"):
        run.run_step(
            "smoke", 0.5, select_model=run.HAIKU, **_kw(tmp_path, env, ledger, never_called())
        )
    assert calls == [] and len(_lines(ledger)) == 1


def test_mini_batch_refuses_a_worst_case_over_the_cap(tmp_path, monkeypatch, env, ledger, prose):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    with pytest.raises(BudgetError, match="cap"):  # 12 x 0.25 x 2 = 6.00 > 5.00
        run.run_step(
            "mini_batch", 1.0, sample_cost_limit=0.25, **_kw(tmp_path, env, ledger, never_called())
        )
    assert calls == [] and len(_lines(ledger)) == 1


def test_mini_batch_refuses_over_the_stop_line(tmp_path, monkeypatch, env, ledger, prose):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    with ledger.open("a") as f:
        f.write(json.dumps({"step": "route_check", "actual": 8.9}) + "\n")  # 8.91 + 0.69 > 9.50
    with pytest.raises(BudgetError, match="stop line"):
        run.run_step("mini_batch", 0.5, **_kw(tmp_path, env, ledger, never_called()))
    assert calls == []


def test_mini_batch_counts_earlier_mini_batch_spend_against_its_cap(
    tmp_path, monkeypatch, env, ledger, prose
):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    with ledger.open("a") as f:
        f.write(json.dumps({"step": "mini_batch", "actual": 4.5, "runs": 6}) + "\n")
    with pytest.raises(BudgetError, match="already spent"):  # 4.50 + 0.69 > 5.00
        run.run_step("mini_batch", 0.4, **_kw(tmp_path, env, ledger, never_called()))
    assert calls == []


def test_mini_batch_refuses_without_the_prose_files(tmp_path, monkeypatch, env, ledger):
    calls: list = []
    _fake_eval(monkeypatch, calls)
    with pytest.raises(run.RunnerError, match="--step pregen"):
        run.run_step("mini_batch", 1.0, **_kw(tmp_path, env, ledger, never_called()))
    assert calls == [] and len(_lines(ledger)) == 1


def test_mini_batch_stops_after_an_eval_that_raises(tmp_path, monkeypatch, env, ledger, prose):
    calls: list = []
    _fake_eval(monkeypatch, calls, fail_first=True)
    with pytest.raises(RuntimeError, match="upstream down"):
        run.run_step("mini_batch", 1.0, **_kw(tmp_path, env, ledger))
    assert [c["model"] for c in calls] == [run.HAIKU]  # Luna never launched
    [line] = _lines(ledger)[1:]
    assert line["models"] == [run.HAIKU] and "upstream down" in line["error"]


@pytest.mark.slow
def test_mini_batch_mockllm_two_evals_ledger_runs_per_eval(tmp_path, env, ledger, prose):
    """rr-6: under a model override each eval's ledger line counts its own 6 runs."""
    model = get_model("mockllm/model", custom_outputs=_mock_window(), memoize=False)
    run.run_step("mini_batch", 1.0, model=model, **_kw(tmp_path, env, ledger))
    lines = _lines(ledger)[1:]
    assert [ln["runs"] for ln in lines] == [6, 6]
    assert [ln["models"] for ln in lines] == [["mockllm/model"], ["mockllm/model"]]
    dirs = [Path(ln["eval_paths"][0]).parent.name for ln in lines]
    assert dirs == ["claude-haiku-5-5", "gpt-6-luna"]  # one log dir per eval
    for ln in lines:
        [path] = ln["eval_paths"]
        log = read_eval_log(path)
        assert log.status == "success" and len(log.samples) == 6
        assert {s.metadata["people"] for s in log.samples} == {"prose"}
        assert {(s.metadata["seed"], s.metadata["dose"]) for s in log.samples} == {
            (s, d) for s in SEEDS for d in (0, 3_000_000)
        }
        assert log.eval.config.max_samples == 2
