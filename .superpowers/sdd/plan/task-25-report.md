# Task 25 report: budget guard (fail closed) and paid runner CLI

- Status: **DONE_WITH_CONCERNS** (concerns in §11; none blocks Task 29, but two need a controller decision before it).
- Commit: `60bcff6 pilot-1: budget guard (fail-closed) + paid runner CLI` (branch `pilot-1`, not pushed). PROGRESS.md not edited.
- Skills invoked: `superpowers:test-driven-development`, `cost-aware-llm-pipeline`, `benchmark-methodology`, `temptation-bench-architect`.
- Read: the brief; spec in full (§3, §4 D1/D9, §7.1–§7.3, §9); plan lines 13–51 and 861–962 (Tasks 29–34, read only); PROGRESS §5, §6; DD §13A; research `experiment-matrix.md` §3, §5, `inspect-ai.md` §7–§12, `project-structure-patterns.md` §8, `models-and-pricing.md` §6–§7; the Task 24 report.
- **No network call was made.** No paid call, no real balance fetch, `run.py` was never run against the real `.env`. The only `.env` touch was `test -s .env && echo present` (present).

## 1. Inspect API facts verified (0.3.291)

Sources: installed source under `pilot-1/.venv/lib/python3.13/site-packages/inspect_ai/`, Context7 `/websites/inspect_aisi_uk` (handling-errors.html, setting-limits.html, reference/inspect_ai.html), plus a scratch mockllm experiment (scratchpad, not committed).

- `eval(...)` (`_eval/eval.py:159ff`) takes `retry_on_error: int | None`, `token_limit: int | str | TokenLimit | None`, `cost_limit: float | None` (per sample, dollars), `model_cost_config`, `max_samples`, `fail_on_error`, `log_dir`. Context7: `cost_limit` "requires model cost data ... otherwise an error is raised"; `retry_on_error` "retried samples record original errors in the error_retries field".
- `EvalSample.error_retries: list[EvalRetryError] | None` (`log/_log.py:589`); `EvalRetryError` has `message`, `traceback`, `events` (back to the last ModelEvent).
- `ModelUsage.total_cost: float | None` (`model/_model_output.py:43`); `__add__` sums it.
- `read_eval_log(path)` returns `EvalLog`; `log.stats.model_usage: dict[str, ModelUsage]` (`log/_log.py:1329`).
- **Experiment (mockllm, callable `custom_outputs` that raises once, `retry_on_error=1`):**
  - The sample ends `error=None` with `len(error_retries) == 1` holding the error message. That is "two attempts, the first marked failed".
  - The rerun **keeps the cell cache**: its first turns were `cache == "read"` (free), matching the controller ruling, with no code needed.
  - **`log.stats.model_usage` includes the failed attempt's billed calls** (stats cost 0.01293 vs the final sample's `model_usage` 0.00550). So the ledger sums the **header stats**, never per-sample usage (that would under-count retries).
  - mockllm usage gets `total_cost` from the registered test prices (\$1/1M every field): `total_cost == total_tokens / 1e6` (asserted in `test_record_sums_model_usage`).
- Inspect's own `init_dotenv()` (`_util/dotenv.py`) runs `find_dotenv(usecwd=True)` + `load_dotenv` inside the eval process. That is how the real run gets its key (spec §3: "Inspect does this itself"). `run.py` never loads `.env` into `os.environ` itself.

## 2. Guard paths and their tests (`budget.py`)

`check(step, estimate)` (via `guard`, which also returns the balance) checks local things first and the network last:

