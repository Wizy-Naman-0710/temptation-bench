# Review: Tasks 22–26 (S4: M3 harness, budget guard, people prose)

- Range: BASE 0c18ca9 .. HEAD 4fa936a (10 commits). Reviewed from the diff package in four passes (budget/engine, agent/pregen/replay/settings/tools/window/run, tests, cross-task), with focused Inspect-source checks for named risks.
- Method: superpowers task-reviewer template, applied per task; verdicts are spec compliance + task quality.
- Line numbers are in the files at HEAD 4fa936a (paths relative to `pilot-1/`).
- Nothing was run against the gateway. `.env` was checked only with `test -s` (present). No test suite was re-run.

Named-risk checks made outside the diff (one per risk):
1. **Who counts tokens for compaction on Haiku.** I read the Inspect 0.3.291 source: `model/_compaction/_compaction.py:177-216`, `model/_model.py:1379-1484`, `model/_providers/anthropic.py:1148-1226` and `model/_providers/openai.py:381-413`. This gives R22-1.
2. **Whether running several models in one eval runs them at the same time.** `_eval/eval.py:311` says `max_tasks` "defaults to number of models being evaluated". This gives X-1.
3. **Whether tests can reach a real model.** `model/_model.py:2315-2320` (the `INSPECT_DISABLE_MODEL_API` switch, which mockllm ignores) and `_util/dotenv.py:15-26` (`init_dotenv` loads the nearest `.env` into `os.environ`). I also grepped `tests/` and `pyproject.toml` for the switch and found none. This gives R25-1.
4. **The scorer's dependence on LIVE and the JSONL path.** I read `harness/scorer.py` (for X-1).
5. **The default visibility of `world.event`.** `engine/world.py:82-87`: the default is `hidden`, so `harness_event` and `people_fallback` events are hidden.
6. **Whether purpose text drives any engine logic** (if it did, prose would change behaviour, not only text). I grepped `engine/` and `bots/`: purpose is only stored and shown.
7. **Turn caps in the variant files.** `configs/variants/{gfree,full}.toml` hold 120 and 600, and window holds 400.

---

## Task 22: Compaction and real `in_window` tracking

### Spec Compliance
✅ **Spec compliant.** Two plan-number deviations are covered by controller rulings, and I agree with both:
- The test uses a trim of 6000, not 2000. Inspect counts about 3.6k tokens of tools and prefix against the threshold, which leaves about 2.4k tokens of conversation. That matches the spec's "≈2k".
- The loop records results through `observe`, not inside the wrappers, because a tool cannot learn its own `tool_call_id`.

Checked against the brief:
- `record`, `update` and `context` have the brief's signatures (`harness/window.py:35-67`).
- `in_window` means "this tool_call_id is in the last input sent after compaction" (`window.py:50-60`).
- `window.update(input)` is called with the compacted input before every generate, including the forced retry (`harness/agent.py:102-111`).
- `CompactionTrim(threshold=trim_tokens, preserve=0.6, memory=False)` with prefix = system + first user (`agent.py:188-192`).
- On `model_length`, the loop forces a trim and retries once (`agent.py:102-121`).
- The `tools.py` edit is outside the brief's file list, but the context has to come from somewhere, so it is needed.

⚠️ **Cannot verify from the diff:** how the Anthropic provider counts tokens through the gateway (R22-1). Only a real Haiku call can settle it.

### Strengths
- The latest-result-wins keying `(kind, key) → tool_call_id`, the refusal filtering (`m.error is not None`) and the same-turn review → False rule are all correct and pinned by unit tests (`tests/harness/test_window.py:837-903`).
- The overflow handling matches Inspect's own `react()` contract: force once, drop the failed turn, then stop sealed and scored.
- The e2e trim test is backed by a control run with no trim.

### Issues
#### Critical
None.

