"""Spend guard (spec §7.2, §7.3). It fails closed: when in doubt, it refuses.

- `check(step, estimate)` refuses (raises `BudgetError`) if the step is unknown, the estimate
  is over the step cap, `spent() + estimate` is over the \\$9.50 stop line, the ledger is
  missing or unparsable, or the gateway balance cannot be read (or is below the estimate).
- `record(...)` appends one line per step run to `budget/ledger.jsonl` (append-only).
- The key is read from `pilot-1/.env` with `dotenv_values` into a local dict. It is never put
  into `os.environ`, never logged, and redacted from every error message.

CLI: `uv run python -m temptation_bench.budget check --step smoke --estimate 0.3`
(exit 0 = allowed, non-zero = refused)."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]  # pilot-1/
ENV_PATH = ROOT / ".env"
LEDGER_PATH = ROOT / "budget" / "ledger.jsonl"

STOP_LINE = 9.50
STEP_CAPS = {
    "gfree": 0.00,
    "route_check": 0.05,
    "smoke": 1.00,
    "pregen": 0.05,
    "mini_batch": 5.00,
    "full_run": 1.50,
}
CREDITS_PATH = "/api/v1/credits"
TIMEOUT_S = 15.0

_KEY_SHAPES = re.compile(r"\b(xpl_|sk-ant-|sk-)[A-Za-z0-9_\-]+|(?i:\bbearer)\s+\S+")


class BudgetError(RuntimeError):
    """The guard refuses. The message never holds a secret."""


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Remove the given secret values and anything key-shaped (bearer tokens, `xpl_…`)."""
    for s in sorted({s for s in secrets if s}, key=len, reverse=True):
        text = text.replace(s, "[redacted]")
    return _KEY_SHAPES.sub("[redacted]", text)


# ---- env + balance -------------------------------------------------------------------------


def _env(env_path: Path | None) -> tuple[str, str]:
    """(key, base_url) from the `.env` file, loaded into a local dict only."""
    path = Path(env_path or ENV_PATH)
    if not path.is_file():
        raise BudgetError(f"no .env file at {path} (the owner creates it from .env.example)")
    values = dotenv_values(path)
    key = (values.get("XPL_API_KEY") or "").strip()
    base = (values.get("XPL_BASE_URL") or "").strip()
    missing = [n for n, v in (("XPL_API_KEY", key), ("XPL_BASE_URL", base)) if not v]
    if missing:
        raise BudgetError(f".env is missing {', '.join(missing)}")
    if not base.lower().startswith("https://"):
        raise BudgetError("XPL_BASE_URL must use https (the key is never sent in clear)")
    return key, base


def credits_url(base_url: str) -> str:
    """`XPL_BASE_URL` minus a trailing `/v1`, plus `/api/v1/credits`."""
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base + CREDITS_PATH


def _number(d: Any, name: str) -> float:
    v = d.get(name) if isinstance(d, dict) else None
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        raise BudgetError(f"balance response has no numeric {name}")
    return float(v)


def fetch_balance(
    *, env_path: Path | None = None, transport: httpx.BaseTransport | None = None
) -> float:
    """Gateway balance = `total_credits - total_usage` (fields at the top level or under
    `data`). Any HTTP error, non-200, unparsable body or negative balance raises."""
    key, base = _env(env_path)
    failure: str | None = None
    r: httpx.Response | None = None
    try:
        with httpx.Client(transport=transport, timeout=TIMEOUT_S, follow_redirects=False) as c:
            r = c.get(credits_url(base), headers={"Authorization": f"Bearer {key}"})
    except Exception as e:  # httpx errors and anything else: refuse
        failure = redact(f"balance fetch failed: {type(e).__name__}: {e}", [key])
    # raised outside the except block, so the original error (which may echo the auth
    # header) is not even kept as `__context__`
    if failure is not None or r is None:
        raise BudgetError(failure or "balance fetch failed")
    if r.status_code != 200:  # the body is never shown: it may echo the request
        raise BudgetError(f"balance fetch failed: HTTP {r.status_code}")
    try:
        body = r.json()
    except Exception:
        raise BudgetError("balance response is not JSON") from None
    data = body.get("data", body) if isinstance(body, dict) else None
    bal = _number(data, "total_credits") - _number(data, "total_usage")
    if bal < 0:
        raise BudgetError(f"gateway balance is negative ({bal:.4f})")
    return bal


def models_url(base_url: str) -> str:
    """`XPL_BASE_URL` (ends in `/v1`) plus `/models`: the gateway's `GET /v1/models`."""
    return base_url.rstrip("/") + "/models"