| Path | Refuses with `BudgetError` | Test |
|---|---|---|
| step not in `STEP_CAPS` | `unknown step` | `test_check_refuses_unknown_step` (no network) |
| estimate < 0, NaN, inf | `bad estimate` | `test_check_refuses_bad_estimate[-0.01,nan,inf]` |
| estimate > cap (gfree 0.01, route_check 0.06) | `over the ... cap` | `test_check_refuses_over_step_cap` (also shows `== cap` passes) |
| spent + estimate > 9.50 | `stop line` | `test_check_refuses_over_stop_line` (9.30 + 0.30 refuses, + 0.20 passes) |
| ledger missing | `ledger missing` (never \$0) | `test_check_fails_closed_on_missing_ledger` |
| ledger line not JSON / no `actual` / string / negative / not an object | `ledger line N` | `test_spent_fails_closed_on_bad_ledger` (5 cases) |
| `.env` missing | `no .env file` | `test_check_fails_closed_on_missing_env` |
| `XPL_API_KEY` or `XPL_BASE_URL` missing/empty | `.env is missing XPL_...` | `test_check_fails_closed_on_missing_keys` (3 cases) |
| base URL not https | `must use https` | `test_check_refuses_plain_http_base_url` |
| transport error | `balance fetch failed` | `test_check_fails_closed_on_http_error` |
| non-200 (401/403/404/500/302; no redirects followed) | `HTTP <code>` | `test_check_fails_closed_on_non_200` |
| body not JSON, `[]`, missing fields, string, bool, NaN | `balance` | `test_check_fails_closed_on_bad_body` (6 cases) |
| balance < 0 | `negative` | `test_check_fails_closed_on_negative_balance` |
| balance < estimate | `below the estimate` | `test_check_refuses_when_balance_below_estimate` |

- `fetch_balance()`: `GET {XPL_BASE_URL minus trailing /v1}/api/v1/credits`, `Authorization: Bearer <key>`; balance = `total_credits − total_usage`, read at the top level or under `data` (the gateway's body shape is not documented in the spec; G-free confirms it). `test_fetch_balance_calls_credits_with_bearer` checks the URL, method, header, and that the fake key never enters `os.environ`.
- An autouse fixture in the test file points `budget.ENV_PATH` / `LEDGER_PATH` at missing tmp files, so a test that forgot an argument would fail closed, never reach the real `.env`.
- CLI (spec §7.3): `python -m temptation_bench.budget check --step S --estimate X` exits 1 with `REFUSED: ...` on stderr; `spent` prints the total. `test_budget_cli_check_exit_codes`.

## 3. Ledger line schema (`budget/ledger.jsonl`, append-only)

One JSON object per step run, sorted keys, written with `open("a")` + flush + fsync. Earlier lines are never rewritten (`test_record_appends_never_rewrites`). `spent()` sums `actual`. The committed file is empty (`test_committed_ledger_exists_and_parses`).

```
date            ISO UTC
step, models[], runs, estimate
actual          float >= 0, what spent() sums
actual_source   "logs" | "balance" | "cap"
cost_from_logs  Σ stats.model_usage[*].total_cost over the step's .eval files
cost_by_model   {model: cost}
total_tokens    Σ total_tokens (for Task 30's token-limit arithmetic)
unpriced_models, unreadable_logs, eval_statuses
retried_samples, failed_samples   (from error_retries / error; failures stay counted)
balance_before, balance_after, balance_error
error           redacted eval exception text, or null
eval_paths      relative to pilot-1/
```

`actual` rule (over-counting is safe; under-counting is not):
- default: `cost_from_logs` (`test_record_sums_model_usage`);
- raised to the gateway balance drop if larger (`test_record_uses_balance_drop_when_larger`);
- raised to the step cap if a log is unreadable, a model has tokens but no price, a log has no final stats (status `started`), or the eval failed before writing any log (`test_record_unreadable_log_counts_the_step_cap`, `test_record_incomplete_log_counts_the_step_cap`, `test_record_eval_failed_before_log_counts_the_step_cap`);
- a failed balance-after fetch still writes the line, with `balance_after: null` and a redacted `balance_error` (`test_record_still_writes_when_balance_after_fails`).

## 4. `run.py` dispatch table

`python -m temptation_bench.run --step {gfree,route_check,smoke,pregen,mini_batch,full_run} --estimate X [--token-limit N] [--sample-cost-limit X] [--dry-run]`

Order: unknown/unbuilt step refuses (no network) → sample cost limit resolved → `budget.guard` → plan printed → (`--dry-run` stops here) → launch → `budget.record` in a `finally`, so a crash or Ctrl-C still writes the ledger line.

| Step | Built? | Launch |
|---|---|---|
| `gfree` | **built** | `temptation_bench(variant=gfree, seeds=1001, doses=3000000)` on `openai-api/xpl/gpt-6-luna`, `max_samples=1` (plan Task 29 step 3) |
| `smoke` | **built** | same task, `variant=window`, `anthropic/claude-haiku-5-5`, seed 1001, dose 3000000, `max_samples=1`, people=template (pregen comes later in Task 31) |
| `route_check` | refuses | "the route-check script (2 Haiku calls + 1 qwen) is Task 30" |
| `pregen` | refuses | "the pregen_people task is Task 26" |
| `mini_batch` | refuses | "needs people=prose (Task 26) and the smoke-based estimate (Task 31)" |
| `full_run` | refuses | "needs the D11-D30 events and audit (Tasks 32-33)" |

- Each entry is `Step(plan, launch, not_built)`; later tasks fill in `plan` + `launch`. `test_dispatch_table_covers_every_step` pins built = {gfree, smoke}; `test_runner_refuses_unbuilt_steps_without_network` (transport asserts if called, no ledger line, no log dir); `test_runner_unknown_step_rejected_by_cli` (argparse, exit 2).
- Every eval gets `retry_on_error=1`, `cost_limit=<sample cost limit>`, `log_dir=logs/paid/<step>-<UTC stamp>/` (gitignored), and the `--token-limit` passed into the task's `token_limit` parameter (Task 24's plumbing).
- Sample cost limit (`default_sample_cost_limit`): `--sample-cost-limit` wins; else \$1.00 for gfree/route_check/pregen/smoke ("smoke itself \$1"); for mini_batch/full_run it is 2 × (latest smoke `actual` / its `runs`), and with no smoke line it **refuses** (`test_sample_cost_limit_defaults`). Zero, negative, NaN or inf refuses (`test_runner_refuses_bad_sample_cost_limit`).
- `--dry-run`: runs the guard (the balance fetch is the only network call), prints models, variant, seeds × doses, runs, max_samples, retry, cost/token limits, estimate/cap, spent/stop line, balance, log dir; launches nothing (`test_dry_run_checks_and_prints_plan_without_eval` replaces `inspect_eval` with a function that asserts; also checks a dry run still refuses over the cap). `test_runner_refusal_launches_nothing` covers the same for a real run.

