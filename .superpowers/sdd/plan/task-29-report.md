# Task 29 pre-work report (S5): list-models, G-free dollar check, model costs, tiktoken cache

No network calls were made. Every gateway interaction is tested with `httpx.MockTransport`
or a blocked `httpx.Client.send`. `pilot-1/.env` was only checked with `test -s .env && echo present`
(present).

## Inspect facts verified (cost data), installed source `pilot-1/.venv/lib/python3.13/site-packages/inspect_ai/`

- `_eval/eval.py:879` calls `resolve_model_costs(resolved_tasks, cost_limit)` after the tasks
  are resolved and before any log is written. In `model/_util.py:67-97`, with a `cost_limit`
  each task's model needs `_get_model_info_direct(model).cost`. If it is missing, Inspect raises
  `PrerequisiteError("cost_limit requires cost data for all models ...")`.
- `model/_model_info.py:356-374` (`_resolve_model_info` for a `Model`) checks the custom
  registry (`set_model_info` / `set_model_cost`) under `str(model)` first, then
  `canonical_name()`, then the built-in DB. `set_model_cost` (`:489`) needs the model to
  already be in the DB. `set_model_info` (`:461`) works for any name.
- Built-in DB (`model/_model_data/anthropic.yml:218`, `openai.yml:519`): both
  `claude-haiku-5-5` and `gpt-6-luna` exist, but neither has `cost`. A probe built
  `get_model(slug, api_key=fake, base_url=.invalid)` and showed:
  - `anthropic/claude-haiku-5-5`: str = canonical = `anthropic/claude-haiku-5-5`, cost None.
  - `openai-api/xpl/gpt-6-luna`: str = `openai-api/xpl/gpt-6-luna`, canonical `gpt-6-luna`, cost None.
  - Without registration, the eval would therefore fail at start with `PrerequisiteError`.
- The project already registers prices. `harness/task.py:34` calls `register_prices()`
  (`harness/pricing.py`, `set_model_info` from `configs/pricing.yaml`, keyed by the exact
  runner strings, spec §7 prices). `run.launch_task_eval` builds the task, which registers the
  prices, before it calls `inspect_eval`. After registration both slugs resolve a price under
  `str(model)`. **No code change was needed for the price lookup.** The new tests lock it in.
- Pricing per call (`model/_model.py:4007-4060`, `model_usage_cost`): if the gateway reports a
  different serving model with no cost, Inspect prices the call at the called model's rates
  (warn once). The cost is still recorded.
- Log timing (`_eval/task/run.py:1386`): `logger.log_start(...)` flushes the `.eval` before any
  sample runs (`run_sample` comes later, at `:1613+`). So **no `.eval` in the log dir means no
  model call**. This is the basis of the ledger rule change.
- `count_tokens`: `Model.count_tokens` (`_model.py:1379-1425`) calls `self.api.count_tokens`.
  `AnthropicAPI` and `GoogleGenAIAPI` override it with network APIs. `INSPECT_DISABLE_MODEL_API`
  does not gate it.
- tiktoken (`tiktoken/load.py:35-53`, `read_file_cached`): it reads `TIKTOKEN_CACHE_DIR` on every
  blob load. The default is `$TMPDIR/data-gym-cache`. The cache file name is
  sha1(blob URL) = `fb374d419588a4632f3f557e76b4b70aebbca790` for o200k_base. The file is
  checked against SHA-256 `446a9538…`, and the copied file matches.

## Items, tests, output

RED was run against the stashed old `src/` with the new tests: **17 failed, 4 passed**. The 4
that passed are the two price tests and `test_estimate_still_required_without_list_models`,
which cover behavior that already existed, plus the conftest-block test, whose RED would need a
real provider count attempt, so it was not run red. GREEN: all pass (output below).