#### Important
- **R22-1: on the Haiku route, compaction makes extra `count_tokens` API calls through the gateway, and no step before the paid smoke exercises this.**
  - Where: `src/temptation_bench/harness/agent.py:188-192` (`compaction(...)` with the default target model), and `_generate` at `agent.py:102-104`.
  - **What happens:**
    - `compact_input` calls `target_model.count_tokens(...)` on every turn. The first call also counts tool tokens and prefix tokens (`inspect_ai/model/_compaction/_compaction.py:177-216`).
    - `Model.count_tokens` hands this to the provider (`_model.py:1379-1484`).
    - The **Anthropic provider overrides it with the native `client.messages.count_tokens` API** (`_providers/anthropic.py:1148-1226`). With `ANTHROPIC_BASE_URL` set, that is `POST /v1/messages/count_tokens` to the gateway: at least 3 calls before the first generate, then about one per turn, so about 150 extra requests in a smoke.
    - The `openai-api/*` provider has no such override and uses a local heuristic. So G-free (Luna) cannot see this.
    - The route check (2 plain generates) does not go through `compaction` either.
    - mockllm counts locally, so no test sees it.
  - **Why it matters:** spec §6 (G-free row) requires "confirm no extra count-tokens calls", and that check cannot be met for Haiku by any planned step. The possible outcomes on the first paid smoke are:
    - The gateway has no route for it: the first `compact_input` raises a non-`RuntimeError` API error, which `_generate` does not catch. The sample errors, is retried, errors again, and the smoke step is wasted. It probably costs $0, because this happens before the first generate.
    - The gateway bills it, or rate-limits it: an unknown extra cost, or 429 retries. This hits the "tiered and undocumented" rate limits of spec §7.2.
  - **Fix (before Task 30):** choose one of these.
    - (a) Make compaction count tokens locally. For example, give `compaction(..., model=...)` a wrapper whose `count_tokens` uses Inspect's local `count_tokens` helper or tiktoken. The trim then stays deterministic and free. Note that the trim threshold becomes "tiktoken tokens", which matches the measurement behind the Task 23 floor.
    - (b) Add one `count_tokens` call through the Anthropic route to the Task 30 route check, and record in PROGRESS whether it is billed.

    (a) also removes a network dependency from every turn.

#### Minor
- **R22-2:** `harness/agent.py:103-107`. `except RuntimeError` on the forced pass turns *any* `RuntimeError` from `compact_input` into "input too long", which ends the run silently as truncated. Match on the "Compaction insufficient" message, or re-raise anything else.

### Assessment
**Task quality:** Needs fixes.
**Reasoning:** The tracker and the loop logic are correct and well tested. But on the real Haiku route, the compaction design depends on an extra provider API that nothing has checked yet (R22-1), and the first place it would show up is the paid smoke.

---

## Task 23: Loop policies (nudges, caps, probe, transcript) + replay

### Spec Compliance
✅ **Spec compliant.**
- **Values:**
  - turn caps: window 400, full 600, gfree 120 (from the configs);
  - `day_turn_cap = 40` → hidden `harness_day_cap`, then `wait_for_next_day` (`agent.py:222-226`);
  - the exact nudge text;
  - 3 no-tool replies → `harness_auto_advance` (`agent.py:211-217`);
  - 10 auto-advances → break → `finalize(truncated=True)` (`agent.py:218-220`, `228`).
- **Probe:**
  - sent only after the seal, and only after a normal finish (`agent.py:231-243`);
  - exact text (`configs/variants/window.toml:190`);
  - stored in `RunStore.probe` and `probe_label`.
- **Mirror:** `transcript().info(event, source="engine")` inside `span(f"day-{n}")` (`agent.py:139-147`). Mirroring at the end of the run is the ruled deviation, and I agree: spec §9.1 forbids a log reader on Branch.
- **Replay:** `replay(eval_path, sample_id) -> SealedLog` reproduces the JSONL byte for byte using the logged `DecisionContext` (`harness/replay.py:41-74`).
- **Leak rule:** a test asserts that no banned word appears in any system, user or tool message except the probe (`tests/harness/test_loop_policies.py:2882-2884`).
- The trim-floor pre-work (`engine/config.py:18-31`) is as ruled.

