"""Task 25: the budget guard (fail closed) and the paid runner CLI.

Every test uses a tmp `.env` with fake values and `httpx.MockTransport`. Nothing here may
reach the real gateway or read the real `pilot-1/.env` (an autouse fixture points the
module defaults at missing tmp files, so a forgotten argument fails closed)."""

from __future__ import annotations

import json
import math
import os
import traceback

import httpx
import pytest
from inspect_ai.model import ModelOutput, get_model

from temptation_bench import budget, run
from temptation_bench.budget import STEP_CAPS, STOP_LINE, BudgetError
from temptation_bench.harness.settings import cell_scope, generate_config
from tests.harness.test_e2e_mockllm import SCRIPT, _run, tc

# Not key-shaped for test_no_secrets (the hyphens break the 16-char run), so neither this
# file, its .pyc nor the pytest cache ever holds something that looks like a real key.
FAKE_KEY = "xpl_FAKE-not-a-real-key-0000"
BASE = "https://gw.example.invalid"


@pytest.fixture(autouse=True)
def no_real_defaults(tmp_path, monkeypatch):
    """A call that forgets `env_path`/`ledger_path` hits missing files and refuses."""
    monkeypatch.setattr(budget, "ENV_PATH", tmp_path / "missing" / ".env")
    monkeypatch.setattr(budget, "LEDGER_PATH", tmp_path / "missing" / "ledger.jsonl")


@pytest.fixture
def env(tmp_path):
    p = tmp_path / "fake.env"
    p.write_text(f"XPL_API_KEY={FAKE_KEY}\nXPL_BASE_URL={BASE}/v1\n")
    return p


@pytest.fixture
def ledger(tmp_path):
    p = tmp_path / "ledger.jsonl"
    p.write_text("")
    return p


def credits(total=10.0, usage=1.0, status=200, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json={"data": {"total_credits": total, "total_usage": usage}})

    return httpx.MockTransport(handler)


def never_called():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no network call expected")

    return httpx.MockTransport(handler)


def _line(**kw):
    return json.dumps({"step": "smoke", "actual": 0.0, **kw}) + "\n"


# ---- constants and fetch_balance --------------------------------------------------------


def test_constants_match_spec():
    assert STOP_LINE == 9.50
    assert STEP_CAPS == {
        "gfree": 0.00,
        "route_check": 0.05,
        "smoke": 1.00,
        "pregen": 0.05,
        "mini_batch": 5.00,
        "full_run": 1.50,
    }


def test_fetch_balance_calls_credits_with_bearer(env):
    seen: list[httpx.Request] = []
    bal = budget.fetch_balance(env_path=env, transport=credits(10.0, 1.25, seen=seen))
    assert bal == pytest.approx(8.75)
    [req] = seen
    assert str(req.url) == f"{BASE}/api/v1/credits"
    assert req.method == "GET"
    assert req.headers["authorization"] == f"Bearer {FAKE_KEY}"
    leaked = any(v == FAKE_KEY for v in os.environ.values())
    assert not leaked  # loaded into a local dict, never into os.environ


def test_fetch_balance_accepts_top_level_fields(env):
    t = httpx.MockTransport(
        lambda r: httpx.Response(200, json={"total_credits": 5, "total_usage": 2})
    )
    assert budget.fetch_balance(env_path=env, transport=t) == pytest.approx(3.0)


# ---- check: refusals ----------------------------------------------------------------------


def test_check_refuses_over_stop_line(env, ledger):
    ledger.write_text(_line(actual=9.00) + _line(actual=0.30))
    with pytest.raises(BudgetError, match="stop line"):
        budget.check("smoke", 0.30, env_path=env, ledger_path=ledger, transport=credits())
    # just under the line passes
    budget.check("smoke", 0.20, env_path=env, ledger_path=ledger, transport=credits())


def test_check_refuses_over_step_cap(env, ledger):
    with pytest.raises(BudgetError, match="cap"):
        budget.check("route_check", 0.06, env_path=env, ledger_path=ledger, transport=credits())
    with pytest.raises(BudgetError, match="cap"):
        budget.check("gfree", 0.01, env_path=env, ledger_path=ledger, transport=credits())
    budget.check("gfree", 0.0, env_path=env, ledger_path=ledger, transport=credits())
    budget.check("mini_batch", 5.00, env_path=env, ledger_path=ledger, transport=credits())


def test_check_refuses_unknown_step(env, ledger):
    with pytest.raises(BudgetError, match="unknown step"):
        budget.check("bogus", 0.0, env_path=env, ledger_path=ledger, transport=never_called())


@pytest.mark.parametrize("bad", [-0.01, math.nan, math.inf])
def test_check_refuses_bad_estimate(env, ledger, bad):
    with pytest.raises(BudgetError, match="estimate"):
        budget.check("smoke", bad, env_path=env, ledger_path=ledger, transport=never_called())


