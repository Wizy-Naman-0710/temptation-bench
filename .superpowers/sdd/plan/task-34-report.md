# Task 34 report

## Step 1 pre-work: `--step full_run` launcher (no network calls made)

### What was built (`pilot-1/src/temptation_bench/run.py`)
- `STEPS["full_run"]` is now built. It runs one eval of `temptation_bench` through `launch_task_eval`, the same path the smoke uses.
  - Plan: model `anthropic/claude-haiku-5-5`, variant `full` (D1–D30), seed `1001`, dose `3000000`.
  - `people` is what `full.toml` resolves to, which is **template** (`full.toml` extends `window.toml`, which sets `people = "template"`). So no prose fallback applies. The dry run would print a fallback note if the plan were prose (tested).
  - `max_samples=1`, `retry_on_error=1`.
- New `Plan` fields:
  - `sample_cost_limit`, the step's own per-sample default. full_run uses **\$0.50**.
  - `token_note`, the source text printed in the dry run.
- `default_sample_cost_limit` uses `Plan.sample_cost_limit` when the plan sets one. full_run no longer needs a smoke line for its cost limit.
- The old `NEEDS_SMOKE` set did two jobs. It is now split:
  - `NEEDS_SMOKE = {"mini_batch"}`: the per-sample limit comes from 2 × the smoke cost.
  - `STEP_SPEND_COUNTS = {"mini_batch", "full_run"}`: earlier ledger lines of the step count against its cap.
- Token limit: `FULL_TOKEN_LIMIT = 2 * 3 * 434_288 = 2_605_728` is the step's own default. Because of that, the window "2 x smoke mean" default (868,576) is never used for full_run. `--token-limit` still overrides it.
- New dry-run and plan lines for task-eval steps (gfree, smoke, mini_batch, full_run):
  - `days: D1-D<last>`
  - `time_limit: <s> s (variant <v>)`
  - `turn caps: <n> per run, <m> per day (variant <v>)`
  - `local cache: on, per-cell scope (as the smoke)`
  - the source of the sample cost limit, e.g. `(step default)`, `(2 x smoke cost per run)`, `(--sample-cost-limit)` or `(default)`
- The docstring has a new `--step full_run` paragraph.

### Harness checks (no change needed)
- **Time limit:** `harness/task.py` already sets `Task(time_limit=int(harness["time_limit_s"]))`, and `full.toml` gives `time_limit_s = 10800`. Tested on the built task, both via the launcher and directly (window stays 3600).
- **Turn and day caps for full mode** (from `load_config("full").harness`; unchanged):
  - `turn_cap = 600` (full.toml)
  - `day_turn_cap = 40` (inherited from window.toml)
  - `no_tool_auto_advance = 3`, `max_auto_advances = 10`, `trim_tokens = 30000`
- **Cache:** the smoke does not turn off the local response cache, so full_run keeps it on. The per-cell scope is `model|seed|dose|people|variant`, so the `full` cell never shares a scope with the window smoke.
- **Logs and ledger:** logs go to `logs/paid/full_run-<stamp>/` (no per-model subfolder: `split_models` is False). The ledger line has `step: full_run`, `runs: 1` and `models: [haiku]`.

### Exposure arithmetic
- Default worst case = runs × sample cost limit × attempts = 1 × \$0.50 × (1 + 1) = **\$1.00**. That is under the \$1.50 cap.
- Stop line: spent is about \$0.1427 (current ledger), and \$0.1427 + \$1.00 = \$1.14, well under \$9.50.
- Overrides:
  - `--sample-cost-limit 0.70` gives \$1.40, which passes.
  - `--sample-cost-limit 0.80` gives \$1.60, which is over the cap and refuses.
  - The largest value that passes is \$0.75.
- Earlier full_run ledger lines count too. For example, \$0.60 already spent + \$1.00 is over \$1.50, so it refuses with "already spent".
- `--estimate` must be ≤ \$1.50 (budget.guard).