### Strengths
- `call_engine` is a single door into the engine, and it journals the exact engine kwargs plus the ctx. The loop's own wait goes through the same door, which is what makes byte-exact replay possible.
- Replay checks the journal against the tool span names (`replay.py:62-66`) and resolves attachments. Mutation-checked: replacing the logged ctx with PERFECT breaks the replay tests.
- `Branch.harness_event` is narrow: only `harness_*` names, hidden, no state change, a no-op after the seal (`engine/branch.py:159-166`). Bots never call it, so the golden hash is safe.

### Issues
#### Critical
None.
#### Important
None.
#### Minor
- **R23-1:** setup runs outside the `try/finally` that seals the log.
  - Where: `harness/agent.py:178-194`. The lines between `LIVE[st.run_key] = branch` and `try:` are `make_tools`, `get_model`, `generate_config`, `_write_harness_json` (which does file I/O) and `compaction(...)`.
  - What goes wrong: if any of them raises, the branch is never sealed and stays in `LIVE`. The "`try/finally` around the loop calls `finalize`" invariant (spec §9.1) then does not cover the whole lifetime of the branch.
  - Fix: start the `try` right after `Branch.new`.
- **R23-2:** `await mirror_events(...)` runs inside `finally` (`agent.py:230`).
  - If it raises, for example on a JSONL read error, it hides the original exception.
  - Under a time-limit cancellation, an await inside `finally` may re-raise the cancellation. The seal has already happened, so only the mirror is lost.
  - Fix: wrap it in `try/except Exception` with a `transcript().info` note.

### Assessment
**Task quality:** Approved.
**Reasoning:** Every policy follows the config values and is tested end to end with mockllm. Replay is byte-exact and mutation-checked. Only robustness polish is left.

---

## Task 24: Model settings and per-cell cache

### Spec Compliance
✅ **Spec compliant:**
- `generate_config` sets `reasoning_effort="low"`, `cache_prompt="auto"`, `max_retries=5` and `CachePolicy(expiry="1W", scopes={"cell": "model|seed|dose"})`. It sets no temperature and no seed (`harness/settings.py:28-52`).
- That config is passed on every generate: the loop turns, the forced retry and the probe (`agent.py:110`, `182`).
- `time_limit` is 3600 or 10800 by mode (`harness/task.py:47`).
- `token_limit` is a task parameter.
- `harness.json` records the settings with `"temperature": "not set (provider default)"`, `max_retries`, the Inspect version, the engine SHA, the config SHA and the tool schemas.
- All six brief tests exist. The cache test is honest: the mockllm script is used up, so any real call in run 2 would error.
- The `engine_sha` coverage (`engine/**/*.py` instead of `engine/*.py`) is a documented superset, which is fine.
- The `parallel=False` pre-work is as ruled.

⚠️ **Cannot verify from the diff:**
- that `effort: low` actually reaches the provider (deferred to Task 30, confirmed);
- that the cache hits across processes (deferred to Task 30, confirmed).

### Strengths
- The per-call `config=` beats task and CLI config, so a stray CLI `--reasoning-effort` cannot change the cell's settings.
- `test_other_dose_never_reads_the_cell_cache` proves that the first inputs of the two dose arms are identical, so only the scope separates them. It was mutation-checked.
- Every test gets its own cache directory (`tests/conftest.py:34`).

### Issues
#### Critical
None.
#### Important
None. The missing `people` in the cell scope is already ruled into the fix wave, and I confirm the ruling (see X-2).
#### Minor
- **R24-1:** `harness/settings.py:25`. When the fix wave adds `people` to `CELL_SCOPE`, also add the variant or mode.
  - Window and full runs of one cell share `model|seed|dose` today.
  - The inputs probably diverge at the system prompt (`last_day`), so this costs nothing and removes the question.
  - Update the `CELL_SCOPE` string written to `harness.json`, and the test.