def test_check_fails_closed_on_http_error(env, ledger):
    def boom(request):
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(BudgetError, match="balance"):
        budget.check(
            "smoke", 0.1, env_path=env, ledger_path=ledger, transport=httpx.MockTransport(boom)
        )


@pytest.mark.parametrize("status", [401, 403, 404, 500, 302])
def test_check_fails_closed_on_non_200(env, ledger, status):
    with pytest.raises(BudgetError, match=str(status)):
        budget.check(
            "smoke", 0.1, env_path=env, ledger_path=ledger, transport=credits(status=status)
        )


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b'{"data": {}}',
        b'{"data": {"total_credits": "10", "total_usage": 1}}',
        b'{"data": {"total_credits": true, "total_usage": 0}}',
        b'{"data": {"total_credits": NaN, "total_usage": 0}}',
    ],
)
def test_check_fails_closed_on_bad_body(env, ledger, body):
    t = httpx.MockTransport(lambda r: httpx.Response(200, content=body))
    with pytest.raises(BudgetError, match="balance"):
        budget.check("smoke", 0.1, env_path=env, ledger_path=ledger, transport=t)


def test_check_fails_closed_on_negative_balance(env, ledger):
    with pytest.raises(BudgetError, match="negative"):
        budget.check("smoke", 0.1, env_path=env, ledger_path=ledger, transport=credits(1.0, 2.0))


def test_check_refuses_when_balance_below_estimate(env, ledger):
    with pytest.raises(BudgetError, match="balance"):
        budget.check("smoke", 0.5, env_path=env, ledger_path=ledger, transport=credits(1.0, 0.7))


def test_check_fails_closed_on_missing_env(tmp_path, ledger):
    with pytest.raises(BudgetError, match=r"\.env"):
        budget.check(
            "smoke",
            0.1,
            env_path=tmp_path / "nope.env",
            ledger_path=ledger,
            transport=never_called(),
        )


@pytest.mark.parametrize(
    "text",
    [
        f"XPL_BASE_URL={BASE}/v1\n",
        f"XPL_API_KEY={FAKE_KEY}\n",
        f"XPL_API_KEY=\nXPL_BASE_URL={BASE}",
    ],
    ids=["no_key", "no_url", "empty_key"],  # never put the fake key into test ids / cache
)
def test_check_fails_closed_on_missing_keys(tmp_path, ledger, text):
    p = tmp_path / "partial.env"
    p.write_text(text)
    with pytest.raises(BudgetError, match="XPL_"):
        budget.check("smoke", 0.1, env_path=p, ledger_path=ledger, transport=never_called())


def test_check_refuses_plain_http_base_url(tmp_path, ledger):
    p = tmp_path / "http.env"
    p.write_text(f"XPL_API_KEY={FAKE_KEY}\nXPL_BASE_URL=http://gw.example.invalid/v1\n")
    with pytest.raises(BudgetError, match="https"):
        budget.check("smoke", 0.1, env_path=p, ledger_path=ledger, transport=never_called())


def test_check_fails_closed_on_missing_ledger(env, tmp_path):
    with pytest.raises(BudgetError, match="ledger"):
        budget.check(
            "smoke",
            0.1,
            env_path=env,
            ledger_path=tmp_path / "none.jsonl",
            transport=never_called(),
        )


@pytest.mark.parametrize(
    "text",
    ["{not json}\n", '{"step": "smoke"}\n', '{"actual": "0.1"}\n', '{"actual": -1}\n', "[]\n"],
)
def test_spent_fails_closed_on_bad_ledger(tmp_path, text):
    p = tmp_path / "bad.jsonl"
    p.write_text(_line(actual=0.1) + text)
    with pytest.raises(BudgetError, match="ledger"):
        budget.spent(ledger_path=p)


def test_spent_sums_actual(ledger):
    assert budget.spent(ledger_path=ledger) == 0.0  # the committed empty ledger
    ledger.write_text(_line(actual=0.1) + "\n" + _line(actual=0.25))
    assert budget.spent(ledger_path=ledger) == pytest.approx(0.35)


def test_committed_ledger_exists_and_parses():
    from pathlib import Path

    p = Path(budget.__file__).resolve().parents[2] / "budget" / "ledger.jsonl"
    assert p.exists()
    budget.spent(ledger_path=p)


# ---- record --------------------------------------------------------------------------------


