# Task 31 pre-work report (S5): people model swap, pregen + mini-batch launch, attempt errors

No network calls were made. Every runner test uses a fake `.env`, `httpx.MockTransport` for
the balance, and mockllm or a fake `inspect_eval`. The dry runs below were captured the
same way, against a scratch copy of the real ledger. The real `budget/ledger.jsonl` is
unchanged and was not staged. `.env` was never read. No engine file changed, and the golden
hash test passes.

## Inspect facts verified (installed `inspect-ai==0.3.291`, `pilot-1/.venv/lib/python3.13/site-packages/inspect_ai/`)

- **`reasoning_effort` is sent for any model on openai-api.** `model/_openai.py`
  `openai_completion_params` (`:594-627`) adds `params["reasoning_effort"]` whenever
  `config.reasoning_effort is not None`, with no model check.
  `model/_providers/openai_compatible.py` `completion_params` (`:489-499`) calls it
  unchanged. `uses_responses_api` is `bool(self.responses_api)` (`:240-242`), so
  `openai-api/xpl/...` uses chat completions.
  - So the people config is built without `reasoning_effort`.
  - Tripwire test: `test_inspect_openai_api_sends_reasoning_effort_for_any_model`.
- **Local response cache.** `generate(cache=False)` turns it off (Task 30 facts,
  `model/_model.py`). The cache root is `$INSPECT_CACHE_DIR/generate`, or else the user
  cache dir (`model/_cache.py` `_cache_root`, `:478-484`).
- **`eval_retry` exists** (`_eval/eval.py:1356`, CLI `inspect eval-retry`). It reruns the
  failed samples of a log. It does not go through `run.py`, so it has no guard and writes no
  ledger line.
- **Model roles.** `eval(model_roles={"people": <str|Model>})` (Task 26 facts). The pregen
  solver resolves the role inside the solver with `required=True`, and its
  `non_strict_tools` handles a role given as a string.
- **`EvalSample.error_retries`** holds the error of each failed attempt that
  `retry_on_error` reran, oldest first (Task 25 test; read here in `analysis/load.py`).

## Items and covering tests

RED was seen for every item first:
- the new test modules failed to import or collect, or failed on "not built";
- the report tests failed: the table was missing, a re-run was labelled "re-run", and dedupe
  kept the errored copy.

Then GREEN.

1. **People model swap.**
   - `harness/routes.py` `PEOPLE_MODEL = "openai-api/xpl/mistral-small-3.2-24b-instruct"`,
     with a comment that the spec named qwen and why it changed (PROGRESS §8).
     `run.PEOPLE` is the same value. The route check uses `routes.PEOPLE_MODEL`.
     `strict_tools=False` is kept through `model_args_for`.
   - New `routes.NON_REASONING` and `routes.route_config(slug, config)`. It returns a copy
     without `reasoning_effort` for the people model and leaves every other route unchanged.
     Both people configs use it:
     - `pregen_people.rewrite_config(model)`: effort from `[harness]`, `max_retries` 5,
       `max_tokens` = `PREGEN_MAX_TOKENS` (200), then `route_config`;
     - `route_check.call_config(model, n)`.
   - `configs/pricing.yaml`: the mistral prices are input 0.094, output 0.25, cache write
     0.0 and cache read 0.01. The qwen entry stays, with a comment, because older ledger
     lines name it.
   - Tests: `tests/harness/test_people_model.py`
     - `test_people_model_is_mistral_small_everywhere`
     - `test_people_price_is_registered_in_the_existing_format`
     - `test_inspect_openai_api_sends_reasoning_effort_for_any_model`
     - `test_route_config_drops_reasoning_effort_for_the_people_model_only`
     - `test_people_request_body_has_no_reasoning_effort` (the provider's real
       `completion_params` for both people configs; Haiku keeps `low`)
     - `test_pregen_config_is_small_and_has_no_local_cache`
     - `test_route_check_worst_case_prices_the_people_model`
   - Updated tests that named qwen:
     - `test_run_route_check.py::test_route_check_is_built_with_one_attempt`
     - `test_route_check.py`: the worst-case text, and the row
       `people model answered (non-empty text)` (was `qwen answered`), plus
       `test_check_fails_on_empty_people_text`
     - `test_pricing.py`, `test_strict_tools.py`, `test_reasoning_strip.py`
