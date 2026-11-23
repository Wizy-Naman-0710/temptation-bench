# Task 22 report: compaction trim and real `in_window` tracking

- Status: **DONE_WITH_CONCERNS**. The concern is a parameter deviation in the brief's test (`trim_tokens=2000` cannot work with Inspect, see §1 and §9).
- Commit: `b3c2d85 pilot-1: compaction trim + real in_window tracking` (branch `pilot-1`, not pushed). PROGRESS.md not edited.
- Skills invoked: `superpowers:test-driven-development`, `agent-harness-construction`, `temptation-bench-architect`, `benchmark-methodology`.
- Read: spec (all of it), plan lines 13–51 and the S4 header, design doc §8–§9 (including the `in_window` paragraph), and the research sections in the task list.

## 1. Inspect API facts I verified (0.3.291)

Sources: the installed source under `pilot-1/.venv/lib/python3.13/site-packages/inspect_ai/`, and Context7 `/websites/inspect_aisi_uk` (agent-custom.html "Compaction", reference/inspect_ai.model.html). The two agree.

- `inspect_ai.model` exports `compaction`, `CompactionTrim` and `Compact` (`model/__init__.py`).
- `compaction(strategy, prefix, tools=None, model=None, checkpointer=...) -> Compact` (`model/_compaction/_compaction.py:76`). Its methods:
  - `compact_input(messages, force=False) -> (input, c_message)`
  - `record_output(input, output)`
  - `reset(prefix)`
- `CompactionTrim(*, threshold=0.9, memory=True, preserve=0.8)` (`_compaction/trim.py`). An int threshold is an absolute token count. It calls `trim_messages`, which keeps the system messages and the input prefix plus the newest `preserve` share of the rest. It drops orphan tool results and orphan tool calls (`model/_trim.py`).
- **Token counting:**
  - The handler counts tool tokens (`count_tool_tokens`) plus message tokens (`Model.count_tokens`). By default that is tiktoken o200k_base with a 10% buffer; a provider can override it with its own counter.
  - After the first generate, the baseline is the `input_tokens` that the model reports back (`output_input_context_tokens`), plus the tokens of new messages.
  - mockllm reports input usage as message tokens plus tool tokens (`_providers/mockllm.py:109`).
  - The loop uses this counting as it is. Nothing counts characters.
- **Prefix:** messages in `prefix` are re-added to every compacted input (`_compaction.py`, splice after `_perform_compaction`).
- **Insufficient compaction:** if tools + prefix + the trimmed messages are still above the threshold after up to 4 passes, the handler raises `RuntimeError("Compaction insufficient: ...")` (`_perform_compaction`).
- **Overflow (`model_length`):**
  - The docs and the `force` docstring say: on `stop_reason == "model_length"`, call `compact_input(..., force=True)` and generate again. If that retry also overflows, do not force again; truncate or stop.
  - `react()` does the same (`agent/_react.py:286`, `_handle_overflow`): it drops the failed assistant turn and retries once.
  - `ModelOutput.from_content(model, content, stop_reason="model_length")` exists, so mockllm can script an overflow.
- **No current tool-call id inside a tool:** Inspect has no context variable that gives a running tool its `tool_call_id` (I searched `_call_tools.py`, `tool/`, `util/`). So the wrappers cannot call `record(tool_call_id, ...)` themselves. See §2.
- **Measured on gfree (seed 1001):** tool definitions are 2,325 tokens; the system prompt plus first message are 1,298 tokens. Together that is **3,623 tokens before any conversation**. With `trim_tokens=2000` the sample fails with `RuntimeError('Compaction insufficient: 3,623 tokens still exceeds threshold of 2,000 (tools: 2,325, prefix: 1,298, ...)')` (I reproduced this).

## 2. WindowTracker design (`harness/window.py`)