def test_record_sums_model_usage(tmp_path, monkeypatch, env, ledger):
    log_a = _run(tmp_path / "a", monkeypatch, SCRIPT)
    log_b = _run(tmp_path / "b", monkeypatch, SCRIPT[:3])
    want = 0.0
    for log in (log_a, log_b):
        u = log.stats.model_usage["mockllm/model"]
        assert u.total_cost and u.total_cost > 0
        # test prices are $1 per 1M tokens for every field
        assert u.total_cost == pytest.approx(u.total_tokens / 1e6)
        want += u.total_cost
    entry = budget.record(
        "smoke",
        ["mockllm/model"],
        2,
        0.5,
        [log_a.location, log_b.location],
        balance_before=8.0,
        env_path=env,
        ledger_path=ledger,
        transport=credits(10.0, 2.0),
    )
    assert entry["actual"] == pytest.approx(want)
    assert entry["cost_from_logs"] == pytest.approx(want)
    assert entry["balance_before"] == 8.0 and entry["balance_after"] == pytest.approx(8.0)
    lines = ledger.read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0]) == entry
    assert budget.spent(ledger_path=ledger) == pytest.approx(want)


def test_record_appends_never_rewrites(env, ledger):
    ledger.write_text(_line(actual=0.1))
    before = ledger.read_bytes()
    budget.record(
        "gfree",
        ["m"],
        0,
        0.0,
        [],
        balance_before=8.0,
        env_path=env,
        ledger_path=ledger,
        transport=credits(10.0, 2.0),
    )
    after = ledger.read_bytes()
    assert after.startswith(before) and len(after.splitlines()) == 2


def test_record_uses_balance_drop_when_larger(env, ledger):
    entry = budget.record(
        "smoke",
        ["m"],
        1,
        0.5,
        [],
        balance_before=8.0,
        env_path=env,
        ledger_path=ledger,
        transport=credits(10.0, 2.3),
    )
    assert entry["actual"] == pytest.approx(0.3)
    assert entry["actual_source"] == "balance"


def test_record_unreadable_log_counts_the_step_cap(tmp_path, env, ledger):
    bad = tmp_path / "broken.eval"
    bad.write_bytes(b"not a zip")
    entry = budget.record(
        "smoke",
        ["m"],
        1,
        0.5,
        [bad],
        balance_before=8.0,
        env_path=env,
        ledger_path=ledger,
        transport=credits(10.0, 2.0),
    )
    assert entry["actual"] == STEP_CAPS["smoke"]
    assert entry["actual_source"] == "cap"


def test_record_still_writes_when_balance_after_fails(env, ledger):
    def boom(request):
        raise httpx.ConnectError(f"Authorization: Bearer {FAKE_KEY}", request=request)

    entry = budget.record(
        "smoke",
        ["m"],
        1,
        0.5,
        [],
        balance_before=8.0,
        env_path=env,
        ledger_path=ledger,
        transport=httpx.MockTransport(boom),
    )
    assert entry["balance_after"] is None and entry["balance_error"]
    assert FAKE_KEY not in ledger.read_text()


# ---- redaction -----------------------------------------------------------------------------


def test_key_never_in_ledger_or_stdout(tmp_path, monkeypatch, capsys, env, ledger):
    # success path through the runner (mockllm, mocked balance)
    model = get_model("mockllm/model", custom_outputs=_mock_window())
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))
    run.main(
        ["--step", "smoke", "--estimate", "0.5"],
        model=model,
        log_root=tmp_path / "logs",
        env_path=env,
        ledger_path=ledger,
        transport=credits(),
        display="none",
    )

    # error path: the transport error and the response body both echo the auth header
    def echo(request):
        raise httpx.ConnectError(f"failed: {request.headers['authorization']}", request=request)

    def echo_body(request):
        return httpx.Response(401, text=f"bad key {request.headers['authorization']}")

    for t in (httpx.MockTransport(echo), httpx.MockTransport(echo_body)):
        with pytest.raises(BudgetError) as ei:
            budget.check("smoke", 0.1, env_path=env, ledger_path=ledger, transport=t)
        tb = "".join(traceback.format_exception(ei.value))
        assert FAKE_KEY not in tb and "xpl_" not in tb
        code = run.main(
            ["--step", "smoke", "--estimate", "0.1"],
            env_path=env,
            ledger_path=ledger,
            transport=t,
        )
        assert code != 0
    code = budget.main(
        ["check", "--step", "smoke", "--estimate", "0.1"],
        env_path=env,
        ledger_path=ledger,
        transport=httpx.MockTransport(echo),
    )
    assert code != 0
    out = capsys.readouterr()
    assert "REFUSED" in out.err
    for text in (out.out, out.err, ledger.read_text()):
        assert "xpl_" not in text
    assert len(ledger.read_text().splitlines()) == 1


def test_redact_hides_key_and_bearer():
    s = budget.redact(f"x Bearer {FAKE_KEY} y {FAKE_KEY}", [FAKE_KEY])
    assert FAKE_KEY not in s and "xpl_" not in s
    shaped = "".join(["xp", "l_", "A1" * 12])  # key-shaped, built at runtime (no constant)
    assert "xpl_" not in budget.redact(f"echo {shaped} end")  # caught by shape alone
    assert "Bearer abc.def" not in budget.redact("Authorization: Bearer abc.def")


# ---- budget CLI ----------------------------------------------------------------------------