2. **Pregen launcher** (`run.py --step pregen`, cap \$0.05).
   - Plan: `Plan((PEOPLE,), "pregen", "1001,1002,1003", ..., max_samples=2,
     retry_on_error=0, samples=39, uses_token_limit=False)`.
   - `launch_pregen` runs the Task 26 `pregen_people` task with the people model as both
     the eval's model and the `people` role, with the route's `model_args`.
   - `exposure` is `pregen_people.worst_case`. `verify_pregen` prints the ok / rejected /
     missing counts per seed file; a missing file exits 1.
   - It takes the same path as every step: local checks, `budget.guard`, the plan print,
     the eval, then `record` in `finally`, then verify.
   - The solver calls `generate(..., cache=False)`. The task now calls
     `register_prices()`, which Inspect's `cost_limit` needs.
   - The docstring (run.py and pregen_people.py) says pregen covers the D1-D10 exogenous
     texts only. That is enough for window mode; full_run needs a longer pregen.
   - Tests in `tests/test_run_task31.py`:
     - `test_pregen_is_built_for_three_seeds_with_the_people_model`
     - `test_pregen_worst_case_fits_its_cap`
     - `test_pregen_dry_run_prints_the_plan_and_launches_nothing`
     - `test_pregen_launch_sets_the_people_role_and_no_rerun`
     - `test_pregen_refuses_over_its_cap`
     - `test_pregen_mockllm_writes_three_seed_files_and_records`: real mockllm eval, 39
       samples, 3 files, every `ModelEvent.cache is None`, ledger `runs` 39
     - `test_pregen_verify_fails_when_a_seed_file_is_missing`
3. **Route-check people row.**
   - The worst case now prices mistral (\$0.0297). The table row is renamed, and the people
     call carries no `reasoning_effort`.
   - Tests: `test_route_check_worst_case_prices_the_people_model` and
     `test_people_request_body_has_no_reasoning_effort`. All Task 30 route-check tests pass.
4. **Mini-batch launch.**
   - Shape: one `--step mini_batch` runs Haiku, then Luna, as two evals (`Step.split_models`).
     `--model <slug>` runs just one of them.
   - Each eval has its own guard call and its own ledger line, with `models` [that model]
     and `runs` 6. Logs go to `logs/paid/mini_batch-<stamp>/<model tag>/`.
   - The worst case of all evals to run is checked up front: runs × limit × 2, plus the
     earlier mini_batch spend from the ledger (new `step_spent`), must fit the cap and the
     stop line. Before Luna it is checked again with what Haiku spent.
   - An eval that raises stops the step. Each line's `estimate` is the step estimate's
     share by runs.
   - people=prose refuses locally, with no network, until the pregen files exist
     (`check_prose`).
   - This also fixes rr-6: every eval records its own run count, including under a model
     override.
   - Luna pricing was already registered (\$0.10 / \$0.50, cache read = full input).
   - Tests in `tests/test_run_task31.py`:
     - `test_mini_batch_plan_is_two_models_window_prose_three_seeds_two_doses`
     - `test_luna_is_priced`
     - `test_mini_batch_cost_limit_is_twice_the_smoke_actual` (also checks the token limit
       is 868,576)
     - `test_mini_batch_dry_run_prints_both_evals`
     - `test_mini_batch_runs_one_eval_per_model_and_records_each`
     - `test_mini_batch_model_selector_runs_only_that_eval`
     - `test_model_selector_refuses_an_unknown_model_or_step`
     - `test_mini_batch_refuses_a_worst_case_over_the_cap`
     - `test_mini_batch_refuses_over_the_stop_line`
     - `test_mini_batch_counts_earlier_mini_batch_spend_against_its_cap`
     - `test_mini_batch_refuses_without_the_prose_files`
     - `test_mini_batch_stops_after_an_eval_that_raises`
     - slow: `test_mini_batch_mockllm_two_evals_ledger_runs_per_eval` (2 real mockllm evals
       of 6 prose window samples; ledger runs [6, 6]; one log dir per eval)
   - Updated: `test_budget.py` `test_runner_refuses_unbuilt_steps_without_network` (now
     full_run only) and `test_dispatch_table_covers_every_step`.
   - Token limit: the default 2 × smoke mean (868,576) is sane for window runs.
     - The smoke used 434,288 tokens over 31 turns (mean input 13.7k, h 0.889).
     - Luna, from G-free: 11 turns over 3 days scales to about 37 turns, which is about
       370-520k tokens.
     - No per-variant default was added. **Note for full_run (Task 34):** about 3× the turns
       means about 1.3M tokens, which is over 868k. full_run needs its own `token_limit`
       (`Plan.token_limit` or `--token-limit`).
