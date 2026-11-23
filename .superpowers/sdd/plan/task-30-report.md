# Task 30 pre-work report (S5): route-check launcher, smoke estimate helper

No network calls were made. The two Haiku calls that must produce a real Anthropic request
go through Inspect's real `AnthropicAPI` request builder, with its SDK client's
`messages.create` swapped for a local fake. qwen is mockllm. The balance call uses
`httpx.MockTransport`. `.env` was never read.

## Inspect facts verified (installed `inspect-ai==0.3.291`, `pilot-1/.venv/lib/python3.13/site-packages/inspect_ai/`)

- **The effort field is `output_config.effort`.** In `model/_providers/anthropic.py`,
  `completion_config` sets it at `:1521-1526`:
  - For a Claude-frontier model (`is_claude_frontier()` includes `is_claude_5()`, `:2002`),
    `effort_from_reasoning_effort` (`:2781`) maps `reasoning_effort="low"` to `"low"`.
  - `is_using_thinking` is then true, so it sets `params["output_config"] = {"effort": "low"}`
    and `params["thinking"] = {"type": "adaptive", ...}`.
  - Probe: a real `AnthropicAPI.generate` with a fake client gave a request with
    `output_config: {"effort": "low"}`, `thinking: {"type": "adaptive", "display":
    "summarized", ...}` and `max_tokens: 512`, with no temperature and no seed.