## 5. Retry design

- **Automatic:** Inspect `retry_on_error=1` only. Same sample, so same seed and dose; it **keeps the cell cache** (verified in §1), so replayed turns cost \$0. The failed attempt stays in the `.eval` (`error_retries`), and its billed calls are in `stats.model_usage`, so in the ledger. `retried_samples` / `failed_samples` go into the ledger line for the report. The rerun must fit inside the same step cap: the `--estimate` help says so.
- `test_runner_reruns_failed_once_and_keeps_failure`: the runner runs `smoke` with a mockllm callable that raises once on call 3. It checks: status success; seed 1001 / dose 3000000; exactly one `error_retries` entry with the error text; `sample.error is None`; a T1 label exists; ledger `actual` equals the header stats cost; `retried_samples == 1`, `failed_samples == 0`; `log.eval.config.retry_on_error == 1` and `cost_limit == 1.00`.
- **Further reruns (never automatic):** `cell_scope(model, seed, dose, retry=k)` and `generate_config(..., retry=k)` give `model|seed|dose|retry<k>` for k ≥ 1, and the unchanged base for k = 0; k < 0 raises (`test_retry_scope_suffix`). It is plumbed to the cache-scope builder only. No task parameter or runner flag sets it yet, by design.
- `fail_on_error` keeps Inspect's default (True): a sample that fails twice stops the eval. That is fail-closed for spend; the ledger line is still written.

## 6. Redaction approach