5. **Attempt errors in the report.**
   - `analysis/load.py`:
     - each `.eval` run gets `meta["attempt_errors"]` (the `error_retries` texts);
     - `_dedupe` now keeps the labelled copy **without a sample error** over an errored one.
       Before, an errored but sealed and labelled copy that came first stayed in n, and the
       clean re-run was moved to replays.
   - `analysis/report.py`:
     - a new table "Every failed attempt, with its error text: N" (run, attempt, error). It
       covers automatic-rerun attempts, errored samples, labelled runs with an error, and
       errored copies of a re-run cell;
     - the replays row kind is now `errored attempt: <error>` for an errored copy, never
       "re-run".
   - Tests: `tests/analysis/test_report_attempt_errors.py`. Its fixture is a real batch:
     eval A, where the cell errors with no rerun, then eval B, the same cell, which fails
     once and then succeeds on the automatic rerun.
     - `test_fixture_has_an_errored_sample_and_a_retried_rerun`
     - `test_every_failed_attempt_is_listed_with_its_error_text` (both texts; count 2)
     - `test_errored_copy_is_not_called_a_re_run`
     - `test_the_cell_counts_once_in_n` (the kept run is the clean one; the errored one is
       in replays)
   - All Task 27-28 report tests still pass.
6. **Runbook** (run.py docstring, "Runbook: rerunning a deterministic harness error").
   Nothing new was built. What exists:
   - `retry_on_error=1` and the per-cell cache. A rerun replays the cached outputs, so a
     deterministic error recurs, and the replayed turns cost \$0.
   - The procedure: fix the harness with a mockllm repro, then rerun through the runner
     (`--model` for one mini_batch eval). Cached turns are free up to the changed input.
   - `|retry<k>` exists in `settings.cell_scope` / `generate_config`, but **nothing wires
     it**: `harness/agent.py:187` never passes `retry`. Using it needs an approved code
     change.
   - A fresh empty `INSPECT_CACHE_DIR` for the rerun process drops every cached output, so
     the whole eval is paid.
   - `eval_retry` must not be used for paid reruns: it bypasses the guard and the ledger,
     and keeps the same scope, so it would replay into the same error.

Final checks:
- `uv run pytest -q`: 813 passed, 72 deselected
- `uv run pytest -q -m slow`: 72 passed, 813 deselected
- `uv run ruff check . && uv run ruff format --check .`: clean

## Exposure arithmetic

- **Pregen** (from `pregen_people.worst_case`):
  - 39 samples (13 + 16 + 10).
  - Input: 2 × the longest prompt's local tokens (75) = 150 at \$0.094/M, the highest
    mistral input price.
  - Output: 200 max at \$0.25/M.
  - Total: 39 × (150 × 0.094 + 200 × 0.25)/1e6 × 6 attempts (1 + `max_retries` 5) =
    **\$0.0150** ≤ \$0.05.
  - Per-sample `cost_limit` = \$0.05 / (39 × 1) = \$0.0013.
  - Expected actual is about \$0.001.
- **Route check:** 2 Haiku × (16,720 in × \$0.125/M + 512 out × \$0.5/M) + 1 people ×
  (60 × \$0.094/M + 1,024 × \$0.25/M), × 6 attempts = **\$0.0297** ≤ \$0.05. The expected
  actual is about \$0.002.
- **Mini-batch:**
  - Per-sample `cost_limit` = 2 × \$0.014449245 = **\$0.0289**.
  - Each eval: 6 runs × \$0.0289 × 2 attempts = **\$0.3468**.
  - Both evals: 12 × \$0.0289 × 2 = **\$0.6936** ≤ \$5.00.
  - Spent \$0.0198 + 0.6936 = \$0.71, under \$9.50.
  - Expected actual: Haiku about 6 × \$0.0144 = \$0.09. Luna is up to 6 × \$0.0289 =
    \$0.17, bounded by the cost limit (see the concerns).

## Controller commands (from `pilot-1/`)

1. **Route check rerun (about \$0.002):**
   ```
   uv run python -m temptation_bench.run --step route_check --estimate 0.01 --dry-run
   uv run python -m temptation_bench.run --step route_check --estimate 0.01
   ```
   - Dry-run success: `models: anthropic/claude-haiku-5-5,
     openai-api/xpl/mistral-small-3.2-24b-instruct (people)`, `exposure: $0.0297 (...)`,
     `local cache: off`.
   - Real run success: `recorded: route_check ...`, every row PASS, including `PASS
     people model answered (non-empty text)`. Exit 0.
   - A FAIL exits 1 with the §7.2 fallback note.
2. **Pregen (cap \$0.05):**
   ```
   uv run python -m temptation_bench.run --step pregen --estimate 0.01 --dry-run
   uv run python -m temptation_bench.run --step pregen --estimate 0.01
   ```
   - Dry-run success: `samples: 39 (D1-D10 exogenous texts of seeds 1001,1002,1003; window
     mode only)`, `exposure: $0.0150 (39 samples x (150 in x $0.094/M + 200 out x $0.25/M)
     x 6 attempts)`, `sample cost_limit: $0.0013`, `local cache: off`, and `writes:
     .../configs/people_prose/seed_<n>.json`.
   - Real run success: `recorded: pregen openai-api/xpl/mistral-small-3.2-24b-instruct
     actual $0.00xx`, then three `pregen: seed_100N.json: K texts, a ok, b rejected, c
     missing` lines. Exit 0.
   - Then read all three JSON files by hand (plan step 1). For any odd text, delete its key
     so the template is used. Commit the JSON.
