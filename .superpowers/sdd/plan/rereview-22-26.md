# Re-review: batch [22–26], fix wave round 1 (+1b)

- Range: 4fa936a..d4086ef (8 commits). Diff read once from `review-4fa936a..d4086ef.diff`. Paths are relative to `pilot-1/`, and line numbers are at d4086ef.
- Inspect facts come from the installed 0.3.291 source in `.venv/lib/python3.13/site-packages/inspect_ai/`.
- Check run: `uv run --offline pytest -q tests/test_model_api_guard.py tests/harness/test_local_count.py` → `6 passed in 3.65s`. Nothing else was run. No network calls. `.env` and `key.txt` were not read.

### Finding Verdicts

- **R22-1: compaction makes provider `count_tokens` calls on the Haiku route.** ADDRESSED.
  - `harness/agent.py:201` passes `compaction(..., model=LocalCountModel(get_model()))`.
  - `harness/counting.py:35-50` overrides `count_tokens` with Inspect's local tiktoken helper (`_tokens.py:42,108,123`) and has no network path.
  - Every count in the compaction path goes through `target_model.count_tokens` or `count_tool_tokens`: `_compaction/_compaction.py:180,182,209,216,290,421,434`. Base `Model.count_tool_tokens` (`_model.py:1507`) calls `self.count_tokens`, so it resolves to the override.
  - `get_model(Model)` returns the instance unmodified (`_model.py:2885-2886`). `CompactionTrim` (`_compaction/trim.py`) never uses the model. The baseline after the first generate comes from the generate's own usage (`record_output_fn`), not from an extra call.
  - The tests prove it. `test_compacted_run_makes_no_model_count_tokens_call` patches base `Model.count_tokens` to raise, so a revert to the default target fails the e2e. (AssertionError is not caught by `_generate`'s `except RuntimeError`.) `test_local_count_never_calls_the_anthropic_count_api` shows the spy fires on the plain Haiku model and not on the wrapper.
  - Remaining gap: no e2e runs compaction with an Anthropic-identity target. Reading the code closes it.
- **R25-1: tests can reach the real gateway.** ADDRESSED.
  - `tests/conftest.py:13-14` sets `INSPECT_DISABLE_MODEL_API=1` at conftest import. That happens before any test module is imported, so it precedes every `inspect_ai.eval` and its `init_dotenv`. There is no root `conftest.py`, no inspect pytest11 plugin and no `[tool.pytest]` `-p`.
  - The autouse fixture `no_model_apis` (`conftest.py:17-19`) sets it again for every test.
  - Inspect reads the switch with `os.getenv` at every generate (`_model.py:2315-2320`, called at `:1853`).
  - `init_dotenv` (`_util/dotenv.py:15-26`) uses `load_dotenv` with override only under VS Code. Even then it overrides only keys that `.env` contains, and `.env` would not contain the switch.
  - `tests/test_model_api_guard.py` asserts that the switch is on and that a non-mockllm generate refuses.
  - Residual (out of scope, below): the switch does not gate `count_tokens`.
- **R25-2: run-time worst case never checked against the hard budget.** ADDRESSED.
  - `run.py:236-264` (`check_exposure`) runs in `run_step` (`:331-332`) before `budget.guard`. The rule is runs × sample cost limit × attempts against the step cap and against spent + exposure ≤ STOP_LINE.
  - **Missing cost limit:** `sample_cost_limit` is always defaulted (`:318-319`) and must be finite and > 0 (`:320-321`). `None` → "unknown" refuses (`:250-252`).
  - **Missing ledger:** `budget.spent` raises (`budget.py:128-129`) before any network call.
  - **Retries:** `attempts = 1 + plan.retry_on_error` (`run.py:76-79`). The same `p.retry_on_error` reaches Inspect (`:538`). Inspect reads 0 as 0 (`_eval/task/run.py:1861`).
  - **Multi-sample steps:** `plan.runs` = models × seeds × doses, and epochs are not used.
  - **G-free at 800k:** still possible. With `retry_on_error=0` and step default `token_limit=800_000` (`run.py:566-576`), the check is 800k ≤ 1M. Covered by `test_gfree_exposure_is_counted_in_free_tier_tokens`, `test_gfree_cli_token_limit_800k_passes_and_1200k_refused` and `test_gfree_launches_without_retry_and_smoke_with_one`.
  - **Smoke:** 1 × \$0.50 × 2 = \$1.00, which fits the cap.
  - Small residual margins are listed under New Breakage (Minor).
- **R25-5: default token limit from the smoke.** ADDRESSED.
  - `run.py:203-212` (`default_token_limit`) uses 2 × `total_tokens` / `runs` from the latest valid smoke line. Old lines are skipped.
  - Precedence (`:323-329`): flag, then step default, then smoke, then none. The source is printed.
  - Tests: `test_default_token_limit_from_smoke`, `test_runner_defaults_the_token_limit_after_a_smoke` and `test_record_keeps_token_totals_for_the_default`.
  - The brief says "input + output". `total_tokens` also counts cache tokens. That gives a larger limit, which is the safe side, and it is the quantity Inspect meters.
- **R26-1: pregen ignores global model settings.** ADDRESSED.
  - `harness/pregen_people.py:115-119` builds `GenerateConfig(reasoning_effort, max_retries)` from window `[harness]` and passes it at `:126`.
  - `test_pregen_uses_the_global_model_settings` reads the settings back from each `ModelEvent`.
- **X-1: two models in one eval collide.** ADDRESSED (per ruling: refuse more than one model).
  - `run.py:113-123` (`one_model`) is used in `launch_task_eval` (`:525`), so the refusal is structural.
  - `run_step` also calls it first (`:316`), before the guard, the network or a ledger line.
  - Tests: `test_launch_refuses_more_than_one_model` and `test_runner_refuses_a_two_model_step_before_any_call`.
- **R24-1: cell scope must include people and variant.** ADDRESSED.
  - `harness/settings.py:27` is `"{model}|{seed}|{dose}|{people}|{variant}"`. `people` and `variant` are required keyword arguments (`:43-53`).
  - `agent.py:184` passes `st.people` and `config.variant`.
  - Every caller was updated: `agent.py:163,184`, `settings.py:99`. A grep of `src/` found no other caller.
  - Tests: `test_cache_scope_differs_by_people`, `test_cache_scope_differs_by_variant` and `test_cell_scope_needs_people_and_variant`.
- **R24-2: `harness.json` lacks the people backend.** ADDRESSED.
  - `settings.py:115` writes `"people"`. `agent.py:185` passes it.
  - Tests: `test_harness_json_records_temperature_not_set_and_retries` and `test_harness_json_records_a_prose_backend`.
- (R25-3, G-free default token limit) is also closed by `Plan.token_limit` = 800k.

**Secrets:** nothing new in the diff can carry the key.
- The new refusal texts contain only numbers and step names. They go through `budget.redact` in `main` (`run.py:447,450`).
- The ledger `error` is redacted (`budget.py:310`).
- `harness.json` gains only the `people` string.
- `LocalCountModel` is never serialized. Only its role appears, in the CompactionEvent.
- The new tests use the non-key string `fake-not-a-key` and an `.invalid` base URL, passed as arguments, never through the environment.

### New Breakage in the Fix Diff

Critical: none. Important: none.

Minor:
1. `run.py:241-249`: the free-tier branch returns before any dollar check. G-free still passes a \$1 `cost_limit` per sample, and that is never compared with STOP_LINE. If the free tier does not apply (for example the gateway bills Luna), up to \$1 can be spent unchecked. Low risk at Task 29, when spent ≈ \$0. A cheap guard would also refuse when `spent + runs × limit × attempts > STOP_LINE`.
2. `run.py:225-231`: exposure treats `cost_limit` as a hard ceiling. Inspect checks the limit after each call, so each attempt can overshoot by one generate (the probe included). On the smoke, the possible overshoot over the \$1.00 cap is a few cents.
3. `run.py:326-329`: the smoke-based default token limit applies to every non-G-free step, including the future `full_run` (600-turn cap, longer horizon). 2 × a window-variant smoke would probably truncate full runs. In the same vein, the default `mini_batch` limit (2 × smoke × 12 runs × 2 attempts) will usually exceed the \$5 cap and refuse. Both fail closed for money. Task 31/33 must decide them (for example a per-variant default, and an explicit `--sample-cost-limit`).
4. The design-value table in `PROGRESS.md` §8 records the smoke change (\$1 → \$0.50). It does not record G-free `retry_on_error` 1 → 0 (DD §13A says one rerun). That ruling exists only in the SDD ledger.
5. `harness/counting.py`: on the Haiku route, compaction now depends on tiktoken's `o200k_base` file, cached in `$TMPDIR/data-gym-cache` (present now; `TIKTOKEN_CACHE_DIR` unset). If the cache is cleared, the first count downloads the file. That is a network call, unkeyed and free. Offline, it fails as a sample error. Consider pinning `TIKTOKEN_CACHE_DIR` to a durable path.
6. `run.py:357-358`: with a `model=` override on a multi-model plan, `runs` in the ledger stays `plan.runs` (the multi-model count), so the per-run smoke cost would be understated. This is reachable only from tests and overrides, because every real plan has one model.

### Out-of-Scope Observations

1. `INSPECT_DISABLE_MODEL_API` does not gate `Model.count_tokens` (`_model.py:1379-1484`; the fixer noted this). A future test that builds a real-provider model with no explicit `api_key` and `base_url`, after `inspect_ai.eval` has loaded `pilot-1/.env`, could still send one count request with the real key. No such test exists. A conftest-level patch of `AnthropicAPI.count_tokens` would close it.
2. `cost_limit` makes Inspect require pricing data for every model (`model/_util.py:67-97`, `PrerequisiteError`). If the gateway slugs `anthropic/claude-haiku-5-5` or `openai-api/xpl/gpt-6-luna` have no cost data, the eval fails at start. `record` would then charge the step cap to the ledger as `actual`: \$1 for the smoke, \$0 for G-free. Check this in a dry run, or with `set_model_cost`, before Task 29/30.
3. The open Minors from the review are still untouched, as the fixer stated: R22-2, R23-1, R23-2, R25-4, R26-2, R26-3, R26-4 and the X-2 retry-cache nuance.

### Verdict

**Fix round:** All findings addressed (R22-1, R25-1, R25-2, R25-5, R26-1, X-1, R24-1, R24-2), with no new Critical or Important breakage. There are 6 Minor items in the diff and 3 out-of-scope notes.