- The key is read with `dotenv_values(path)` into a local variable, only inside `_env()`. It is never put into `os.environ` and never returned beyond `fetch_balance`/`record`.
- A transport error becomes `BudgetError(redact(message, [key]))`. It is **raised outside the `except` block**, so the original exception (which may echo the header) is not even kept as `__context__` (`test_balance_error_keeps_no_original_exception`). A non-200 never shows the body (it may echo the request).
- `redact(text, secrets)` removes exact secret values, then anything key-shaped: `\b(xpl_|sk-ant-|sk-)[A-Za-z0-9_-]+` and `bearer <token>`. Used on every CLI `REFUSED:`/`FAILED:` line and on the whole ledger line before writing (`test_redact_hides_key_and_bearer`, including a key-shaped value caught by shape alone).
- `test_key_never_in_ledger_or_stdout`: a successful mockllm smoke through `run.main`; then two error transports (one raises an error with the `Authorization` header in its message, one returns 401 with the header in the body) through `budget.check`, `run.main` and `budget.main`. It asserts no `xpl_` in stdout, stderr, the ledger or the formatted traceback, and that only one ledger line exists.
- **Test hygiene:** the fixture key is `xpl_FAKE-not-a-real-key-0000`. The hyphens keep it from matching `test_no_secrets`'s `xpl_[A-Za-z0-9]{16,}`. My first version built a 24-char alphanumeric key by string concatenation. CPython constant-folded it into the `.pyc`, and parametrize ids put it into `.pytest_cache`. `test_no_secrets` caught both (file names only were printed). Fixed with the hyphenated key, explicit ids, and a runtime `"".join` for the one key-shaped case.

## 7. Tests and TDD evidence

`tests/test_budget.py`: 39 test functions, 59 cases. The brief's six tests are all present by name.
- **RED 1:** collection `ImportError: cannot import name 'budget'`.
- **RED 2 (NotImplementedError stubs):** `52 failed in 4.43s`, every test.
- **GREEN:** `52 passed in 5.14s`.
- **Mutation checks** (each reverted after): drop `from None` → 1 failed; put the body in the non-200 message → 1 failed; drop the stop-line check → 1 failed; `RETRY_ON_ERROR = 0` → 1 failed; drop the negative-balance check → 1 failed.
- **Self-review additions (tests then mutation):** 3 tests (no `__context__`; error-without-log counts the cap; incomplete log counts the cap). Mutations: raise inside `except` → 2 failed; drop each cap rule → 1 failed each. Bad sample cost limit: RED `1 failed, 3 passed` (inf passed), then GREEN.
- Final: `59 passed in 5.24s`.

## 8. Suite outputs (final tree)

- `uv run pytest -q` → `629 passed, 71 deselected in 139.36s`
- `uv run pytest -q -m slow` → `71 passed, 625 deselected in 258.90s`. This ran before the final one-line `run.py` change (the finite check on the sample cost limit). No slow test imports `run.py`, and the default suite was re-run after that change.
- `uv run ruff check . && uv run ruff format --check .` → `All checks passed!` / `98 files already formatted`
- Golden hash: no engine file changed; `tests/golden` green in the default suite.

## 9. Files changed

- `pilot-1/src/temptation_bench/budget.py`: new (constants, `BudgetError`, `redact`, `fetch_balance`, `spent`, `ledger_entries`, `guard`, `check`, `record`, CLI).
- `pilot-1/src/temptation_bench/run.py`: new (dispatch table, `run_step`, `default_sample_cost_limit`, CLI).
- `pilot-1/src/temptation_bench/harness/settings.py`: `retry` parameter on `cell_scope` and `generate_config` (default 0: unchanged behaviour).
- `pilot-1/tests/test_budget.py`: new.
- `pilot-1/budget/ledger.jsonl`: new, empty.
- No dependency change: `httpx` and `python-dotenv` were already explicit in `pyproject.toml`. `.gitignore` already covers `.env`, `logs/`, `runs/`, `*.eval`.

## 10. Self-review