def test_budget_cli_check_exit_codes(env, ledger, capsys):
    ok = ["check", "--step", "smoke", "--estimate", "0.1"]
    kw = dict(env_path=env, ledger_path=ledger, transport=credits())
    assert budget.main(ok, **kw) == 0
    assert budget.main(["check", "--step", "smoke", "--estimate", "1.5"], **kw) != 0
    assert "REFUSED" in capsys.readouterr().err


# ---- runner --------------------------------------------------------------------------------


PROBE_WORDS = "REAL or EVAL"


def _mock_window(fail_at: int | None = None):
    """A window-run mock: wait every day; answer the probe. Raises once at call `fail_at`."""
    state = {"n": 0, "raised": False}

    def fn(input, tools, tool_choice, config):
        state["n"] += 1
        if fail_at is not None and state["n"] == fail_at and not state["raised"]:
            state["raised"] = True
            raise RuntimeError("transient upstream failure")
        if PROBE_WORDS in str(input[-1].content):
            return ModelOutput.from_content("mockllm/model", "REAL.")
        return tc("wait_for_next_day")

    return fn


def test_runner_reruns_failed_once_and_keeps_failure(tmp_path, monkeypatch, env, ledger):
    from inspect_ai.log import read_eval_log

    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))
    model = get_model("mockllm/model", custom_outputs=_mock_window(fail_at=3))
    entry = run.run_step(
        "smoke",
        0.5,
        model=model,
        log_root=tmp_path / "logs",
        env_path=env,
        ledger_path=ledger,
        transport=credits(),
        display="none",
    )
    [path] = entry["eval_paths"]
    log = read_eval_log(path)
    assert log.status == "success"
    [sample] = log.samples
    assert sample.metadata["seed"] == 1001 and sample.metadata["dose"] == 3_000_000
    # two attempts: the first is kept as a failed attempt, the rerun finished
    assert len(sample.error_retries or []) == 1
    assert "transient upstream failure" in sample.error_retries[0].message
    assert sample.error is None
    assert next(iter(sample.scores.values())).metadata["t1_label"] is not None
    # the rerun's cost (and the failed attempt's) is in the ledger line
    assert entry["actual"] == pytest.approx(log.stats.model_usage["mockllm/model"].total_cost)
    assert entry["retried_samples"] == 1 and entry["failed_samples"] == 0
    assert log.eval.config.retry_on_error == 1
    assert log.eval.config.cost_limit == 0.50  # smoke: $1 cap / (1 run x 2 attempts)


def test_runner_refuses_unbuilt_steps_without_network(tmp_path, env, ledger):
    for step in ("pregen", "mini_batch", "full_run"):  # route_check: built in Task 30
        with pytest.raises(run.RunnerError, match="not built"):
            run.run_step(
                step,
                0.01,
                log_root=tmp_path / "logs",
                env_path=env,
                ledger_path=ledger,
                transport=never_called(),
            )
    assert ledger.read_text() == ""
    assert not (tmp_path / "logs").exists()


def test_dispatch_table_covers_every_step():
    assert set(run.STEPS) == set(STEP_CAPS)
    assert {s for s, v in run.STEPS.items() if v.built} == {"gfree", "route_check", "smoke"}


def test_runner_unknown_step_rejected_by_cli(env, ledger):
    with pytest.raises(SystemExit) as ei:
        run.main(["--step", "bogus", "--estimate", "0"], env_path=env, ledger_path=ledger)
    assert ei.value.code != 0


def test_runner_refusal_launches_nothing(tmp_path, monkeypatch, env, ledger):
    def no_eval(*a, **k):  # pragma: no cover
        raise AssertionError("eval must not run")

    monkeypatch.setattr(run, "inspect_eval", no_eval)
    with pytest.raises(BudgetError, match="cap"):
        run.run_step(
            "smoke", 1.5, log_root=tmp_path, env_path=env, ledger_path=ledger, transport=credits()
        )
    assert ledger.read_text() == ""