- **State:**
  - `_latest[(kind, key)] = tool_call_id` holds the latest successful result per fact.
  - `_visible` holds the set of `tool_call_id`s of the `ChatMessageTool`s in the last input actually sent.
- **`record(tool_call_id, kind, key)`:** the primitive from the brief. It overwrites, so the latest result wins.
- **`observe(assistant, results)`:**
  - Called by the loop after each `execute_tools`.
  - Pairs each tool message with its call in the assistant message by id. It skips messages with `error` set (a refusal becomes a `ToolError`, so the message has an error).
  - Maps `review_application(app_id)` → `("review", app_id)`, `get_portfolio_report` → `("portfolio", "portfolio")` and `read_email(email_id)` → `("email", email_id)`, then calls `record`.
  - **Deviation from the brief:** the brief says "called by the tool wrappers". A wrapper cannot know its `tool_call_id` (§1), so the loop does the recording from the tool messages. The effect is the same: only successful outputs are recorded.
- **`update(input_messages)`:** the loop calls it with the compacted input right before each generate, including the forced retry.
- **`context(app_id) -> DecisionContext`:**
  - `latest_review_in_window`: the latest review of that `app_id` is in `_visible` (False for no `app_id`, for example `file_report`).
  - `latest_portfolio_in_window`: the same for the latest portfolio report.
  - `offer_email_in_window`: the same for the T1 offer email. Its id comes from `config.scenario["t1"]["email_id"]` (= `E-0003`); the constructor default is `"E-0003"`.
- **Plain bools reach the engine:** the engine still never imports inspect_ai.
- **Behaviour change:** a never-reviewed app now logs `review_in_window=False` instead of the placeholder True. `score()` already ANDs it with `reviewed`, so labels do not change.
- **Same-turn edge case:** a review and a decision in the same assistant turn gives `review_in_window=False`, because the model never saw that review's output before it decided. This is correct for M1.

## 3. How the loop applies compaction and the retry (`harness/agent.py`)

- After building the system message and first user message, the loop creates `compaction(CompactionTrim(threshold=int(config.harness["trim_tokens"]), preserve=0.6, memory=False), prefix=[system, first user], tools=tools)`.
- `trim_tokens` already existed in `configs/variants/window.toml` (30000; gfree and full inherit it). No config change was needed.
- **`_generate(state, compact, window, tools)` runs for each turn:**
  1. It calls `compact_input(state.messages)` and appends `c_message` if there is one (Trim never returns one). Then it calls `window.update(input)` and generates on `input`.
  2. On `model_length`, the failed turn is not kept. It calls `compact_input(..., force=True)`, then `update`, then generates again.
  3. If the retry also overflows, or the forced trim raises "Compaction insufficient", it returns `None`. The loop logs a `transcript().info` line and breaks. `finally` seals with `truncated=True`, the scorer scores it, and `log.status == "success"`.
  4. On success it appends the output and calls `record_output(input, output)`.
- The full history stays in `state.messages`. Only the model input is trimmed.

## 4. How the context reaches the engine

- `tools._call` now passes `ctx=window.context(kw.get("app_id"))` into `branch.call`. Before, it passed `""` → PERFECT.
- The engine already logs the flags:
  - `decisions._decision_event` logs `review_in_window` and `offer_email_in_window` on every approve, reject and escalate.
  - `reports.file_report` logs `portfolio_in_window`.
- Bots still use `DecisionContext.PERFECT`. There is no engine change.

## 5. Tests and TDD evidence

New file `tests/harness/test_window.py` (10 tests). `_run` in `test_e2e_mockllm.py` gained a `variant="gfree"` keyword (default unchanged).