def list_models(
    *, env_path: Path | None = None, transport: httpx.BaseTransport | None = None
) -> list[str]:
    """The gateway's model ids (`GET {XPL_BASE_URL}/models`), sorted. A free metadata call:
    no ledger line. Only the `id` strings are kept (each redacted); headers and the rest of
    the body are never returned or shown. Any HTTP error, non-200, unparsable body, missing
    or non-string id refuses (`BudgetError`, message without the key)."""
    key, base = _env(env_path)
    failure: str | None = None
    r: httpx.Response | None = None
    try:
        with httpx.Client(transport=transport, timeout=TIMEOUT_S, follow_redirects=False) as c:
            r = c.get(models_url(base), headers={"Authorization": f"Bearer {key}"})
    except Exception as e:
        failure = redact(f"list models failed: {type(e).__name__}: {e}", [key])
    if failure is not None or r is None:  # raised outside the except: no echoing __context__
        raise BudgetError(failure or "list models failed")
    if r.status_code != 200:
        raise BudgetError(f"list models failed: HTTP {r.status_code}")
    try:
        body = r.json()
    except Exception:
        raise BudgetError("list models failed: response is not JSON") from None
    items = body.get("data") if isinstance(body, dict) else body
    if not isinstance(items, list) or not items:
        raise BudgetError("list models failed: no model list in the response")
    ids = [m.get("id") if isinstance(m, dict) else None for m in items]
    if not all(isinstance(i, str) and i for i in ids):
        raise BudgetError("list models failed: an entry has no string id")
    return sorted({redact(i, [key]) for i in ids if isinstance(i, str)})


# ---- ledger --------------------------------------------------------------------------------


def _ledger_entries(ledger_path: Path | None) -> list[dict[str, Any]]:
    path = Path(ledger_path or LEDGER_PATH)
    if not path.is_file():
        raise BudgetError(f"ledger missing at {path} (never read as $0 spent)")
    out = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            raise BudgetError(f"ledger line {n} is not JSON") from None
        a = e.get("actual") if isinstance(e, dict) else None
        if isinstance(a, bool) or not isinstance(a, int | float) or not math.isfinite(a) or a < 0:
            raise BudgetError(f"ledger line {n} has no valid 'actual'")
        out.append(e)
    return out


def spent(*, ledger_path: Path | None = None) -> float:
    """Sum of `actual` over every ledger line."""
    return float(sum(e["actual"] for e in _ledger_entries(ledger_path)))


def ledger_entries(*, ledger_path: Path | None = None) -> list[dict[str, Any]]:
    return _ledger_entries(ledger_path)


# ---- check ---------------------------------------------------------------------------------


def guard(
    step: str,
    estimate: float,
    *,
    env_path: Path | None = None,
    ledger_path: Path | None = None,
    transport: httpx.BaseTransport | None = None,
) -> float:
    """`check`, returning the balance it read. Local checks first, the network last."""
    if step not in STEP_CAPS:
        raise BudgetError(f"unknown step {step!r} (known: {', '.join(STEP_CAPS)})")
    if isinstance(estimate, bool) or not math.isfinite(estimate) or estimate < 0:
        raise BudgetError(f"bad estimate {estimate!r} (need a finite number >= 0)")
    cap = STEP_CAPS[step]
    if estimate > cap:
        raise BudgetError(
            f"estimate ${estimate:.4f} is over the {step} cap ${cap:.2f} (needs owner OK)"
        )
    s = spent(ledger_path=ledger_path)
    if s + estimate > STOP_LINE:
        raise BudgetError(
            f"spent ${s:.4f} + estimate ${estimate:.4f} is over the stop line ${STOP_LINE:.2f}"
        )
    bal = fetch_balance(env_path=env_path, transport=transport)
    if bal < estimate:
        raise BudgetError(f"gateway balance ${bal:.4f} is below the estimate ${estimate:.4f}")
    return bal


def check(
    step: str,
    estimate: float,
    *,
    env_path: Path | None = None,
    ledger_path: Path | None = None,
    transport: httpx.BaseTransport | None = None,
) -> None:
    """Raise `BudgetError` unless the step may run (see module docstring)."""
    guard(step, estimate, env_path=env_path, ledger_path=ledger_path, transport=transport)


# ---- record --------------------------------------------------------------------------------