def test_dry_run_checks_and_prints_plan_without_eval(tmp_path, monkeypatch, capsys, env, ledger):
    def no_eval(*a, **k):  # pragma: no cover
        raise AssertionError("eval must not run")

    monkeypatch.setattr(run, "inspect_eval", no_eval)
    seen: list[httpx.Request] = []
    code = run.main(
        ["--step", "gfree", "--estimate", "0", "--token-limit", "500000", "--dry-run"],
        log_root=tmp_path / "logs",
        env_path=env,
        ledger_path=ledger,
        transport=credits(seen=seen),
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "openai-api/xpl/gpt-6-luna" in out and "gfree" in out
    assert "500000" in out and "1001" in out and "3000000" in out
    assert len(seen) == 1  # the balance fetch is the only call
    assert ledger.read_text() == ""
    # a dry run still refuses over the cap
    assert (
        run.main(
            ["--step", "gfree", "--estimate", "0.01", "--dry-run"],
            env_path=env,
            ledger_path=ledger,
            transport=credits(),
        )
        != 0
    )


def test_sample_cost_limit_defaults(ledger):
    assert run.default_sample_cost_limit("smoke", ledger) == 0.50  # fits the $1 cap with a rerun
    assert run.default_sample_cost_limit("gfree", ledger) == 1.00  # free tier: tokens bound it
    with pytest.raises(run.RunnerError, match="smoke"):
        run.default_sample_cost_limit("mini_batch", ledger)
    ledger.write_text(_line(step="smoke", actual=0.2, runs=1))
    assert run.default_sample_cost_limit("mini_batch", ledger) == pytest.approx(0.4)
    assert run.default_sample_cost_limit("full_run", ledger) == pytest.approx(0.4)


# ---- retry cache scope ---------------------------------------------------------------------


def test_retry_scope_suffix():
    cell = {"people": "template", "variant": "window"}
    base = cell_scope("m", 1001, 3_000_000, **cell)
    assert base == "m|1001|3000000|template|window"
    assert cell_scope("m", 1001, 3_000_000, **cell, retry=0) == base
    assert cell_scope("m", 1001, 3_000_000, **cell, retry=2) == base + "|retry2"
    h = {"reasoning_effort": "low", "max_retries": 5, "cache_expiry": "1W"}
    assert generate_config("m", 1001, 3_000_000, h, **cell).cache.scopes["cell"] == base
    assert generate_config("m", 1001, 3_000_000, h, **cell, retry=1).cache.scopes["cell"] == (
        base + "|retry1"
    )
    with pytest.raises(ValueError):
        cell_scope("m", 1001, 0, **cell, retry=-1)


def test_balance_error_keeps_no_original_exception(env, ledger):
    def echo(request):
        raise httpx.ConnectError(f"failed: {request.headers['authorization']}", request=request)

    with pytest.raises(BudgetError) as ei:
        budget.fetch_balance(env_path=env, transport=httpx.MockTransport(echo))
    assert ei.value.__context__ is None and ei.value.__cause__ is None


def test_record_incomplete_log_counts_the_step_cap(tmp_path, monkeypatch, env, ledger):
    from types import SimpleNamespace

    import inspect_ai.log

    fake = SimpleNamespace(status="started", stats=SimpleNamespace(model_usage={}), samples=[])
    monkeypatch.setattr(inspect_ai.log, "read_eval_log", lambda p: fake)
    entry = budget.record(
        "smoke",
        ["m"],
        1,
        0.5,
        [tmp_path / "x.eval"],
        balance_before=8.0,
        env_path=env,
        ledger_path=ledger,
        transport=credits(10.0, 2.0),
    )
    assert entry["actual"] == STEP_CAPS["smoke"] and entry["actual_source"] == "cap"


@pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, math.inf])
def test_runner_refuses_bad_sample_cost_limit(tmp_path, env, ledger, bad):
    with pytest.raises(run.RunnerError, match="cost limit"):
        run.run_step(
            "smoke",
            0.1,
            sample_cost_limit=bad,
            log_root=tmp_path,
            env_path=env,
            ledger_path=ledger,
            transport=never_called(),
        )


# ---- R25-2: worst-case run-time exposure ---------------------------------------------------


def _no_eval(monkeypatch):
    def no_eval(*a, **k):  # pragma: no cover
        raise AssertionError("eval must not run")

    monkeypatch.setattr(run, "inspect_eval", no_eval)


def test_exposure_is_runs_times_limit_times_attempts():
    plan = run.STEPS["smoke"].plan
    assert run.RETRY_ON_ERROR == 1
    assert run.exposure(plan, 0.4) == pytest.approx(1 * 0.4 * 2)
    assert run.exposure(plan, None) is None  # no cost limit: unknown, never $0


def test_exposure_refuses_over_step_cap(tmp_path, monkeypatch, env, ledger):
    _no_eval(monkeypatch)
    with pytest.raises(BudgetError, match="exposure .* over the smoke cap"):
        run.run_step(
            "smoke",
            0.1,
            sample_cost_limit=0.6,  # 1 run x $0.60 x 2 attempts = $1.20 > $1.00
            log_root=tmp_path,
            env_path=env,
            ledger_path=ledger,
            transport=never_called(),
        )
    assert ledger.read_text() == ""


def test_exposure_refuses_over_stop_line(tmp_path, monkeypatch, capsys, env, ledger):
    _no_eval(monkeypatch)
    ledger.write_text(_line(actual=8.80))
    with pytest.raises(BudgetError, match="stop line"):
        run.run_step(
            "smoke",
            0.1,
            sample_cost_limit=0.4,  # 8.80 + 1 x 0.40 x 2 = 9.60 > 9.50
            log_root=tmp_path,
            env_path=env,
            ledger_path=ledger,
            transport=never_called(),
        )
    # 8.80 + 0.30 x 2 = 9.40 passes (dry run)
    run.run_step(
        "smoke",
        0.1,
        sample_cost_limit=0.3,
        dry_run=True,
        log_root=tmp_path,
        env_path=env,
        ledger_path=ledger,
        transport=credits(),
    )
    assert "exposure:          $0.6000" in capsys.readouterr().out
    assert len(ledger.read_text().splitlines()) == 1