1. **`--list-models`**
   - Code: `budget.list_models` and `budget.models_url`, plus `run.list_models_cli`.
   - What it does:
     - `GET {XPL_BASE_URL}/models` with `Bearer` from `dotenv_values`.
     - Keeps only `id` strings, each redacted, then sorts them and prints one per line. Nothing else is printed.
     - Fails closed on transport error, non-200, non-JSON, empty list, or a non-string id. Prints `REFUSED: list models failed...`, redacted, with exit 1.
     - The error is raised outside the `except`, so it keeps no `__context__`.
     - Allowed only with `--step route_check`. It skips the guard and writes **no ledger line** (free metadata, no spend).
     - `--estimate` is now optional only when `--list-models` is given. Otherwise argparse errors as before.
   - Tests (`tests/test_budget.py`):
     - `test_list_models_prints_only_the_sorted_ids`: checks the URL, the header and exact stdout, empty stderr, and no ledger line.
     - `test_list_models_never_prints_an_echoed_auth_header[ok_with_key_in_id|unauthorized|connect|not_json|no_ids|bad_id]`: the auth header is echoed in the body, the ids and the exception, and is never in stdout or stderr. "Bearer" is never in the output either.
     - `test_list_models_error_keeps_no_original_exception`
     - `test_list_models_only_on_route_check`
     - `test_estimate_still_required_without_list_models`
     - `test_list_models_fails_closed_without_env`
2. **G-free dollar check**
   - Code: in `run.check_exposure`, the free-tier branch now also computes `runs × sample_cost_limit × attempts` (1 × \$1 × 1).
   - It refuses if `spent + that > STOP_LINE`, or if the cost limit is None.
   - The plan line now reads: `$0 within the free tier (800000 of 1000000 free-tier tokens: 1 runs x 800000 tokens x 1 attempts); $1.0000 if billed (1 runs x $1.0000 x 1 attempts)`.
   - Tests:
     - `test_gfree_refuses_when_spent_plus_dollar_exposure_is_over_the_stop_line`: 8.60 + 1 > 9.50, refused before any network call.
     - `test_gfree_dollar_check_uses_one_attempt`: 8.40 passes, 8.51 is refused, None means unknown.
3. **Cost data plus the ledger rule**
   - Prices: no change needed (see the facts above). Tests (`tests/harness/test_pricing.py`, both with `httpx.Client/AsyncClient.send` patched to raise):
     - `test_inspect_has_no_built_in_price_for_the_gateway_slugs`: after `clear_model_info_cache`, Inspect's real `resolve_model_costs` raises `PrerequisiteError` for both slugs. This shows why registration matters.
     - `test_runner_slugs_resolve_a_price_before_the_eval_without_network`: for `gfree` and `smoke`, `run.launch_task_eval` runs with a fake `inspect_eval`. The fake builds the model the way Inspect does and runs the real `resolve_model_costs`, which passes. It also checks that the resolved input and output prices equal `configs/pricing.yaml`.
   - Ledger: `budget.record` no longer charges the step cap when the eval failed with no `.eval` written. `actual` = summed log usage (0), raised to the balance drop if that is larger. The redacted `error` is kept on the line. The cap rule stays for an unreadable log, an unpriced model with tokens, or a log without final stats.
     - The old test `test_record_eval_failed_before_log_counts_the_step_cap` contradicted the ruling, so it was replaced by `test_record_eval_failed_before_log_charges_actual_usage_not_the_cap` (0 when the balance is unchanged; 0.25 from `balance` when it drops).
     - New end-to-end test: `test_runner_prerequisite_error_at_start_records_zero`.
