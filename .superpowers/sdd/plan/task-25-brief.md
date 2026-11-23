### Task 25: Budget guard and paid runner

**Files:**
- Create: `src/temptation_bench/budget.py`, `src/temptation_bench/run.py`, `pilot-1/budget/ledger.jsonl` (empty)
- Test: `tests/test_budget.py`

**Interfaces:**
- `budget.py`:
  - `STOP_LINE = 9.50`; `STEP_CAPS = {"gfree": 0.00, "route_check": 0.05, "smoke": 1.00, "pregen": 0.05, "mini_batch": 5.00, "full_run": 1.50}`
  - `fetch_balance() -> float`: `GET {XPL_BASE_URL minus /v1}/api/v1/credits` with the bearer key from the `.env` values loaded via `dotenv_values` (never `os.environ` export). Returns `total_credits − total_usage`. Raises `BudgetError` on any HTTP or parse error (fail closed).
  - `spent() -> float`: the sum of the ledger's `actual`.
  - `check(step: str, estimate: float) -> None`: raises `BudgetError` if `estimate > STEP_CAPS[step]`, or `spent() + estimate > STOP_LINE`, or balance unreadable.
  - `record(step, models, runs, estimate, eval_paths) -> dict`: actual cost = Σ `ModelUsage.total_cost` from the logs. Appends a ledger line with the balance before and after.
- `run.py` CLI: `python -m temptation_bench.run --step {gfree,route_check,smoke,pregen,mini_batch,full_run} --estimate X [--token-limit N] [--dry-run]`. It calls `check`, then the right `inspect_ai.eval(...)` (or the route-check script), then `record`. It sets `cost_limit` per sample from `--sample-cost-limit` (default: 2× the measured smoke cost read from the ledger; smoke itself \$1). A sample that ends in error is rerun once with the same seed and dose (`retry_on_error=1`); the failed sample stays in the log and counts in the report (DD §13A). The rerun's estimate is inside the same step cap.
- [ ] **Step 1: Failing tests** (HTTP mocked with `httpx.MockTransport`):
  - `test_check_refuses_over_stop_line`
  - `test_check_refuses_over_step_cap`
  - `test_check_fails_closed_on_http_error`
  - `test_record_sums_model_usage` (from a mockllm `.eval` with test prices)
  - `test_key_never_in_ledger_or_stdout` (capsys + ledger grep for `xpl_`)
  - `test_runner_reruns_failed_once_and_keeps_failure` (mockllm sample that raises once: two attempts in the log, the first marked failed)
- [ ] **Step 2:** Run and confirm they fail. Implement. Run and confirm they pass. Commit.