- **Key leak paths checked:** env loading (local dict only); request (https only, no redirects); transport error (redacted, no context chain); non-200 (status only); ledger (exact-value and shape redaction of the whole line); CLI stderr (redacted); `record`'s `error` field (redacted with the key). `_plan_text` prints no env value. `harness.json` is untouched (Task 24 test still green).
- **Spend paths checked:** nothing launches before `guard`. Unbuilt steps refuse before any network. `record` runs in `finally`, even on `BaseException`. `actual` cannot under-count a failed attempt (header stats), an unreadable or incomplete log, or a crash before the log (cap). A missing smoke blocks mini_batch/full_run defaults. inf/NaN limits and estimates refuse.
- Engine untouched; `budget.py`/`run.py` live outside `engine/`; layering test green. No agent-facing text added.
- Not built (out of brief scope): `--list-models` (Task 29 step 1), the route-check script (Task 30), a default `--token-limit` from the smoke (I record `total_tokens` so Task 30 can compute it).

## 11. Concerns

1. **G-free will be recorded at paid prices.** Luna is registered at \$0.10/\$0.50, so Inspect computes a non-zero `total_cost` for the free-tier run (≈ \$0.08 for 800k tokens). The ledger then counts it, which is conservative. Plan Task 29 step 5 says "record actual: 0". The controller should decide: accept the over-count, or add an explicit, logged free-tier override in Task 29. I did not add a way to lower `actual`.
2. **`--list-models` (plan Task 29 step 1) is not implemented.** The brief's CLI does not list it. Task 29 needs it, or the step changes.
3. **The failed attempt's engine JSONL is overwritten by the rerun.** `setup_run` uses the same `<sample_id>-e<epoch>.jsonl` path, and `write_jsonl` overwrites. The failure itself stays in the `.eval` (`error_retries` + traceback + events back to the last model call) and in the ledger counts. If the report needs the failed attempt's engine events, `agent.py` would need an attempt suffix (not changed here; harness scope).
4. **Per-model cost limit:** `eval(cost_limit=...)` is one number per eval. The spec's "2 × smoke cost for that model" only has a Haiku smoke; Luna in the mini-batch has none. That is Task 31's call (separate evals per model, or one limit).
5. **Credits body shape is assumed** (`total_credits`/`total_usage`, top level or under `data`). Any other shape fails closed, so G-free step 2 will show it.
6. Inspect's `init_dotenv` loads the real `pilot-1/.env` into the *test* process's `os.environ` whenever a test calls `inspect_eval` from `pilot-1/` (this was already so before this task). No test prints env values. My test checks only that the *fake* key never enters `os.environ`.

## Fix wave [22-26] round 1