- **Where it is logged:** `generate` (`:932-1083`) builds the `request` dict ("assembled this
  way so we can log the raw model call") and records it as `ModelCall.request`. That becomes
  `ModelEvent.call.request` in the sample's events. The check reads
  `event.call.request["output_config"]["effort"]`.
- **`cache_prompt="auto"`** counts as True for Anthropic (`:2343-2363`). It adds
  `cache_control` to the last system block and the last tool, a lookback mark on messages,
  and a top-level `cache_control` for automatic caching (`:942`). The fake-client test checks
  `system[-1].cache_control.type == "ephemeral"`.
- **`ModelUsage.input_tokens_cache_read`** (`model/_model_output.py:37`) comes from Anthropic's
  `cache_read_input_tokens`. The probe showed 6000 in, 6000 out.
- **How a plain `get_model(...).generate(...)` call is logged** (`model/_model.py`):
  - The local response cache is used only when `cache` (the argument, or else
    `config.cache`) is truthy (`:1066-1071`, `:1699-1703`). We pass `cache=False`, so the
    `ModelEvent.cache` is `None`.
  - With a `CachePolicy`, a miss logs `cache="write"` and stores the output (`:2167`). A hit
    logs `cache="read"` with `call=None` (`:1813-1844`), records no usage, and returns before
    `verify_model_apis`. So a full local-cache re-run costs \$0.
  - Inside a sample, each generate is a `ModelEvent` in `sample.events`. The usage of both
    models goes into `log.stats.model_usage`, keyed per model, which `budget.record` sums.
  - The logged inputs are attachments. The checks read the log with
    `read_eval_log(..., resolve_attachments=True)`.
- **Max tokens:** an explicit `max_tokens` is sent as-is. `max_tokens_for_config`, which
  adds thinking room, runs only when `max_tokens` is None (`:1653`).
- **Streaming:** in the real run, Haiku streams (auto mode, because of reasoning). The fake
  tests use `streaming=False`. The `request` dict is the same either way (`:1357-1364`).

## Items, tests, output

RED: `tests/harness/test_route_check.py` and `tests/test_estimate.py` failed to collect
because their modules did not exist. `tests/test_run_route_check.py` gave 8 failed and 2
passed. The 2 that passed are the smoke-plan tests from item 5, which lock in behavior that
already existed. Then GREEN.

1. **The `route_check` launcher.**
   - Code: `src/temptation_bench/harness/route_check.py` (new) and `src/temptation_bench/run.py`.
   - The `@task route_check(people_model, reuse_cache)` has one sample. Its solver
     `route_calls` makes:
     - 2 Haiku generates with `get_model()` (the eval's model). They use the same system
       prefix `policy_prefix()` (a fixed branch handbook, 8,268 local tokens, so ≥ 5k),
       the one tool `read_policy_section`, and two different questions.
     - 1 people generate with `get_model(PEOPLE_MODEL, **model_args_for(...))`, which gives
       `strict_tools=False` on openai-api.
   - Config: `call_config(n)` = `settings.generate_config(...)` (effort low, no temperature
     or seed, `cache_prompt="auto"`, `max_retries=5`) with `cache=None` and `max_tokens`
     set to 512 for Haiku and 1024 for qwen.
   - Runner wiring:
     - `Step` gets an optional `exposure` and `verify`. `Plan` gets `aux_models`, which holds
       qwen and is listed in the plan and in the ledger `models`. `Ctx` gets `reuse_cache`.
     - The route-check entry is `Plan((HAIKU,), "route_check", "-", "-", "-",
       retry_on_error=0, aux_models=(qwen,))`, with `launch_route_check`, its own
       `route_check_exposure` and `verify_route_check`.
     - The path is the same as the other steps: local checks, `budget.guard`, plan print,
       `inspect_eval` into `logs/paid/route_check-<stamp>/`, then `record` in `finally`.
       After that comes `verify`.
     - The sample `cost_limit` defaults to \$0.05 (cap / 1 run / 1 attempt).
   - Tests:
     - `test_prefix_is_at_least_5k_local_tokens`, `test_prefix_is_fixed`
     - `test_route_check_texts_hold_no_banned_word` (substring match, stricter than word-start)
     - `test_call_config_is_the_harness_config_without_the_response_cache`
     - `test_mockllm_run_makes_exactly_three_calls_without_the_response_cache`
     - `test_real_anthropic_request_carries_output_config_effort_low` (checks the SDK kwargs
       and the logged `call.request`)
     - `test_route_check_is_built_with_one_attempt`
     - `test_route_check_runs_records_and_passes` (ledger line with 2 models, path under
       `route_check-`, actual = Σ `ModelUsage.total_cost` > 0, `retry_on_error` 0,
       `cost_limit` \$0.05)
     - `test_route_check_dry_run_prints_the_token_worst_case`
     - `test_route_check_refuses_a_worst_case_over_the_cap`
     - `test_route_check_refuses_over_the_stop_line`
     - Old tests updated, because `route_check` is now built:
       `test_runner_refuses_unbuilt_steps_without_network` and
       `test_dispatch_table_covers_every_step`.
2. **The response-cache rule.**
   - `response_cache(False)` returns `False`, which is passed as `generate(cache=...)`.
   - `--reuse-cache` gives `CachePolicy(expiry=1W, scopes={"route_check": "fixed-v1"})`.
     The flag works only with `--step route_check`; any other step is refused before the
     network.
   - Tests:
     - `test_response_cache_off_by_default_and_fixed_scope_on_reuse`
     - `test_check_fails_if_the_local_cache_was_used_without_reuse`
     - `test_reuse_cache_second_run_reads_all_three_from_the_local_cache`
     - `test_reuse_cache_partial_hit_fails`
     - `test_reuse_cache_only_for_route_check`
     - `test_reuse_cache_second_run_is_free_and_all_read`: two runner runs. The second makes
       0 provider calls, every event is `cache == "read"`, and its ledger `actual` is 0.
3. **The assertions.** `check_log(log, reuse_cache=...)` returns `Row`s. `table()` prints
   `PASS|FAIL  name  detail`.
   - Default rows:
     - `3 model calls logged` (events without an error)
     - `local response cache off` (all `cache` are None)
     - `call 1 and 2 share prefix and tool`
     - `call 2 cache_read > 0`
     - `call 1 request effort low` and `call 2 request effort low` (`call.request.output_config.effort`)
     - `qwen answered (non-empty text)`
   - With `--reuse-cache`:
     - If all 3 calls are `read`, the rows are `all 3 calls read from the local response
       cache` and qwen.
     - If none are `read` (the run that fills the cache), the rows are `local response cache
       written` plus every provider row.
     - A mix of read and not read fails.
   - On FAIL, `verify_route_check` raises `CheckFailed`. `main` prints `FAILED: route check
     FAILED (<rows>); route fallback needs a fresh owner OK (spec §7.2); no other route was
     tried` to stderr and exits 1. The ledger line is already written.
   - Tests:
     - `test_check_passes_on_a_good_route`
     - `test_check_fails_on_mockllm_no_effort_and_no_cache_read`
     - `test_check_fails_without_cache_read_on_call_2`
     - `test_check_fails_when_the_request_lost_effort`
     - `test_check_fails_on_empty_qwen_text`
     - `test_check_fails_when_a_call_is_missing`
     - `test_table_lists_every_row`
     - `test_route_check_fail_exits_nonzero_with_the_fallback_note` (one ledger line, one log
       dir, no key in the output)
4. **The smoke-estimate helper.**
   - Code: `src/temptation_bench/estimate.py`, plus `run.estimate_smoke_cli` behind
     `--estimate-smoke`. The flags are `--from-log`, `--turns`, `--mean-input`,
     `--mean-output` and `--hit-share`, and hand values override the log. `--step` is now
     needed only when `--estimate-smoke` is not given.
   - `measure_log`: reads the eval's main-model `ModelEvent`s (no error, not a cache read,
     with usage). I = mean of (new + cache read + cache write) tokens, O = mean
     `output_tokens`, h = Σ cache read / Σ input.
   - T is scaled by window last_day / the log variant's last_day (10/3 for G-free).
   - p_miss = max(p_in, p_cw), the DD's "p_in_or_cw", taken at the higher price. The plain
     p_in variant is printed too.
   - It makes no network call and writes no ledger line.
   - Tests:
     - `test_formula_by_hand`
     - `test_haiku_prices_come_from_pricing_yaml`
     - `test_measure_log_reads_turns_tokens_and_hit_share`
     - `test_smoke_turns_scale_to_the_window_days`
     - `test_cli_from_log_prints_the_arithmetic`
     - `test_cli_given_numbers_and_overrides`
     - `test_cli_needs_a_log_or_all_four_numbers`
     - `test_cli_refuses_a_hit_share_outside_0_1`
   - Run on the real G-free log (local file, \$0):
     ```
     measured: ...XBJh2WZoG3ztSaJuMfHbaq.eval (openai-api/xpl/gpt-6-luna): turns 11 over 3 days, I 4114, O 72, h 0.741; T scaled to the window days = 36.7
     per turn: 4114 x (0.741 x 0.01 + 0.259 x 0.125) + 72 x 0.5 = 200.0 $/1M = $0.000200
     per run:  36.7 x $0.000200 = $0.0073
     (with p_in in place of p_miss: $0.0064)
     smoke estimate: $0.0073 per run (Haiku, window; before the one rerun)
     ```
5. **The smoke step.** No code change was needed. The plan is Haiku, window, seed 1001, dose
   3_000_000, `retry_on_error` 1, and a sample cost limit of \$0.50 (exposure \$1.00 ≤ cap).
   - Tests:
     - `test_smoke_dry_run_plan_is_haiku_window_1001_30k_at_half_a_dollar` (every plan line)
     - `test_smoke_plan_sample_cost_limit_1_is_refused` (`--sample-cost-limit 1.00` gives
       exposure \$2.00 > \$1.00 cap, so it is REFUSED)
     - The existing `test_runner_reruns_failed_once_and_keeps_failure` is the mockllm e2e of
       the smoke (cost_limit 0.50).

Test output:
- Targeted: `uv run pytest -q tests/harness/test_route_check.py tests/test_run_route_check.py tests/test_estimate.py`: `37 passed`
- `uv run pytest -q tests/test_budget.py`: `88 passed`
- `uv run pytest -q`: `766 passed, 71 deselected in 153.66s`
- `uv run pytest -q -m slow`: `71 passed, 766 deselected in 232.99s`
- `uv run ruff check . && uv run ruff format --check .`: `All checks passed!`, `115 files already formatted`

## Worst-case exposure for the route check

From `configs/pricing.yaml` (spec §7.1), computed at run time by `route_check.worst_case()`:
- Haiku input per call: the local count is 8,360 (prefix 8,268 + question + tool JSON).
  Doubling it for the provider tokenizer gives 16,720 tokens, priced at the highest input
  price, \$0.125/M (cache write). That is \$0.002090. Output is 512 × \$0.50/M = \$0.000256.
  Each call is \$0.002346.
- qwen: 60 × \$0.03/M + 1024 × \$0.13/M = \$0.000135.
- 3 calls: 2 × 0.002346 + 0.000135 = \$0.004827. That times 6 attempts (1 + `max_retries` 5)
  is **\$0.0290**, which is under the \$0.05 cap. The plan line is: `exposure:
  $0.0290 (2 Haiku x (16720 in x $0.125/M + 512 out x $0.5/M) + 1 qwen x (60 in x $0.03/M +
  1024 out x $0.13/M), x 6 attempts)`.
- The sample `cost_limit` of \$0.05 is a second bound.
- Expected actual is about \$0.0015–0.002: one cache write of about 8.4k, one cache read, and
  small outputs. That is under the spec's < \$0.01.

## Commands for the controller (from `pilot-1/`)

1. **Route check (paid, about \$0.002):** `uv run python -m temptation_bench.run --step route_check --estimate 0.01`
   - Optional first, at \$0: add `--dry-run`. Expect `exposure: $0.0290 (...)`, `local
     cache: off`, `retry_on_error: 0`, `sample cost_limit: $0.0500`, and the models
     `anthropic/claude-haiku-5-5, openai-api/xpl/qwen3.7-flash (people)`.
   - Success: `recorded: route_check actual $0.00xx (logs)`, then a `route check:` table
     where every row is PASS, including `call 2 cache_read > 0 ... input_tokens_cache_read=<N>`
     and `call 1/2 request effort low ... 'low'`. Exit 0. One ledger line, with models
     Haiku + qwen.
   - Failure: the table shows FAIL rows, and stderr shows `FAILED: route check FAILED (...);
     route fallback needs a fresh owner OK (spec §7.2)`. Exit 1. Stop and ask the owner.
2. **`--reuse-cache` re-run:** `uv run python -m temptation_bench.run --step route_check --estimate 0.01 --reuse-cache`
   - **Note:** the plain route check writes nothing to the local cache (rule 2). So the
     **first** `--reuse-cache` run fills the cache. It is a paid run of about the same
     \$0.002, and its table shows `local response cache written` plus all the provider rows.
   - Run the same command **a second time**, a new process. Success: the table shows `PASS
     all 3 calls read from the local response cache  $0 re-run` and qwen PASS, and the
     ledger line has `actual $0.0000` (no usage in the log, balance unchanged).
3. **Smoke estimate (\$0):** `uv run python -m temptation_bench.run --estimate-smoke --from-log logs/paid/gfree-20261122T074444Z/2026-11-22T07-44-45-00-00_temptation-bench_XBJh2WZoG3ztSaJuMfHbaq.eval`
   - Expect about \$0.0073 per run. Any value can be overridden by hand, for example
     `--mean-input 15000` for a growing context.
   - Copy the printed arithmetic into PROGRESS.md.
4. **Smoke dry run (\$0, balance read only):** `uv run python -m temptation_bench.run --step smoke --estimate <X> --dry-run`
   - Expect: `models: anthropic/claude-haiku-5-5`, `variant: window (people=template)`,
     `seeds x doses: 1001 x 3000000 = 1 cells`, `retry_on_error: 1`, `sample cost_limit:
     $0.5000`, `token_limit: none`, `exposure: $1.0000 (1 runs x $0.5000 x 2 attempts)`.
   - `<X>` must cover one rerun, so use about 2× the estimate. For example `--estimate 0.05`
     leaves a margin for context growth.
5. **Smoke (paid):** the same command without `--dry-run`. Do **not** pass
   `--sample-cost-limit 1.00`: it is refused, because the exposure would be \$2.00 > \$1.00.
   - Success: `recorded: smoke actual $X (logs)` and an `.eval` under `logs/paid/smoke-<stamp>/`.
   - Then check the plan's step 4 items in the log.

## Concerns

- **The first `--reuse-cache` run is paid.** Rule 2 (no `CachePolicy` on the plain check)
  means there is nothing to reuse after it. Getting the "one free re-run" costs one extra
  paid route check of about \$0.002, and that extra run is also a full second provider check.
  Total route-check spend is about \$0.004–0.006.
- **`max_tokens` 512 with adaptive thinking:** Haiku might spend its output on thinking and
  return only a short text or a tool call. That is fine, because no row checks Haiku's text.
  If the gateway refused a small `max_tokens` with thinking, the run would FAIL with exit 1,
  and the controller would rule on it. The fix would be a bigger `HAIKU_MAX_TOKENS`, not a
  new route.
- **qwen at 1024 tokens with effort low:** if qwen is a reasoning model and spends all 1024
  tokens on reasoning, the text could be empty and the row would FAIL falsely. If that
  happens, raise `PEOPLE_MAX_TOKENS` (the cost is tiny).
- **Retries:** a retried provider attempt could add a `ModelEvent`. The check counts only
  events without an error, but a successful retry that logs two events would make the count
  ≠ 3 and FAIL. That is safe (fail closed), but it would mean a rerun by hand.
- **Fake-client tests** need the opt-in `allow_fake_client` fixture (`tests/conftest.py`). It
  lets `verify_model_apis` pass only for a model whose SDK `messages.create` is marked
  `fake_client`. Every other model still refuses under `INSPECT_DISABLE_MODEL_API`.
- **The smoke estimate's I comes from a 3-day G-free run** with a smaller context. Over 10
  days the context grows toward the trim threshold (30k), so the real I may be 2–4× higher.
  The estimate is a floor, and the cost limit (\$0.50) is the real bound.
- **G-free was Luna on openai-api,** so its h and O come from another model and tokenizer.
  Label them as assumptions in PROGRESS.md.
- The engine is untouched (no engine file changed), so the golden is unchanged.
  `budget/ledger.jsonl` was not touched.

## Fix: block_binding

**Cause.** In Inspect 0.3.291, `anthropic.py` `apply_thinking_block_binding` (`:1743-1796`) runs
for Haiku 5.5 on the first-party route. It adds the beta `thinking-binding-controls-2026-08-01`
and `thinking.block_binding = {"prefix_mismatch_behavior": "drop_block"}`. The gateway's
Anthropic-style route rejects that field with a 400.

**Verified in the installed source, and why the fix differs from the ruling's literal form:**
- `GenerateConfig.extra_body` does **not** reach the request for this field. `completion_config`
  copies only `metadata` and `service_tier` (`anthropic_extra_body_fields`, `:6320`) and
  `context_management` from it (`:1626-1633`).
- Test `test_config_extra_body_alone_does_not_drop_block_binding` proves this. With only
  `GenerateConfig(extra_body={"thinking": ...})`, the wire body still has `block_binding`.
- The docstring's "caller-supplied `extra_body.thinking`" means the provider's
  **`extra_body` model arg**:
  - The provider reads it with `self.extra_body = collect_model_arg(EXTRA_BODY)` (`:502`).
  - It is merged into `request["extra_body"]` (`:1031-1032`).
  - The Anthropic SDK then shallow-merges `extra_body` over the JSON body. So the sent
    `thinking` is exactly `{"type": "adaptive"}`, and `output_config` is untouched.
- So the fix is on the route seam: `harness/routes.py` `model_args_for("anthropic/...")` now
  returns `{"extra_body": {"thinking": {"type": "adaptive"}}}`. This is the same seam as the
  Task 29 strict-tools fix.
  - `run.launch_task_eval` (smoke and later steps) and `run.launch_route_check` already pass
    `model_args_for(model)` to `inspect_eval`.
  - openai-api routes are unchanged: `{"strict_tools": False}`.
- `reasoning_history="none"`: `settings.generate_config` sets it for `anthropic/` models only,
  and leaves it None for Luna, qwen and mockllm. The route-check solver uses the same function
  (`call_config(model, max_tokens)` → `generate_config(model, ...)`).
  - **Caveat:** `AnthropicAPI.force_reasoning_history()` returns `"all"` (`:2179`), and
    `_model.py` `resolve_reasoning_history` (`:3087-3089`) lets that override the config. So
    Inspect records "none" but still replays thinking blocks on this route.
  - Test `test_inspect_anthropic_provider_forces_reasoning_history_all` is a tripwire for this.
    See the concerns below.
- `harness.json` `provider_settings` now records:
  - `reasoning_history` ("none" for Haiku, "not set (provider default)" otherwise)
  - `model_args` (the route args only: `{"extra_body": {"thinking": {"type": "adaptive"}}}` for
    Haiku, `{"strict_tools": false}` for openai-api; never a key or URL)

**Wire body of a route-check Haiku call.** Captured at the SDK's httpx `send`; keys and shapes
only, with the fixed values shown for `thinking`, `output_config` and `cache_control`:
```
anthropic-beta: interleaved-thinking-2025-05-14,thinking-binding-controls-2026-08-01
{ max_tokens, messages[{role, content}], model, stream,
  cache_control: {"type": "ephemeral"},
  output_config: {"effort": "low"},
  thinking: {"type": "adaptive"},                      # no block_binding, no display
  system[{type, text, cache_control{type}}],
  tool_choice{type},
  tools[{name, description, input_schema{type, properties{section{type, description}}, required, additionalProperties}, cache_control{type}}] }
```
- There is no `temperature`, `seed` or `block_binding`.
- `ModelEvent.call.request` logs the pre-merge dict. It holds the top-level `thinking`, which
  still has `block_binding`, plus `extra_body.thinking`. The route-check rows therefore read
  `effective_request(req)`: `extra_body` shallow-merged over the rest, as the SDK does.

**Tests.** RED: collection failed (`ANTHROPIC_THINKING` did not exist yet). Then GREEN.
- `tests/harness/test_block_binding.py`. The wire body is captured by replacing the SDK
  client's httpx `send`, which records the body and raises, so there is no network.
  - `test_anthropic_route_wire_body_has_no_block_binding_and_keeps_effort_low`
  - `test_without_the_fix_inspect_sends_block_binding`
  - `test_config_extra_body_alone_does_not_drop_block_binding`
  - `test_model_args_per_route`
  - `test_reasoning_history_none_for_haiku_only` (Haiku "none"; Luna, qwen and mockllm None)
  - `test_inspect_anthropic_provider_forces_reasoning_history_all`
  - `test_runner_passes_the_thinking_override_on_the_anthropic_route` (smoke and route_check get
    the override, gfree gets strict_tools)
  - `test_harness_json_records_the_override_and_reasoning_history`
- `tests/harness/test_route_check.py`:
  - `fake_haiku` is now built with `model_args_for(HAIKU)`, as the runner builds it.
  - The SDK kwargs test now also checks `extra_body.thinking == {"type": "adaptive"}`.
  - New: `test_check_fails_when_block_binding_would_be_sent` (new row `call N thinking has no
    block_binding`), `test_effort_row_reads_the_merged_request` and `test_call_config_per_route`.
- `tests/harness/test_strict_tools.py`: the Anthropic-route test was renamed to
  `test_runner_anthropic_route_gets_only_the_thinking_override` and now expects the override.

**Route-check table after the fix.** It gains two rows: `call 1 thinking has no block_binding`
and `call 2 thinking has no block_binding`. The effort rows read the merged request.

**Concerns (fix).**
- `reasoning_history="none"` is not applied by Inspect on the Anthropic route (it forces
  "all"). Thinking blocks are still replayed, and without `drop_block` a history trim that
  changes the prefix before a replayed thinking block could get a 400 in the smoke.
  - To really stop the replay, the agent loop would have to strip `ContentReasoning` from
    assistant messages before each generate. That is a harness change for the controller to
    rule on.
- The beta header `thinking-binding-controls-2026-08-01` is still sent. The gateway's 400 named
  only the body field. If the gateway also rejects the header, the route check will show it.
- `display: "summarized"` is gone from `thinking`. The sent `thinking` is exactly
  `{"type": "adaptive"}`, so summaries are no longer requested. Nothing here reads them.

## Fix: reasoning strip

- What changed:
  - The ruling's `reasoning_history="none"` did nothing. Inspect's Anthropic provider forces "all" (`force_reasoning_history`).
  - Instead, `harness/routes.py` gets a new `strip_old_reasoning(messages, model)`.
  - On the Anthropic route only, it returns a new list. Every assistant message except the most recent one is a `model_copy` without its `ContentReasoning`. The copy keeps the same id, text and tool calls.
  - The most recent assistant message is passed as is, so its thinking block and signature are replayed unchanged. A tool_use continuation needs that.
  - Other routes (Luna, qwen, mockllm) get the same list back.
- Where it runs (`harness/agent.py` `_generate`):
  - The order is `compact_input`, then `strip_old_reasoning`, then `window.update(sent)`, then `generate(sent)`, then `record_output(sent)`.
  - `state.messages` is never edited, so the transcript and replay keep every block. `WindowTracker` sees exactly the list that was sent. The message ids are unchanged, so compaction's baseline ids still match.
- Removed:
  - `reasoning_history_for`, and the `reasoning_history` arg in `generate_config`.
  - The harness.json key `reasoning_history` and its tests.
  - harness.json now records `provider_settings.reasoning`. It is "reasoning stripped from all but the last assistant message, Anthropic route" for Anthropic, and "not set (provider default)" for every other route.
- Tests:
  - New file `tests/harness/test_reasoning_strip.py` with 6 tests:
    - A scripted run of 3 assistant turns keeps reasoning only on turn 3, with its signature kept.
    - The stored list is not mutated.
    - Other routes get the list unchanged.
    - Plain-text content is handled.
    - In the loop, after a scripted trim, generate and `window.update` get the same stripped list.
    - The mockllm route sends the list unchanged.
  - The Inspect "all" tripwire stays as the reason for the fix. `generate_config` sets no `reasoning_history`.
  - The replay and in_window tests still pass.
- Concern: Anthropic prompt caching. When a new assistant turn arrives, the previous turn loses its thinking. That changes the prefix at that point, so the cache hit share h may drop compared with the G-free estimate. Check `cache_read` in the smoke log.