- **R24-2:** `harness/agent.py:150-162`. `harness.json` does not record the run's people backend (prose or template), and its `config_sha256` leaves out the per-sample `people` choice.
  - Each sample's `run_config` event already carries this, so nothing is lost.
  - Adding it to `harness.json` would make the file self-describing.

### Assessment
**Task quality:** Approved (with the ruled fix-wave scope change).
**Reasoning:** The settings match the spec exactly. The cache behaviour is proven, not assumed, and nothing secret goes into `harness.json`.

---

## Task 25: Budget guard and paid runner

### Spec Compliance
✅ **Spec compliant:**
- `STOP_LINE` and `STEP_CAPS` hold the exact values (`src/temptation_bench/budget.py:29-37`).
- `fetch_balance`:
  - calls `GET {base minus /v1}/api/v1/credits` with a bearer key;
  - reads the key with `dotenv_values` into a local variable only;
  - uses https only and follows no redirects;
  - fails closed on transport, status and body errors (`budget.py:258-316`).
- `check` refuses in each case the brief lists: over the step cap, over the stop line, an unreadable balance, a missing ledger and a missing `.env` (`budget.py:353-391`).
- `record`:
  - sums `stats.model_usage[*].total_cost`, which includes the billed calls of retried attempts;
  - appends one line only, with fsync;
  - records the balance before and after (`budget.py:445-514`).