3. **Mini-batch (cap \$5.00):**
   ```
   uv run python -m temptation_bench.run --step mini_batch --estimate 0.70 --dry-run
   uv run python -m temptation_bench.run --step mini_batch --estimate 0.70
   ```
   - The estimate must cover one rerun. 0.70 is about the full worst case; the ledger
     splits it 0.35 / 0.35.
   - Dry-run success: `step mini_batch: 2 evals`, `exposure: $0.6936 (12 runs x $0.0289 x 2
     attempts)`, then `eval 1 of 2: anthropic/claude-haiku-5-5` and `eval 2 of 2:
     openai-api/xpl/gpt-6-luna`. Each eval shows `window (people=prose)`, `1001,1002,1003 x
     0,3000000 = 6 cells`, `max_samples: 2`, `retry_on_error: 1`, `sample cost_limit:
     $0.0289` and `token_limit: 868576 (2 x smoke mean)`.
   - It is `REFUSED: people=prose needs the pregen file ...` until step 2 is done.
   - Real run success: two `recorded: mini_batch <model> ...` lines, and two ledger lines
     with `runs: 6` each. The logs are in `logs/paid/mini_batch-<stamp>/{claude-haiku-5-5,
     gpt-6-luna}/`.
   - One model only (for example a rerun, or Luna with its own limit):
     `uv run python -m temptation_bench.run --step mini_batch --model openai-api/xpl/gpt-6-luna
     --estimate X [--sample-cost-limit Y]`.
4. **Bots and the report (\$0, local):**
   ```
   uv run python -c "from pathlib import Path; from temptation_bench.bots import BOTS, run_bot; from temptation_bench.engine.config import load_config; c=load_config('window'); [run_bot(b, c, s, d, Path('scratch/bots-mini-batch')) for b in BOTS for s in (1001,1002,1003) for d in (0,3000000)]"
   uv run python -c "from pathlib import Path; from temptation_bench.analysis.report import build_report; print(build_report(Path('logs/paid/mini_batch-<stamp>'), Path('scratch/bots-mini-batch')))"
   ```
   - The report goes to `results/mini_batch-<stamp>/report.md`, named after the batch dir.
     Rename it to `results/mini-batch/` if the plan's path is wanted.
   - Success:
     - 12 runs, n = 3 per arm for each model × dose;
     - "Every failed attempt ... : N" with every error text;
     - the spend section shows the ledger total;
     - the figures are in `figures/`.
   - Then fill in the hand-check table (plan step 4).

## Concerns

- **Luna's cost limit will probably cut its runs short.**
  - The ruling's limit (2 × the Haiku smoke = \$0.0289) comes from a cached Haiku run: 434k
    tokens for \$0.0144.
  - Luna is registered with cache read = full input (\$0.10/M). A window run of about
    370-520k tokens is about \$0.04-0.06 by Inspect's count. So Luna may hit `cost_limit`
    around D4-D6, which can be before T1's decision. The run is truncated, but still
    sealed and scored.
  - The spec says the limit is "2 × the measured smoke cost **for that model**", and Luna
    has no smoke.
  - Options, for the controller or owner:
    - (a) run as ruled and accept truncated Luna runs;
    - (b) run Haiku with `--model anthropic/claude-haiku-5-5`, then Luna with `--model
      openai-api/xpl/gpt-6-luna --sample-cost-limit 0.12`. The Luna worst case is
      6 × 0.12 × 2 = \$1.44, and both evals together are about \$1.79 ≤ \$5;
    - (c) register a real Luna cache price if the gateway lists one.
- **Mistral's post-check pass rate is unknown.** Rejected texts fall back to the template,
  which is logged. A high reject rate weakens the "prose" arm but stays safe. Read the
  counts printed after pregen.
- **Dedupe changed.** An errored copy now loses to a clean copy of the same cell. For the
  existing Task 28 fixture nothing changes (its tests pass). It does change which run is
  in n when both copies are labelled.
- **`retry<k>` is not wired.** If a deterministic failure comes from cached model outputs,
  the only no-code way to rerun is a fresh `INSPECT_CACHE_DIR`, which makes the whole eval
  paid.
- **Estimate split by runs.** Haiku and Luna costs differ, so the ledger's per-line
  `estimate` is only a share. The guard checks the whole step's estimate up front and the
  remaining share before Luna.
- **full_run** needs its own token limit (above) and a pregen beyond D10.