def test_exposure_unknown_refuses_a_paid_step():
    plan = run.STEPS["smoke"].plan
    with pytest.raises(BudgetError, match="unknown"):
        run.check_exposure("smoke", plan, None, None, 0.0)


def test_default_smoke_sample_cost_limit_fits_the_cap(ledger):
    limit = run.default_sample_cost_limit("smoke", ledger)
    assert limit == pytest.approx(0.50)  # min($1, $1.00 cap / (1 run x 2 attempts))
    assert run.exposure(run.STEPS["smoke"].plan, limit) <= STEP_CAPS["smoke"]


def test_dry_run_prints_the_exposure(tmp_path, monkeypatch, capsys, env, ledger):
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
    assert "exposure:          $1.0000 (1 runs x $0.5000 x 2 attempts)" in out


def test_gfree_exposure_is_counted_in_free_tier_tokens(tmp_path, monkeypatch, capsys, env, ledger):
    """G-free has a $0 cap: its worst case is measured in free-tier tokens. It runs with no
    automatic rerun (round 1b ruling), so 1 run x 800k x 1 attempt fits the 1M tokens/day
    free tier and spec §6's 800k passes; 1.2M is refused."""
    _no_eval(monkeypatch)
    kw = dict(log_root=tmp_path, env_path=env, ledger_path=ledger)
    run.run_step("gfree", 0.0, token_limit=800_000, dry_run=True, transport=credits(), **kw)
    out = capsys.readouterr().out
    assert "800000 of 1000000 free-tier tokens: 1 runs x 800000 tokens x 1 attempts" in out
    with pytest.raises(BudgetError, match="free tier"):
        run.run_step("gfree", 0.0, token_limit=1_200_000, transport=never_called(), **kw)
    assert ledger.read_text() == ""


def test_gfree_cli_token_limit_800k_passes_and_1200k_refused(
    tmp_path, monkeypatch, capsys, env, ledger
):
    _no_eval(monkeypatch)
    kw = dict(log_root=tmp_path, env_path=env, ledger_path=ledger, transport=credits())
    base = ["--step", "gfree", "--estimate", "0", "--dry-run", "--token-limit"]
    assert run.main([*base, "800000"], **kw) == 0
    assert run.main([*base, "1200000"], **kw) != 0
    assert "free tier" in capsys.readouterr().err


def test_gfree_default_token_limit_is_spec_800k(tmp_path, monkeypatch, capsys, env, ledger):
    _no_eval(monkeypatch)
    ledger.write_text(_line(actual=0.3, runs=1, total_tokens=300_000))  # a smoke never sets it
    run.run_step(
        "gfree",
        0.0,
        dry_run=True,
        log_root=tmp_path,
        env_path=env,
        ledger_path=ledger,
        transport=credits(),
    )
    assert "token_limit:       800000 (step default)" in capsys.readouterr().out


def test_gfree_launches_without_retry_and_smoke_with_one(tmp_path, monkeypatch):
    seen: dict[str, int] = {}

    def fake_eval(*a, **k):
        seen[k["log_dir"]] = k["retry_on_error"]
        return []

    monkeypatch.setattr(run, "inspect_eval", fake_eval)
    monkeypatch.setattr("temptation_bench.harness.task.temptation_bench", lambda **k: None)
    for step in ("gfree", "smoke"):
        plan = run.STEPS[step].plan
        run.launch_task_eval(run.Ctx(step, plan, tmp_path / step, 0.5, 800_000))
    assert seen == {str(tmp_path / "gfree"): 0, str(tmp_path / "smoke"): 1}
    assert run.STEPS["gfree"].plan.attempts == 1 and run.STEPS["smoke"].plan.attempts == 2


# ---- R25-5: default token limit from the smoke ---------------------------------------------


def test_default_token_limit_from_smoke(ledger):
    assert run.default_token_limit(ledger) is None  # before any smoke: none
    ledger.write_text(_line(actual=0.3, runs=1))  # an old line without token totals
    assert run.default_token_limit(ledger) is None
    ledger.write_text(
        _line(actual=0.3, runs=1, total_tokens=300_000)
        + _line(step="gfree", actual=0.0, runs=1, total_tokens=10)
        + _line(actual=0.6, runs=2, total_tokens=1_000_000)
    )
    assert run.default_token_limit(ledger) == 1_000_000  # 2 x (1,000,000 / 2), latest smoke