- `run.py` order is: check, then launch, then record in `finally`. It passes `retry_on_error=1` and a per-sample `cost_limit` (default $1 for the smoke; 2 × the smoke's cost per run for later steps), and passes `--token-limit` through.
- All six brief tests are present.
- Unbuilt steps refuse with no network call.

⚠️ **Cannot verify from the diff:**
- **The body shape of the credits response.** Deferred to Task 29, confirmed.
- **Whether a gateway error text inside Inspect's own sample error (in the `.eval`) could echo a credential.** Inspect, not `run.py`, writes it. Check one real error at Task 29 or 30.
- **The default `token_limit`.** The Task 24 brief says `run.py` sets it after the smoke as 2 × T̂_run from the ledger. It was not built, and the ledger has no deferral for it (R25-5).

### Strengths
- The fail-closed design is complete and every refusal is tested:
  - an unknown step, NaN, inf or a negative estimate;
  - each `.env` problem and each ledger problem;
  - a non-200 status (redirects are not followed) and each kind of bad body;
  - a negative balance, and a balance below the estimate.
- The error is raised outside the `except` block, so the auth header cannot survive in `__context__`. It was mutation-checked.
- `actual` can only be counted up, never down:
  - it is raised to the balance drop if that is larger;
  - it is raised to the step cap when a log is unreadable, unpriced or incomplete, or when the eval failed before writing a log;
  - failed attempts count, through the header stats.
- Test hygiene for the key: a fake key that is not key-shaped, and autouse fixtures that point the defaults at missing files.

### Issues
#### Critical
None.

#### Important
- **R25-1: tests can reach the real gateway with the real key.** Nothing blocks model APIs, and Inspect loads the real `pilot-1/.env` into the test process.
  - Where: `tests/conftest.py` (no kill switch) and `tests/test_budget.py:356-392`.
  - **What happens:**
    - `inspect_ai.eval` runs `init_dotenv()`. That loads the nearest `.env`, which is `pilot-1/.env` when pytest runs from `pilot-1/`, into `os.environ`, real `ANTHROPIC_*` and `XPL_*` values included (`inspect_ai/_util/dotenv.py:15-26`; the implementer's concern 6 says the same).
    - From then on, any test that builds a non-mock model makes a paid call.
    - `test_key_never_in_ledger_or_stdout` already calls `run.main(["--step","smoke",...])` **without `model=`** (`test_budget.py:381-388`). The only thing that stops a real Haiku smoke there is that the mocked balance transport fails first. If someone changes that transport, a test spends real money.
  - **Fix:** add an autouse `monkeypatch.setenv("INSPECT_DISABLE_MODEL_API", "1")` in `tests/conftest.py`. Inspect refuses every non-mockllm model API under it (`model/_model.py:2315-2320`). A test can assert that the switch is on.
- **R25-2: the runtime worst-case spend is never checked against the hard budget.**
  - Where: `src/temptation_bench/run.py:199-210`. The stop line is checked only against the user's `--estimate`.
  - **The gap:**
    - At run time the only stop is the per-sample `cost_limit`, so the worst case is `runs × cost_limit`, plus retried attempts.
    - For the mini-batch (12 runs, cost limit 2 × the smoke): with a $0.33 smoke the worst case is 12 × $0.66 ≈ $7.9. That is over the $5.00 cap and, after the earlier steps, close to or over the $9.50 stop line.
    - For the built single-sample steps (smoke, gfree) the worst case is about $1–2, so this is not dangerous yet.
  - **Fix (before Task 31):** in `run_step`, compute `exposure = runs × sample_cost_limit`. Refuse if `spent + exposure > STOP_LINE`, and print the exposure in the plan or dry run. This keeps D9's per-sample rule (no Budget/N cut) and still makes the owner's hard $10 hold at run time.

#### Minor
- **R25-3: `gfree` has no default token limit.**
  - Where: `run.py:119`. The plan entry carries no `token_limit`, so the 800k free-tier guard depends on the operator typing `--token-limit 800000` (plan Task 29 step 3).
  - Meanwhile the step's per-sample `cost_limit` is $1.00 on a step whose cap is $0.
  - Fix: give `Plan` a default token limit (800_000 for gfree), or refuse gfree without one.
- **R25-4:** `run.py:227-243`. If `budget.record` raises inside `finally` (for example, the ledger was deleted mid-run), it hides the eval's own exception, and no line is written. Catch, print the redacted error and re-raise the original.
- **R25-5: the default token limit from the smoke is not built** (Task 24 brief: "run.py sets after the smoke as 2 × T̂_run").
  - `record` stores `total_tokens`, but nothing turns it into a default.
  - Harmless now, because mini_batch and full_run refuse.
  - The controller should record a "Deferred to Task 31" line so it is not lost.

### Assessment
**Task quality:** Needs fixes.
**Reasoning:** The guard itself is thorough and properly fail-closed. Two gaps sit around it:
- R25-1: the test suite has no hard block on real model calls.
- R25-2: the runner never bounds the worst-case run-time spend against the stop line.

Both are cheap to fix and should land before any paid step.

---

## Task 26: People prose pregen (P2)

### Spec Compliance
❌ **Issue found:** the pregen generate does not use the global model settings (R26-1).

Everything else complies:
- **`post_check`:**
  - facts must appear verbatim;
  - no other digits, and no number or date words the draft does not have;
  - at most 1.5 × the draft, in words and in characters;
  - the banned stems apply anywhere, and `loan` is banned in the C3 note only;
  - not empty, one line (`engine/people.py:62-93`).
- **Prose-eligible texts** are exactly spec §5's list (`prose_jobs`, `scenario.exogenous_drafts`). The D3 offer and its dose sentence never reach `compose`; the spy test confirms it.
- **`ProsePeople`** reads the JSON only and re-runs the check. It falls back on a missing key, a text rejected at pregen, a changed draft or a failed recheck, and logs a hidden `people_fallback` (`people.py:131-174`).
- **A missing prose file fails loudly** before any model call (`harness/task.py`).
- **The minimal pair holds** under prose for doses 0, $1k and $30k. E-0003 is byte-identical under template and prose for every dose.
- **Replay works under prose** and checks the prose file's SHA.
- **The attempt-file pre-work** is as ruled.
- **The deferred items are confirmed:** the pregen step in `run.py` (Task 31), D1–D10 only, and the small effect on 2-word purposes.

⚠️ **Cannot verify from the diff:** the S4 exit step. The brief asks for a PROGRESS.md update and the commit `"pilot-1: S4 done (harness, budget, people)"`. Neither exists yet: HEAD is "people prose pregen (P2)". This is presumably the controller's job after the fix wave.

### Strengths
- The engine never calls a model. Prose comes only from a committed JSON whose SHA goes into `run_config`, so a prose run can be traced to its exact file.
- The recheck at run time means a hand-edited file cannot slip a number in. It was mutation-checked.
- The minimal-pair test is not vacuous: the prose arm really differs from the template arm, and fallbacks are included in the compared events.
- `get_model(role="people", required=True)`: pregen can never silently use the agent model.

### Issues
#### Critical
None.

#### Important
- **R26-1: pregen ignores the global model settings (effort `low`, `max_retries`).**
  - Where: `src/temptation_bench/harness/pregen_people.py:119`. `model.generate(state.messages)` passes no config.
  - Why it matters: spec D5 and §7.1 say "Reasoning effort **low** for all", and the batch constraints list `reasoning_effort="low"`, `max_retries=5`. As written, `qwen3.7-flash` runs at the provider's default effort (the spec notes that the server default, medium, costs more), and nothing records the setting.
  - The money at stake is small (the cap is $0.05), but it is a binding constraint, and the settings record would be wrong.
  - Fix: pass `config=GenerateConfig(reasoning_effort=h["reasoning_effort"], max_retries=int(h["max_retries"]))`, taking `h` from the window `[harness]` table. Optionally add a pregen cache (a re-run costs $0) and a small settings record next to the JSON. Add a test that asserts the config on the `ModelEvent`.

#### Minor
- **R26-2: fact order in reason strings can vary between runs** (latent determinism bug).
  - Where: `engine/people.py:69`, `values = sorted({...}, key=len, reverse=True)`.
  - Equal-length fact values keep set-iteration order, which depends on PYTHONHASHSEED. The `facts not verbatim: a, b` reason then varies, and that string goes into the pregen JSON and into `people_fallback` events in the engine JSONL.
  - Every current facts dict has one value, so nothing shows yet.
  - Fix: `key=lambda v: (-len(v), v)`.
- **R26-3:** `tests/harness/test_pregen.py:256-263`. The `prose_pair` fixture sets the global `Branch.strict_output = True` without `try/finally`. If a bot run fails, the flag leaks into later tests.
- **R26-4: the instruction and the check disagree by one word.**
  - The instruction says "Keep it under {n} words" (`pregen_people.py:43`), but `check_reasons` accepts up to and including n.
  - So the model is asked for fewer than n words while n is allowed.
  - With 2-word purposes, n = 3. Either say "at most {n} words" or check `< n`. Pick one, so that the prompt and the check agree.

### Assessment
**Task quality:** Needs fixes (one item: R26-1).
**Reasoning:** The safety design (offline, rechecked, SHA-pinned, minimal pair proven, bribe email never from prose) is strong. One binding model setting was missed on the new model call.

---

## Cross-task: how the five pieces fit together

How it works end to end (each link was verified):
- `run.py` calls the guard, then `temptation_bench(variant, seeds, doses, people, token_limit)` (Tasks 24 and 26).
- `setup_run` uses the attempt-file rule (Task 26).
- `branch_manager` builds:
  - the people backend for each sample (Task 26);
  - the per-cell `GenerateConfig` (Task 24);
  - the compaction and the `WindowTracker` (Task 22);
  - the policy counters (Task 23).
- On every turn: `compact_input`, then `window.update`, then generate with the cell config, then `execute_tools`, then `window.observe`.
- Every engine input goes through `call_engine`, which journals it.
- `finally` seals the log and mirrors it into the transcript. The probe runs after that.
- The scorer reads the sealed JSONL.
- `replay` re-feeds the journal under the same people backend.
- `record` sums the header stats, so retries are counted.

The layering holds: there are no inspect_ai imports in `engine/`, and the new engine imports are stdlib only.

### X-1 (Important): two models in one eval would collide on log paths, `LIVE` keys and `harness.json`
- **Where:**
  - `src/temptation_bench/harness/task.py:40-43`: `run_id` is set once when the Task object is built, and the sample ids are `s{seed}-d{dose}`.
  - `harness/agent.py:60-63`: `run_key = sample_id|epoch`; the path is `runs/<run_id>/<sample_id>-e<epoch>.jsonl`.
  - `agent.py:153`: `harness.json` is written by the first writer only.
  - `run.py:104`: `model=list(p.models)`.
- **What would happen:** `launch_task_eval` hands one Task object plus a list of models to `inspect_eval`, and Inspect runs the tasks concurrently (`max_tasks` defaults to the number of models, `_eval/eval.py:311`). The Haiku and Luna samples of the same cell would then:
  - share one JSONL path. `keep_failed_attempt` would rename the other model's log to `.attempt1`, which marks it as a failed attempt. Worse, the run sealed second overwrites the file, and the first sample's mirror or scorer can read the other model's log.
  - share one `LIVE` key, which the scorer uses for its fallback seal.
  - share one `harness.json`, which names only the first model.
- **Status:** nothing built uses more than one model today. The Task 31 deferral ("one eval per model", because `cost_limit` is one number per eval) avoids this if it is followed. But plan Task 31 step 3 still says "the runner calls Inspect for both models", and the code path allows it.
- **Fix:** make it structural.
  - Add the model to `run_key` and to the log path, for example `runs/<run_id>/<model-slug>/...`. Write `harness.json` per model.
  - Or have `launch_task_eval` refuse more than one model, so the ruling is enforced and not only remembered.

### X-2: Confirmation of the controller rulings
- **Agreed:**
  - the 6000 trim in the test;
  - `observe` doing the recording in the loop;
  - the trim floor at config load;
  - the mirror written at the end of the run;
  - explicit `parallel=False` (Inspect's default was already serial, as the Task 24 report says);
  - probe errors caught;
  - the G-free over-count (it errs on the safe side);
  - the attempt files;
  - adding `people` to the cell scope in the fix wave (and add the variant or mode, R24-1);
  - the deferrals to Tasks 28, 29, 30 and 31.
- **One nuance on "a rerun of an errored cell keeps the cell cache"** (Minor). The ruling is sound for budget, but it only rescues *transient provider* errors, which happen before any response is cached.
  - For a deterministic harness error caused by a model output, the rerun replays the cached output and fails the same way, at $0.
  - With `fail_on_error` at Inspect's default, that second failure then stops the whole eval, which in a mini-batch cancels the other samples.
  - This is acceptable as fail-closed behaviour. Write it into the Task 31 runbook (resume with `eval_retry`; or use the `retry<k>` scope suffix the code already has).

### X-3: the spec's G-free checklist cannot cover the Haiku route
The G-free item "confirm no extra count-tokens calls" (spec §6) runs on Luna through `openai-api`. Luna counts tokens locally, so the check passes trivially and says nothing about Haiku. See R22-1. It needs a decision before Task 30, whichever fix is chosen.

---

## Counts

| Severity | Count | IDs |
|---|---|---|
| Critical | 0 | |
| Important | 5 | R22-1, R25-1, R25-2, R26-1, X-1 |
| Minor | 13 | R22-2, R23-1, R23-2, R24-1, R24-2, R25-3, R25-4, R25-5, R26-2, R26-3, R26-4, X-2 (retry-cache nuance), X-3 (note) |

Before any paid step, fix R25-1 and choose a fix for R22-1. R25-2, X-1 and R25-5 must land before Task 31. Fold R26-1 into the [22-26] fix wave.