4. **Durable tiktoken cache**
   - Code: `harness/counting.py` sets `os.environ["TIKTOKEN_CACHE_DIR"] = pilot-1/.cache/tiktoken` at import, before its own `inspect_ai` imports.
   - `counting.py` is imported by `harness/agent.py`, and so by `task.py`, before `inspect_eval`.
   - `seed_tiktoken_cache` makes the dir and copies o200k_base from `$TMPDIR/data-gym-cache` if it is there. It uses a plain copy plus `os.replace`, never overwrites, and makes no network call.
   - `pilot-1/.gitignore` gets `.cache/`. The file is now in `pilot-1/.cache/tiktoken/` (3.6 MB, SHA-256 matches tiktoken's expected hash) and git ignores it.
   - Tests (`tests/harness/test_local_count.py`):
     - `test_tiktoken_cache_dir_is_durable_and_set_when_the_counter_loads`: pops the variable, reloads the module, and checks the variable is set again.
     - `test_tiktoken_seed_copies_the_tmp_cache_file_without_network`
     - `test_o200k_cache_key_is_tiktokens`
5. **Block count_tokens in tests**
   - Code: the autouse fixture `no_provider_count_tokens` in `tests/conftest.py` does two things:
     - It wraps `Model.count_tokens` so it raises `AssertionError("provider count_tokens API called in a test (...)")` unless `model.api` is `MockLLM`.
     - It patches `count_tokens` / `count_text_tokens` on every loaded `ModelAPI` subclass that defines them, except MockLLM. `AnthropicAPI` is always covered, and `GoogleGenAIAPI` if it is importable.
   - `LocalCountModel` overrides `Model.count_tokens`, so it still works.
   - Test: `test_conftest_blocks_provider_count_tokens` covers Haiku at the Model and API levels, Luna at the Model level, mockllm still counting, and LocalCountModel still counting.

Test output (final run):
- `uv run pytest -q`: `724 passed, 71 deselected` ; rerun after the lint-only edits: `724 passed, 71 deselected in 151.71s`
- `uv run pytest -q -m slow`: `71 passed, 724 deselected in 238.36s`
- `uv run ruff check . && uv run ruff format --check .`: `All checks passed!`, `108 files already formatted`
- Targeted: `uv run pytest -q tests/test_budget.py tests/harness/test_pricing.py tests/harness/test_local_count.py`: `98 passed`

## Commands for the controller (run from `pilot-1/`)

These are the same as the brief. The CLI matches it, and `--list-models` needs no `--estimate`.

1. `uv run python -m temptation_bench.run --step route_check --list-models`
   - Success: exit 0 and only model ids on stdout, one per line, sorted, with nothing on stderr. Check that the Haiku and Luna slugs appear in the gateway's own spelling. No ledger line is written.
   - Failure: `REFUSED: list models failed: HTTP 401` (or similar) on stderr, exit 1.
   - Note: the ids are the gateway's names, for example `anthropic/claude-haiku-5-5` or `openai/gpt-6-luna`. The Inspect strings in `run.py` are `anthropic/claude-haiku-5-5` (Anthropic provider, `ANTHROPIC_BASE_URL`) and `openai-api/xpl/gpt-6-luna`. Inspect sends `gpt-6-luna` as the wire model to `XPL_BASE_URL`. If the listing shows Luna under a prefixed id such as `openai/gpt-6-luna`, the runner slug must change to `openai-api/xpl/openai/gpt-6-luna`, and `configs/pricing.yaml` needs the same key.
2. `uv run python -c "from temptation_bench.budget import fetch_balance; print(round(fetch_balance(), 2))"`
   - Success: one number, for example `10.0`. If there is an error, stop.
3. `uv run python -m temptation_bench.run --step gfree --estimate 0 --token-limit 800000`
   - The plan prints first. Expect:
     - `exposure: $0 within the free tier (800000 of 1000000 free-tier tokens: 1 runs x 800000 tokens x 1 attempts); $1.0000 if billed (1 runs x $1.0000 x 1 attempts)`
     - `sample cost_limit: $1.0000`
     - `retry_on_error: 0`
     - `gateway balance: $X`
   - Then Inspect runs, and the last line is `recorded: gfree actual $0.0000 (logs); spent $0.0000 of $9.50`.
   - If the eval fails at start (for example a `PrerequisiteError`), the line is now `actual $0.0000` with `error` set, not the cap.
   - Option: run `... --dry-run` first. It calls only the balance endpoint, needs no eval and writes no ledger line.
4. Inspect the `.eval` under `pilot-1/logs/paid/gfree-<stamp>/`. Commands:
   - `uv run inspect log dump <file> | jq '.stats.model_usage'` shows `ModelUsage` with `total_cost`.
   - Check the tool events and status lines in the sample messages.
   - Check that no model events are `count_tokens`. Openai-api uses the local counter anyway, and compaction uses `LocalCountModel`.
   - Look for the upstream route in the `ModelEvent` `output`/`call.response` body fields.
5. Run the step 2 command again to see the balance is unchanged. The runner already wrote the ledger line with `actual: 0` (source `logs`). Do not add a second line. Then `uv run pytest tests/test_no_secrets.py`, PROGRESS.md, and commit.

## Concerns

- **Slug spelling** (step 1): the runner and pricing keys assume the wire id `gpt-6-luna` on the xpl route. A prefixed gateway id means renaming both. Step 3 would otherwise fail at the gateway (HTTP 4xx), not at the cost gate.
- **Luna's registered ModelInfo is cost-only.** It shadows the DB entry for `str(model)` lookups, for example `context_length`. `get_model_input_tokens` still falls back to the DB (922k), so compaction is unaffected. Other info-driven behavior (`family`) uses the service name. Haiku's registration copies the DB entry, so it keeps its fields.
- **Ledger rule with no log and an unreadable balance:** `actual` is 0 and the line has `balance_error`. This relies on the Inspect fact that the log is flushed before any sample. If Inspect changes that ordering, the rule would under-count.
- **The G-free \$1 cost limit only bounds spend if the gateway bills Luna.** Inspect checks the limit after each call, so overshoot by one generate is possible (rereview Minor 2).
- **RED for the conftest block was not run.** Running it would have meant a real `AnthropicAPI.count_tokens` attempt against `gw.example.invalid`. An earlier combined test run was started before the fixture existed and was stopped. It may have made DNS lookups or connection attempts to the `.invalid` test host only (no key, no real service).
- **The `.cache/tiktoken` copy is per checkout.** A fresh clone downloads o200k_base once into it, unkeyed and free.

## Fix: strict tools

**Cause.** The gateway returned 400 `invalid_function_parameters` for `list_applications`.
- Inspect's `openai-api` provider defaults to `strict_tools=True` (`inspect_ai/model/_providers/openai_compatible.py:99`, stored at `:171`).
- `tools_to_openai` (`:562-567`) sets `function.strict = self.strict_tools` on every tool.
- OpenAI strict mode needs every property in `required`. Our optional params, such as `status`, break that.
- `strict_tools` is a constructor arg only. No other code path in the installed source reads it.

**Fix.** The tool schemas are unchanged, and so is the Anthropic route.
- New `src/temptation_bench/harness/routes.py`:
  - `model_args_for(slug)` returns `{"strict_tools": False}` for `openai-api/...` slugs and `{}` for any other slug.
  - `non_strict_tools(model)` sets `api.strict_tools = False` on an `OpenAICompatibleAPI` and leaves other providers untouched.
  - `PEOPLE_MODEL = "openai-api/xpl/qwen3.7-flash"`.
- Runner seam: `run.launch_task_eval` passes `model_args=model_args_for(model)` to `inspect_eval`.
  - This is the `-M` equivalent. Inspect's `resolve_models(model, base_url, model_args, ...)` (`_eval/eval.py:2117-2128`) builds the main model with it inside the eval, after Inspect loads `.env`.
  - The Haiku route gets `{}`.
- Pregen seam: `harness/pregen_people.py` now has `people_model()` = `non_strict_tools(get_model(role="people", required=True))`, which the `rewrite` solver uses.
  - Model roles accept only `str | Model` (`model/_model.py:3508`). A string role is built with no args (`model/_util.py:49-57`).
  - So the role model is fixed after Inspect builds it.
  - The runner's pregen launch is still Task 31.
- `inspect eval` run directly from the CLI, without the runner, needs `-M strict_tools=false` for Luna.

**Tests** (`tests/harness/test_strict_tools.py`; models are only built, with a fake key and an `.invalid` URL):
- `test_runner_builds_luna_with_strict_tools_off`: the runner's `model` + `model_args` give `strict_tools is False`, and `tools_to_openai` gives `"strict": False` for all 18 tools.
- `test_runner_leaves_the_anthropic_route_unchanged`: smoke/Haiku gets `model_args == {}`.
- `test_pregen_people_model_has_strict_tools_off`: qwen built the way Inspect builds a role is strict by default (this is the bug). After `people_model()` all 18 tools are non-strict.
- `test_non_strict_tools_ignores_other_providers`
- `test_every_tool_schema_is_strict_valid_or_strict_is_off` (Luna and qwen).

RED: collection failed because `harness.routes` and `people_model` did not exist yet. GREEN:
- `tests/harness/test_strict_tools.py`: 5 passed.
- `uv run pytest -q`: `729 passed, 71 deselected`.
- Ruff: clean.

**Note:** `budget/ledger.jsonl` has the controller's G-free line (`actual 0.0`, balance unchanged). It is not part of this commit. The controller commits it in step 5.