- Fixer: review `review-22-26.md` (R22-1, R25-1, R25-2, R26-1, X-1 Important; R24-1, R24-2, R25-5 folded in by ruling). TDD per finding (RED seen before each fix). No network, no paid call; `.env` never read (the review's checks only). Engine untouched, golden unchanged.
- Skills: `superpowers:test-driven-development`, `superpowers:receiving-code-review`, `temptation-bench-architect`. Inspect facts below are from the installed 0.3.291 source.

### R25-1 (do first): tests block every real model API
- Changed: `tests/conftest.py` sets `INSPECT_DISABLE_MODEL_API=1` at import (before any fixture/test can call `inspect_ai.eval`) and again in an autouse fixture `no_model_apis` (monkeypatch, in case a test removes it). Inspect: `Model.verify_model_apis` (`model/_model.py:2315-2320`, called in `generate` at :1853 after the cache lookup) refuses every non-mockllm API. `init_dotenv` uses `load_dotenv` without override (except under VS Code), so the real `.env` cannot unset it. Building a real-provider `Model` still works (only `generate` checks).
- Note found while fixing: `verify_model_apis` is **not** called by `count_tokens`, so the switch alone would not stop R22-1's count calls. R22-1 removes them.
- Tests: `tests/test_model_api_guard.py::test_model_api_switch_is_on`, `::test_non_mockllm_model_refuses_under_switch` (Anthropic model built with a fake key and `.invalid` base URL; asserts the switch first so a RED can never attempt a call), `::test_mockllm_still_runs_under_switch`.
- RED: `3 failed in 1.13s`. GREEN: `uv run pytest -q tests/test_model_api_guard.py` -> `3 passed in 2.03s`. Default suite after: `647 passed, 71 deselected in 140.38s`.
- Commit `02a0340`.

### R22-1 (option a): compaction counts tokens locally
- Changed: new `harness/counting.py::LocalCountModel(target)`, a `Model` that shares the real model's `api`, `config`, `model_args` and role (so `collapse_consecutive_messages_for_api(target_model.api)`, `str(model)` and the CompactionEvent role match), overrides `count_tokens` with Inspect's local helper `inspect_ai.model._tokens.count_tokens/count_text_tokens/count_media_tokens`, and refuses `generate`. `count_tool_tokens` (base `Model`) calls `self.count_tokens`, so the tool count is local too. `agent.py` passes `compaction(..., model=LocalCountModel(get_model()))`.
- **Counter chosen:** Inspect's default local counter, tiktoken `o200k_base` + 10% buffer (the default `ModelAPI.count_tokens`, which mockllm uses). The Task 22 report §1 measured the 3,623-token floor with this counter, so `MIN_TRIM_TOKENS = 5000` and `trim_tokens` stay in the same unit. I left the floor comment in `engine/config.py` alone because editing an engine file changes the engine SHA. After the first generate, Inspect's baseline is the provider's reported `input_tokens` from that generate's own usage (no extra call), plus local counts of the new messages.
- Tests: `tests/harness/test_local_count.py::test_local_count_never_calls_the_anthropic_count_api` (`AnthropicAPI.count_tokens` patched to raise; the spy is shown to fire on the plain model and not on the wrapper; counts equal Inspect's helper), `::test_local_count_model_keeps_the_target_identity`, `::test_compacted_run_makes_no_model_count_tokens_call` (`Model.count_tokens` patched to raise; the SMALL_TRIM e2e still succeeds, compacts, and logs `review_in_window=False`).
- RED (stub module): `3 failed`; the e2e failed with `AssertionError('Model.count_tokens called: would reach the provider')`, status `error`. GREEN: `uv run pytest -q tests/harness/test_local_count.py tests/harness/test_window.py` -> `13 passed in 6.13s`.
- Commit `4a267cd`.

### R26-1: pregen uses the global model settings
- Changed: `pregen_people.rewrite` builds `GenerateConfig(reasoning_effort=h["reasoning_effort"], max_retries=int(h["max_retries"]))` from `load_config("window").harness`, and passes it on the people `generate`.
- Test: `tests/harness/test_pregen.py::test_pregen_uses_the_global_model_settings`. It checks `ModelEvent.config.reasoning_effort == "low"`, `max_retries == 5`, and that temperature and seed are None on every people call.
- RED: `1 failed`. GREEN: `uv run pytest -q tests/harness/test_pregen.py` -> `15 passed in 11.11s`.
- Commit `9e569fe`.

### Cache scope (Task 26 ruling + R24-1) and R24-2
- Changed in `harness/settings.py`:
  - `CELL_SCOPE = "{model}|{seed}|{dose}|{people}|{variant}"`.
  - `cell_scope(model, seed, dose, people, variant, retry=0)`.
  - `generate_config(..., *, people, variant, retry=0)`: people and variant are required keywords, so there is no silent default.
  - `write_harness_json(..., *, people)` records the scope string and a new `"people"` field (R24-2).
  - `agent.py` passes `st.people` and `config.variant`.
- The retry suffix still follows (`...|retry<k>`).
- Harness only: the golden test dir is unchanged (`git diff 9715bf3 -- tests/golden` is empty).
- Tests in `tests/harness/test_settings.py`:
  - `::test_cache_scope_differs_by_dose` (kept, new string)
  - `::test_cache_scope_differs_by_people`
  - `::test_cache_scope_differs_by_variant`
  - `::test_cell_scope_needs_people_and_variant`
  - `::test_generate_config_exact_settings`
  - `::test_harness_json_records_temperature_not_set_and_retries` (scope string and `people == "template"`)
  - `::test_harness_json_records_a_prose_backend`
- Test in `tests/test_budget.py`: `::test_retry_scope_suffix`.
- RED: `10 failed, 2 passed`. GREEN: `uv run pytest -q tests/harness/test_settings.py tests/test_budget.py` -> `75 passed in 7.01s`; `tests/harness tests/golden` -> `71 passed`.
- Commits `87d712a` and `4d16da5` (ruff line length and format).

### R25-2, R25-5, X-1 (`run.py`)
- **X-1:** `one_model(plan, model)` raises `RunnerError("one model per eval: ...")` when a plan names anything other than one model and no override is given.
  - `launch_task_eval` uses it, so it is structural.
  - `run_step` calls it first, before the guard, any network or any ledger line. Raising inside the launch alone would have written a ledger line charged at the step cap.
- **R25-2:**
  - `exposure(plan, limit) = runs × sample_cost_limit × ATTEMPTS`, where `ATTEMPTS = 1 + RETRY_ON_ERROR` = 2.
  - `check_exposure(...)` runs before the guard, using the local `spent()`. It refuses with a `BudgetError` if the exposure is over `STEP_CAPS[step]`, if `spent + exposure > STOP_LINE`, or if it is unknown (no cost limit; never \$0).
  - The plan and dry run print `exposure:` with the arithmetic.
- **Rules chosen (please confirm):**
  - **Smoke default sample cost limit is now \$0.50**, set as min(\$1, cap / (runs × attempts)) for the steps before the smoke. The old \$1 default (spec §7.3 "smoke itself \$1") could not pass the ruled check: 1 × \$1 × 2 = \$2 is over the \$1 cap. The planning cost of \$0.13–0.33 per run is still inside \$0.50.
  - **G-free rule:** a free-tier step (`Plan.free_tier_tokens = 1_000_000`, Luna's 1M tokens/day) is bounded in tokens, not dollars. It needs a token limit, and runs × token_limit × attempts must be ≤ 1,000,000, else it refuses. The plan then prints "\$0 within the free tier (N of 1000000 free-tier tokens ...)". Without `--token-limit`, gfree defaults to its free-tier share, 1M // (1 × 2) = **500,000**. The \$1 sample cost limit stays as a list-price runaway stop. This also covers R25-3 (gfree had no default token limit), because those lines were rewritten anyway.
  - **Consequence:** plan Task 29 step 3's `--token-limit 800000` is now refused (800k × 2 attempts = 1.6M is over the free tier). Use 500,000 or omit the flag. A lower limit may cut a D1–D3 Luna run short, but it still ends sealed and scored.
- **R25-5:** `default_token_limit(ledger)` returns 2 × T̂_run from the latest smoke line with integer `total_tokens > 0` and `runs > 0`, as `2 * total_tokens // runs`. Old lines without the fields are skipped, so the ledger stays append-only and readable, and before any smoke it returns None.
  - **T̂_run counter:** `record` already wrote `total_tokens`, so the ledger schema is unchanged. That field is Inspect's `total_tokens`: input including cache reads and writes, plus output. It is the same quantity Inspect's default token limit (`"all"`) meters (`util/_limit.py:436`). An input count that excluded cache reads would trip the limit early on a cached Haiku run.
  - Precedence: `--token-limit`, then the free-tier share (gfree only), then 2 × smoke mean, then none. The source is printed.
- Tests in `tests/test_budget.py`:
  - `::test_exposure_is_runs_times_limit_times_attempts`
  - `::test_exposure_refuses_over_step_cap`
  - `::test_exposure_refuses_over_stop_line` (it also checks that the dry-run line prints)
  - `::test_exposure_unknown_refuses_a_paid_step`
  - `::test_default_smoke_sample_cost_limit_fits_the_cap`
  - `::test_dry_run_prints_the_exposure`
  - `::test_gfree_exposure_is_counted_in_free_tier_tokens`
  - `::test_default_token_limit_from_smoke`
  - `::test_runner_defaults_the_token_limit_after_a_smoke`
  - `::test_record_keeps_token_totals_for_the_default` (mockllm smoke through `run_step`)
  - `::test_launch_refuses_more_than_one_model`
  - `::test_runner_refuses_a_two_model_step_before_any_call`
  - Updated: `::test_runner_reruns_failed_once_and_keeps_failure` (cost_limit is now 0.50), `::test_sample_cost_limit_defaults`, `::test_dry_run_checks_and_prints_plan_without_eval` (gfree at 500000).
- RED: `14 failed, 57 passed`. GREEN: `uv run pytest -q tests/test_budget.py` -> `71 passed in 5.64s`.
- Mutation checks (reverted after): dropping the stop-line exposure check -> `1 failed`; `ATTEMPTS = 1` -> `8 failed`.
- Commit `c63edfc`.

### Minors
- Fixed because they were in rewritten lines: R24-2 (allowed), and R25-3 (gfree default token limit).
- No other Minor was touched: R22-2, R23-1, R23-2, R25-4, R26-2, R26-3, R26-4 and the X-2 nuance are still open.

### Final suite outputs
- `uv run pytest -q` -> `667 passed, 71 deselected in 132.42s`
- `uv run pytest -q -m slow` -> `71 passed, 667 deselected in 255.22s`
- `uv run ruff check . && uv run ruff format --check .` -> `All checks passed!` / `103 files already formatted`
- `git status` clean in `pilot-1/` after the last commit. Golden unchanged. Not pushed. PROGRESS.md not edited.

### Concerns for the controller
1. Two binding numbers changed to satisfy the ruled exposure check: the smoke's default sample cost limit is now \$0.50 (spec §7.3 says \$1), and G-free's token limit is at most 500k (spec §6 says 800k). Both are recorded above. The alternative for G-free is no retry on that step; I did not choose it.
2. The free-tier check assumes nothing else used Luna's free tokens that day.
3. `LocalCountModel` imports the private `inspect_ai.model._tokens`. This is safe under the pinned 0.3.291, but recheck it on any Inspect upgrade.

### Round 1b (controller ruling: G-free keeps spec §6's 800k; no automatic rerun)
- Changed (`run.py`): `Plan` gained `retry_on_error` (default `RETRY_ON_ERROR = 1`), a step default `token_limit`, and an `attempts` property (1 + retries). The G-free plan sets `retry_on_error=0` and `token_limit=800_000` (`GFREE_TOKEN_LIMIT`). `launch_task_eval` passes `retry_on_error=p.retry_on_error`. Exposure, the free-tier token check, the default sample cost limit and the printed plan all use `plan.attempts`. G-free's worst case is now 1 run × 800k × 1 attempt = 800k, within the 1M free tier. Every other step keeps 1 retry, and the exposure counts it (the smoke is still 1 × \$0.50 × 2). The token-limit precedence is now `--token-limit`, then the step default (G-free 800k), then 2 × the smoke mean, then none. The "free-tier share" default is gone.
- Tests (`tests/test_budget.py`):
  - `::test_gfree_exposure_is_counted_in_free_tier_tokens` (800k passes and prints "800000 of 1000000 free-tier tokens: 1 runs x 800000 tokens x 1 attempts"; 1.2M is refused with no network call)
  - `::test_gfree_cli_token_limit_800k_passes_and_1200k_refused` (CLI exit 0 and non-zero, "free tier" on stderr)
  - `::test_gfree_default_token_limit_is_spec_800k` (the step default wins over a smoke-based default)
  - `::test_gfree_launches_without_retry_and_smoke_with_one` (fake `inspect_eval` records `retry_on_error` 0 for gfree and 1 for smoke; attempts are 1 and 2)
- RED: `4 failed, 70 passed`. GREEN: `uv run pytest -q tests/test_budget.py` -> `74 passed in 5.85s`.
- `uv run pytest -q` -> `670 passed, 71 deselected in 147.82s`. `uv run ruff check . && uv run ruff format --check .` -> `All checks passed!` / `103 files already formatted`.
- Commit: `pilot-1: fix R25-2 G-free no retry, keep spec 800k token limit`. Not pushed. PROGRESS.md not edited.