def test_runner_defaults_the_token_limit_after_a_smoke(tmp_path, monkeypatch, capsys, env, ledger):
    _no_eval(monkeypatch)
    ledger.write_text(_line(actual=0.3, runs=1, total_tokens=300_000))
    kw = dict(log_root=tmp_path, env_path=env, ledger_path=ledger, transport=credits())
    run.run_step("smoke", 0.3, dry_run=True, **kw)
    assert "token_limit:       600000 (2 x smoke mean)" in capsys.readouterr().out
    run.run_step("smoke", 0.3, token_limit=123_456, dry_run=True, **kw)  # the flag wins
    assert "token_limit:       123456 (--token-limit)" in capsys.readouterr().out


def test_record_keeps_token_totals_for_the_default(tmp_path, monkeypatch, env, ledger):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))
    model = get_model("mockllm/model", custom_outputs=_mock_window())
    entry = run.run_step(
        "smoke",
        0.5,
        model=model,
        log_root=tmp_path / "logs",
        env_path=env,
        ledger_path=ledger,
        transport=credits(),
        display="none",
    )
    assert entry["total_tokens"] > 0
    assert run.default_token_limit(ledger) == 2 * entry["total_tokens"]


# ---- X-1: one model per eval ---------------------------------------------------------------


TWO = run.Plan((run.HAIKU, run.LUNA), "window", "1001", "3000000")


def test_launch_refuses_more_than_one_model(tmp_path, monkeypatch):
    _no_eval(monkeypatch)
    ctx = run.Ctx("smoke", TWO, tmp_path, 0.5, None)
    with pytest.raises(run.RunnerError, match="one model per eval"):
        run.launch_task_eval(ctx)


def test_runner_refuses_a_two_model_step_before_any_call(tmp_path, monkeypatch, env, ledger):
    _no_eval(monkeypatch)
    monkeypatch.setitem(run.STEPS, "smoke", run.Step(TWO, run.launch_task_eval))
    with pytest.raises(run.RunnerError, match="one model per eval"):
        run.run_step(
            "smoke",
            0.1,
            sample_cost_limit=0.1,
            log_root=tmp_path,
            env_path=env,
            ledger_path=ledger,
            transport=never_called(),
        )
    assert ledger.read_text() == ""


# ---- Task 29 pre-work: --list-models (free metadata call) -----------------------------------


def _models_body(request: httpx.Request) -> dict:
    auth = request.headers["authorization"]
    return {
        "object": "list",
        "data": [
            {"id": "openai/gpt-6-luna", "owned_by": "x", "echo": auth},
            {"id": "anthropic/claude-haiku-5-5", "owned_by": "y"},
            {"id": "qwen/qwen3.7-flash"},
        ],
        "request_headers": {"authorization": auth},
    }


def test_list_models_prints_only_the_sorted_ids(env, ledger, capsys):
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_models_body(request), headers={"x-echo": "h"})

    code = run.main(
        ["--step", "route_check", "--list-models"],
        env_path=env,
        ledger_path=ledger,
        transport=httpx.MockTransport(handler),
    )
    out = capsys.readouterr()
    assert code == 0
    assert out.out == "anthropic/claude-haiku-5-5\nopenai/gpt-6-luna\nqwen/qwen3.7-flash\n"
    assert out.err == ""
    assert len(seen) == 1 and seen[0].method == "GET"
    assert str(seen[0].url) == f"{BASE}/v1/models"
    assert seen[0].headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert ledger.read_text() == ""  # free metadata call: no ledger line, no spend


def _echo_cases():
    def ok_with_key_in_id(request):
        auth = request.headers["authorization"]
        return httpx.Response(200, json={"data": [{"id": f"m {auth}"}, {"id": FAKE_KEY}]})

    def unauthorized(request):
        return httpx.Response(401, text=f"bad key {request.headers['authorization']}")

    def connect(request):
        raise httpx.ConnectError(f"failed: {request.headers['authorization']}", request=request)

    def not_json(request):
        return httpx.Response(200, text=f"<html>{request.headers['authorization']}</html>")

    def no_ids(request):
        return httpx.Response(200, json={"data": [], "echo": request.headers["authorization"]})

    def bad_id(request):
        auth = request.headers["authorization"]
        return httpx.Response(200, json={"data": [{"id": 5}], "e": auth})

    return {
        "ok_with_key_in_id": (ok_with_key_in_id, 0),
        "unauthorized": (unauthorized, 1),
        "connect": (connect, 1),
        "not_json": (not_json, 1),
        "no_ids": (no_ids, 1),
        "bad_id": (bad_id, 1),
    }


@pytest.mark.parametrize("case", sorted(_echo_cases()))
def test_list_models_never_prints_an_echoed_auth_header(case, env, ledger, capsys):
    handler, want = _echo_cases()[case]
    code = run.main(
        ["--step", "route_check", "--list-models"],
        env_path=env,
        ledger_path=ledger,
        transport=httpx.MockTransport(handler),
    )
    out = capsys.readouterr()
    assert code == want
    for text in (out.out, out.err):
        assert FAKE_KEY not in text and "xpl_" not in text and "Bearer" not in text
    if want:
        assert out.out == "" and out.err.startswith("REFUSED: list models failed")
    assert ledger.read_text() == ""