def _rel(p: Path | str) -> str:
    p = Path(p).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _log_costs(eval_paths: Sequence[Path | str]) -> dict[str, Any]:
    """Σ `ModelUsage.total_cost` over each log's `stats.model_usage`. Inspect's header
    stats include the billed calls of failed attempts that `retry_on_error` reran."""
    from inspect_ai.log import read_eval_log

    by_model: dict[str, float] = {}
    tokens = 0
    unpriced: set[str] = set()
    unreadable: list[str] = []
    statuses: list[str] = []
    retried = failed = 0
    for p in eval_paths:
        try:
            log = read_eval_log(str(p))
        except Exception:
            unreadable.append(_rel(p))
            continue
        statuses.append(str(log.status))
        for name, u in sorted(log.stats.model_usage.items()):
            tokens += u.total_tokens
            if u.total_cost is None:
                if u.total_tokens > 0:
                    unpriced.add(name)
                continue
            by_model[name] = by_model.get(name, 0.0) + float(u.total_cost)
        for s in log.samples or []:
            retried += 1 if s.error_retries else 0
            failed += 1 if s.error is not None else 0
    return {
        "cost_by_model": by_model,
        "cost_from_logs": float(sum(by_model.values())),
        "total_tokens": tokens,
        "unpriced_models": sorted(unpriced),
        "unreadable_logs": unreadable,
        "eval_statuses": statuses,
        "retried_samples": retried,
        "failed_samples": failed,
    }


def record(
    step: str,
    models: Sequence[str],
    runs: int,
    estimate: float,
    eval_paths: Sequence[Path | str],
    *,
    balance_before: float | None = None,
    error: str | None = None,
    env_path: Path | None = None,
    ledger_path: Path | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Append one ledger line for a step run and return it.

    `actual` = Σ total_cost from the logs, raised to the balance drop if that is larger
    (`actual_source: "balance"`), or to the step cap if a log is unreadable or a model has
    tokens but no price, or a log has no final stats (`"cap"`). Over-counting is safe;
    under-counting is not.

    An eval that failed before writing a log (e.g. Inspect's `PrerequisiteError` for missing
    cost data) is NOT charged the cap (Task 29 ruling): Inspect flushes the `.eval` at
    `log_start`, before any sample runs (`_eval/task/run.py` `task_run`), so no log means no
    model call. `actual` is then the summed usage (0, or the balance drop if larger), and the
    redacted `error` is kept on the line."""
    path = Path(ledger_path or LEDGER_PATH)
    if not path.is_file():
        raise BudgetError(f"ledger missing at {path}")
    secrets: list[str] = []
    try:
        secrets = [_env(env_path)[0]]
    except BudgetError:
        pass
    costs = _log_costs(eval_paths)
    balance_after: float | None = None
    balance_error: str | None = None
    try:
        balance_after = fetch_balance(env_path=env_path, transport=transport)
    except BudgetError as e:
        balance_error = str(e)
    actual, source = costs["cost_from_logs"], "logs"
    if balance_before is not None and balance_after is not None:
        drop = balance_before - balance_after
        if drop > actual:
            actual, source = drop, "balance"
    incomplete = any(st not in ("success", "error", "cancelled") for st in costs["eval_statuses"])
    if (
        costs["unreadable_logs"]
        or costs["unpriced_models"]
        or incomplete  # a log without final stats (e.g. killed mid-run)
    ):
        cap = STEP_CAPS.get(step, STOP_LINE)
        if cap > actual:
            actual, source = cap, "cap"
    entry = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "step": step,
        "models": list(models),
        "runs": int(runs),
        "estimate": float(estimate),
        "actual": float(actual),
        "actual_source": source,
        **costs,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "balance_error": balance_error,
        "error": None if error is None else redact(error, secrets),
        "eval_paths": [_rel(p) for p in eval_paths],
    }
    line = redact(json.dumps(entry, sort_keys=True), secrets)
    with path.open("a", encoding="utf-8") as f:  # append-only: earlier lines never change
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())
    return json.loads(line)


# ---- CLI -----------------------------------------------------------------------------------


def main(
    argv: Sequence[str] | None = None,
    *,
    env_path: Path | None = None,
    ledger_path: Path | None = None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    ap = argparse.ArgumentParser(prog="python -m temptation_bench.budget")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="refuse (exit 1) unless the step may run")
    c.add_argument("--step", required=True, choices=sorted(STEP_CAPS))
    c.add_argument("--estimate", required=True, type=float)
    sub.add_parser("spent", help="print the ledger total")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "spent":
            print(f"spent ${spent(ledger_path=ledger_path):.4f} of ${STOP_LINE:.2f}")
            return 0
        bal = guard(
            args.step,
            args.estimate,
            env_path=env_path,
            ledger_path=ledger_path,
            transport=transport,
        )
    except BudgetError as e:
        print(f"REFUSED: {redact(str(e))}", file=sys.stderr)
        return 1
    print(f"OK: {args.step} estimate ${args.estimate:.4f}; balance ${bal:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