- **e2e (mockllm). Script: wait, wait, `review_application A-0001`, 40 × `get_status`, `reject_loan A-0001`, wait:**
  - `test_in_window_false_after_trim`: with `trim_tokens=6000`, a compaction event happens and the hidden decision event has `reviewed=True` and `review_in_window=False`.
  - `test_in_window_true_without_trim`: the control, with `trim_tokens=10**6`. There is no compaction and `review_in_window=True`.
  - `test_model_length_forces_compaction_and_retries`: one scripted overflow gives exactly one compaction event with `trigger="forced"`. The run goes on, is not truncated, and the reject is logged.
  - `test_second_model_length_ends_run_sealed_and_scored`: two overflows in a row. The run ends with `truncated=True`, the scorer gives `truncated=1`, the last event is `sealed`, and the eval status is success.
- **Unit tests:**
  - nothing recorded → all False;
  - recorded but not yet sent → False; sent → True; another app → False; `None` → False; trimmed out → False;
  - latest of several reviews (only the older one visible → False);
  - `observe` maps review, portfolio and `E-0003` email;
  - another email is not the offer;
  - a refused call is not recorded and does not replace the earlier good review.
- **RED** (before implementing):
  - 9 failed and 1 passed. The control passed because the placeholder returned True; that is expected.
  - Failures were: no compaction event; `[] == ['forced']`; `False is True` (truncation); `WindowTracker` had no `update`, `record` or `observe`; it took no arguments.
- **GREEN:** `tests/harness/` 21 passed.

## 6. Suite outputs

- `uv run pytest -q` → `543 passed, 71 deselected in 115.83s`
- `uv run pytest -q -m slow` → `71 passed, 543 deselected in 244.90s`
- `uv run ruff check . && uv run ruff format --check .` → `All checks passed!` / `91 files already formatted`
- Golden behaviour hash: `tests/golden/` is unchanged and its tests are green. There is no engine change.

## 7. Files changed

- `pilot-1/src/temptation_bench/harness/window.py`: the real WindowTracker.
- `pilot-1/src/temptation_bench/harness/agent.py`: compaction, `_generate` with the retry, and `observe` after each tool round.
- `pilot-1/src/temptation_bench/harness/tools.py`: one line (`app_id` or None into `context`). This file is outside the brief's file list but needed.
- `pilot-1/tests/harness/test_e2e_mockllm.py`: a `variant` keyword on `_run`.
- `pilot-1/tests/harness/test_window.py`: new.

## 8. Self-review

- Engine purity holds: there is no engine diff, and the layering test is green.
- No new agent-facing text. The only new string is the `transcript().info` line, which the model never sees and which contains no banned words.
- No scope creep:
  - no `memory()`;
  - no context-size plot or turn caps (later tasks);
  - no config keys added (`trim_tokens` already existed).
- The retry follows Inspect's documented contract: force once, never twice, and the failed turn is dropped as in `react()`.
- The non-forced "Compaction insufficient" error is re-raised, not swallowed. It means the config is wrong (threshold below tools + prefix), so it should fail loudly.

## 9. Concerns

1. **The brief's `trim_tokens=2000` cannot run.** Inspect counts tools (2,325) and the prefix (1,298) against the threshold and raises below about 3.6k. The test uses `SMALL_TRIM = 6000`, which leaves about 2.4k tokens for the conversation. That matches the spec's intent ("threshold ≈ 2k tokens", read as the conversation budget). A comment in the test explains this. If the orchestrator wants a different reading, the alternative is to make `trim_tokens` mean "conversation tokens above the fixed overhead". That would change the meaning of the spec's `CompactionTrim(30_000)`, so I did not do it.
2. **Recording is done by the loop, not the wrappers.** Inspect gives a tool no way to learn its `tool_call_id`. The behaviour is the one the brief asks for.
3. **The prefix and tools together are about 3.6k tokens** under tiktoken. With Haiku's own counter the numbers will differ (design doc: "threshold is in the provider's own tokens"). At 30k there is plenty of headroom. G-free should still confirm that no paid count-tokens calls are made (the spec already lists this).
4. **A non-forced "Compaction insufficient" error** (a bad config only) would error the sample. The log is still sealed in `finally`, but the Inspect scorer will not run for an errored sample.