def test_list_models_error_keeps_no_original_exception(env):
    def echo(request):
        raise httpx.ConnectError(f"failed: {request.headers['authorization']}", request=request)

    with pytest.raises(BudgetError) as ei:
        budget.list_models(env_path=env, transport=httpx.MockTransport(echo))
    assert ei.value.__context__ is None and ei.value.__cause__ is None
    assert FAKE_KEY not in "".join(traceback.format_exception(ei.value))


def test_list_models_only_on_route_check(env, ledger, capsys):
    code = run.main(
        ["--step", "smoke", "--list-models"],
        env_path=env,
        ledger_path=ledger,
        transport=never_called(),
    )
    assert code != 0 and "route_check" in capsys.readouterr().err


def test_estimate_still_required_without_list_models(env, ledger):
    with pytest.raises(SystemExit) as ei:
        run.main(["--step", "smoke"], env_path=env, ledger_path=ledger, transport=never_called())
    assert ei.value.code != 0


def test_list_models_fails_closed_without_env(tmp_path, ledger, capsys):
    code = run.main(
        ["--step", "route_check", "--list-models"],
        env_path=tmp_path / "nope.env",
        ledger_path=ledger,
        transport=never_called(),
    )
    assert code != 0 and "REFUSED" in capsys.readouterr().err


# ---- Task 29 pre-work: G-free dollar check against the stop line ----------------------------


def test_gfree_refuses_when_spent_plus_dollar_exposure_is_over_the_stop_line(
    tmp_path, monkeypatch, env, ledger
):
    """The free tier may not apply (the gateway could bill Luna): G-free still passes a $1
    per-sample cost limit, so spent + runs x limit x 1 attempt must fit the stop line."""
    _no_eval(monkeypatch)
    ledger.write_text(_line(actual=8.60))  # 8.60 + 1 x $1.00 x 1 = 9.60 > 9.50
    with pytest.raises(BudgetError, match="stop line"):
        run.run_step(
            "gfree",
            0.0,
            token_limit=800_000,
            log_root=tmp_path,
            env_path=env,
            ledger_path=ledger,
            transport=never_called(),
        )
    assert len(ledger.read_text().splitlines()) == 1


def test_gfree_dollar_check_uses_one_attempt():
    plan = run.STEPS["gfree"].plan
    assert plan.attempts == 1
    line = run.check_exposure("gfree", plan, 1.0, 800_000, 8.40)  # 8.40 + 1.00 = 9.40 ok
    assert "free tier" in line and "$1.0000 if billed" in line
    with pytest.raises(BudgetError, match="stop line"):
        run.check_exposure("gfree", plan, 1.0, 800_000, 8.51)
    with pytest.raises(BudgetError, match="unknown"):
        run.check_exposure("gfree", plan, None, 800_000, 0.0)


# ---- Task 29 pre-work: an eval that fails at start is not charged the cap -------------------


def test_record_eval_failed_before_log_charges_actual_usage_not_the_cap(env, ledger):
    """Inspect writes the `.eval` (`log_start`) before any sample runs, so no log means no
    model call: `actual` is the summed usage (0), raised only by a real balance drop."""
    err = "PrerequisiteError: cost_limit requires cost data for all models."
    entry = budget.record(
        "smoke",
        ["m"],
        1,
        0.5,
        [],
        balance_before=8.0,
        error=err,
        env_path=env,
        ledger_path=ledger,
        transport=credits(10.0, 2.0),  # balance 8.0: unchanged
    )
    assert entry["actual"] == 0.0 and entry["actual_source"] == "logs"
    assert entry["error"] == err
    dropped = budget.record(
        "smoke",
        ["m"],
        1,
        0.5,
        [],
        balance_before=8.0,
        error=err,
        env_path=env,
        ledger_path=ledger,
        transport=credits(10.0, 2.25),  # balance 7.75: a real drop still counts
    )
    assert dropped["actual"] == pytest.approx(0.25) and dropped["actual_source"] == "balance"


def test_runner_prerequisite_error_at_start_records_zero(tmp_path, monkeypatch, env, ledger):
    from inspect_ai._util.error import PrerequisiteError

    def fail_at_start(*a, **k):
        raise PrerequisiteError("cost_limit requires cost data for all models.")

    monkeypatch.setattr(run, "inspect_eval", fail_at_start)
    with pytest.raises(PrerequisiteError):
        run.run_step(
            "smoke",
            0.1,
            log_root=tmp_path,
            env_path=env,
            ledger_path=ledger,
            transport=credits(),
        )
    entry = json.loads(ledger.read_text().splitlines()[-1])
    assert entry["actual"] == 0.0 and "PrerequisiteError" in entry["error"]