### Tests
`pilot-1/tests/test_run_task34.py` has 14 tests. All mocked: fake `.env`, `httpx.MockTransport`, and a fake `inspect_eval` or mockllm.
- `test_full_run_plan_is_one_haiku_run_full_seed_1001_dose_30k`
- `test_full_run_defaults_cost_limit_half_dollar_and_its_own_token_limit`: \$0.50 even with an empty ledger, and token limit 2,605,728
- `test_full_run_exposure_is_one_dollar_within_the_cap`
- `test_full_run_dry_run_prints_the_whole_plan`: every plan line, including the token source, time limit, turn caps, cache, log dir and no eval launched
- `test_full_run_dry_run_notes_the_prose_fallback_past_d10`
- `test_full_run_token_limit_flag_overrides_the_step_default`
- `test_full_run_launch_passes_the_limits_and_records_one_run`: checks the Task's token_limit and time_limit, the 1-sample dataset metadata, cost_limit, max_samples, retry, the log dir and the ledger `runs: 1`
- `test_full_mode_task_time_limit_is_three_hours`: this passed before the change, because the harness already does it (regression guard)
- `test_full_run_sample_cost_limit_flag_overrides_and_is_still_checked`
- `test_full_run_refuses_an_estimate_over_the_cap`
- `test_full_run_refuses_over_the_stop_line`
- `test_full_run_counts_earlier_full_run_spend_against_its_cap`
- `test_full_run_rejects_the_model_selector`
- `test_full_run_mockllm_thirty_days_one_ledger_run` (slow): a 30-day mockllm run through the runner. It checks the log succeeds, has 1 sample with variant full, cost_limit 0.50, retry 1 and a scored label, and that the ledger says `runs: 1`.

`tests/test_budget.py` was updated, because full_run is now built:
- The unbuilt-step refusal test now monkeypatches an unbuilt entry.
- The dispatch table now includes full_run.
- The full_run default cost limit is now 0.50, not 2 × smoke.

RED was seen before the code: 13 of the 14 new tests failed with "step full_run is not built yet". The time-limit guard passed, as noted above.

### Controller commands (run from `pilot-1/`)
The dry run reads the gateway balance (one GET), launches no eval and writes no ledger line:

    uv run python -m temptation_bench.run --step full_run --estimate <X> --dry-run

Success looks like this: exit 0, and it prints `DRY RUN (no eval launched)` and then:
- `step: full_run`
- `models: anthropic/claude-haiku-5-5`
- `variant: full (people=template)`
- `days: D1-D30`
- `seeds x doses: 1001 x 3000000 = 1 cells`
- `runs: 1`
- `max_samples: 1`
- `retry_on_error: 1 (...)`
- `sample cost_limit: $0.5000 (step default)`
- `token_limit: 2605728 (step default: 2 x 3 x the smoke's 434288 tokens per run, full mode)`
- `time_limit: 10800 s (variant full)`
- `turn caps: 600 per run, 40 per day (variant full)`
- `local cache: on, per-cell scope (as the smoke)`
- `exposure: $1.0000 (1 runs x $0.5000 x 2 attempts)`
- `estimate / cap: $<X> / $1.50`
- `spent / stop line`, `gateway balance`, and `log dir: .../logs/paid/full_run-<stamp>`

The real run:

    uv run python -m temptation_bench.run --step full_run --estimate <X>

Success looks like this:
- Exit 0, the same plan is printed, and then `recorded: full_run anthropic/claude-haiku-5-5 actual $<a> (...)`.
- One `.eval` file in `logs/paid/full_run-<stamp>/`.
- One new ledger line with `step: full_run`, `runs: 1` and `actual` ≤ \$1.00.
- The sample covers D1–D30 (or is `truncated` by a limit) and has scorer labels.

`<X>`: the brief says smoke actual × ρ⁻¹. For reference, here are measured costs (not a ruling):
- smoke: \$0.0144 per run
- mini_batch Haiku: \$0.0795 / 6 runs = \$0.0133 per run
- So about 3× the turns gives roughly \$0.04–0.05.

Any `<X>` ≤ \$1.50 passes the guard.

### Concerns
- **The token limit is a hard-coded 434,288**, the Task 30 smoke measurement. It is not read from the ledger. If a new smoke is recorded, `FULL_TOKEN_LIMIT` does not follow it. This matches the ruling's fixed value.
  - Mini_batch Haiku window runs averaged about 451k tokens. So 3× is about 1.35M, which gives about 1.9× headroom under 2.6M.
  - The 600-turn cap or the 10800 s time limit may bind before the token limit does.
- **Possible over-spend inside the cap:** the cost limit of \$0.50 is about 10× the expected cost per run. It is a ceiling, not a forecast.
- **The new dry-run lines also appear for smoke, gfree and mini_batch.** These are the days, time_limit, turn caps, cache and cost source lines. They only add text, and the existing substring tests still pass.
- **people=template:** the D11–D30 people messages, and D1–D10 too, are template texts. This differs from mini_batch, which used prose. A full-vs-window comparison therefore mixes the people backend.
- The report file sits under `.superpowers/sdd/`, which is gitignored, so it is not committed.

### Verification and commit
- `uv run pytest -q`: 850 passed (75 deselected).
- `uv run pytest -q -m slow`: 75 passed.
- `uv run ruff check . && uv run ruff format --check .`: clean.
- Commit `439f848` on pilot-1 (run.py, test_budget.py, test_run_task34.py). Not pushed; ledger not staged.
