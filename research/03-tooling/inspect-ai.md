# inspect-ai for a long-horizon simulation benchmark

- **Version checked:** `inspect-ai` **0.3.291** (PyPI, released 2026-11-17, needs Python >= 3.11). Checked 2026-11-21.
- **How checked:** installed the package in a clean venv, printed real function signatures, read the docs source in the [GitHub repo](https://github.com/UKGovernmentBEIS/inspect_ai/tree/main/docs), and ran a small smoke eval with the free `mockllm` model (no API cost). Every API name below exists in 0.3.291.
- Docs home: <https://inspect.aisi.org.uk/>
- Note: the docs use made-up example model names (e.g. `openai/gpt-6-luna`), but those IDs are real models as of Nov 2026. See [models-and-pricing.md](models-and-pricing.md).

---

## 1. Core structure: Task, Solver/Agent, Scorer

- A `Task` = `dataset` (list of `Sample`) + `solver` (a Solver **or** an Agent) + `scorer`. Docs: [Tasks](https://inspect.aisi.org.uk/tasks.html).
- `Task(...)` also takes: `model_roles`, `epochs`, `message_limit`, `token_limit`, `turn_limit`, `time_limit`, `working_limit`, `cost_limit`, `metadata`, `setup`, `cleanup`.
- A `Sample(input=..., id=..., metadata={...})` is one simulation run. Put your world config (seed, scenario name, temptation schedule) in `metadata`.
  - There is **no `seed` field on `Sample`**. Put the seed in `metadata` and read it with `state.metadata["seed"]` or typed `state.metadata_as(MyMeta)`.
- `TaskState` (what solvers and scorers see) has: `messages`, `output`, `metadata`, `metadata_as()`, `store`, `store_as()`, `epoch`, `sample_id`, `token_usage`, `cost_usage`, `token_limit`, `message_limit`, `cost_limit`.
- Scorers: `@scorer(metrics=[mean()])` decorating a function that returns `async def score(state: TaskState, target: Target) -> Score`. Docs: [Custom scorers](https://inspect.aisi.org.uk/custom-scorers.html).
  - `Score(value=..., explanation=..., metadata={...})`. `value` can be a number, string, or a dict of many numbers (good for "net worth", "violations", "days survived").

## 2. Custom tools (`@tool`)

- Docs: [Tool basics](https://inspect.aisi.org.uk/tools.html), [Custom tools](https://inspect.aisi.org.uk/tools-custom.html).
- Pattern: an outer factory decorated with `@tool` that returns an inner `async def execute(...)`. The **docstring + type hints are required**. Inspect builds the JSON schema from them.
- **Return type (`ToolResult`)**: `str | int | float | bool | ContentText | ContentImage | ContentAudio | ContentVideo | ContentDocument | list[...]`. For a simulator, just return a `str` (or JSON string).
- **Errors the model should see**: `raise ToolError("Insufficient funds")`. This becomes the tool result text and the run continues. Other unexpected exceptions fail the sample.
- **Tool calls run one by one by default** (serial, in the order the model wrote them). Only `@tool(parallel=True)` tools run at the same time. Keep the default for simulator tools: it keeps the run deterministic.
- Tool output size limit: `max_tool_output` generate option (docs: [Output Size](https://inspect.aisi.org.uk/tools-custom.html#sec-tool-output-size)).

```python
from inspect_ai.tool import tool, ToolError
from inspect_ai.util import store_as

@tool
def transfer_funds():
    async def execute(from_account: str, to_account: str, amount: float) -> str:
        """Move money between two accounts.

        Args:
            from_account: Source account id.
            to_account: Destination account id.
            amount: Amount in dollars.
        """
        sim = store_as(SimState)          # hidden state, see section 4
        if amount > sim.balances.get(from_account, 0):
            raise ToolError("Insufficient funds.")
        ...
        return "Transfer done."
    return execute
```

## 3. Agents

- Docs: [Agents](https://inspect.aisi.org.uk/agents.html), [ReAct agent](https://inspect.aisi.org.uk/react-agent.html), [Custom agents](https://inspect.aisi.org.uk/agent-custom.html), [Multi agent](https://inspect.aisi.org.uk/multi-agent.html), [Deep agent](https://inspect.aisi.org.uk/deepagent.html).
- Built-in agents in `inspect_ai.agent`: `react()`, `deepagent()` (+ `subagent()`, `research()`, `plan()`, `general()`), `human_cli()`.
- Helpers: `handoff()`, `as_tool()`, `as_solver()`, `run()`, `agent_with()`.
- `react()` params (0.3.291): `name, description, prompt, tools, model, attempts, submit, on_continue, retry_refusals, compaction, truncation, approval, review`.
  - `react` is built around "work until you call `submit()`". A business sim instead ends when the **sim clock** ends, so a **custom agent loop** fits better (below).
  - `react(truncation="auto")` only trims **after** the context window overflows (keeps ~70% of messages). It is **not** a fixed "last N tokens" window.
- For sub-agents and multi-agent design see [multiagent-and-subagents.md](multiagent-and-subagents.md).

### 3a. Recommended: custom agent loop + `CompactionTrim` (Vending-Bench-2 style)

- `CompactionTrim(threshold=..., preserve=..., memory=...)`:
  - `threshold`: **an int = absolute token count** (e.g. `30_000`), a float in 0..1 = fraction of the model's context window. Default `0.9`.
  - When input reaches the threshold, it keeps the system messages + the sample's first input messages + the newest `preserve` fraction of the other messages (default `0.8`). It never leaves an orphan tool result.
  - `memory=True` (default) adds a warning telling the model to save notes **if** the built-in `memory()` tool is present. Set `memory=False` if you don't want that extra hint (fairer benchmark).
- Why this is the best default:
  - It matches [Vending-Bench 2](https://andonlabs.com/evals/vending-bench-2): ~69k-token window, "keeping approximately 61% of messages".
  - It **keeps the prompt prefix stable between trims**, so provider prompt caching keeps working (big cost saving, see [models-and-pricing.md](models-and-pricing.md)).
  - The **full history is still in `state.messages` and in the log**. Only the model's input is trimmed.
- Tested on 0.3.291 with `mockllm`: with `threshold=400`, input grew 2→18 messages, one trim happened (back to 12), and system + task message were kept.

```python
from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.model import (ChatMessageUser, CompactionTrim, compaction,
                              execute_tools, get_model)

@agent
def bank_manager_agent(window_tokens: int = 30_000) -> Agent:
    async def execute(state: AgentState) -> AgentState:
        tools = [transfer_funds(), read_email(), wait_for_next_day()]
        compact = compaction(
            CompactionTrim(threshold=window_tokens, preserve=0.6, memory=False),
            prefix=state.messages,      # system prompt + task: always kept
            tools=tools,                # counted when measuring input size
        )
        while not store_as(SimState).done:          # the SIM decides when to stop
            input, c_msg = await compact.compact_input(state.messages)
            if c_msg:
                state.messages.append(c_msg)
            state.output = await get_model().generate(input, tools=tools)
            state.messages.append(state.output.message)
            await compact.record_output(input, state.output)  # calibrates token counts
            if state.output.message.tool_calls:
                messages, state.output = await execute_tools(state.messages, tools)
                state.messages.extend(messages)
            else:
                state.messages.append(ChatMessageUser(content="Continue your work."))
        return state
    return execute
```

- On overflow (`state.output.stop_reason == "model_length"`), docs say: call `compact.compact_input(state.messages, force=True)` and retry once. If you change or reorder old messages yourself, call `compact.reset(...)` ([docs](https://inspect.aisi.org.uk/agent-custom.html#compaction)).
- Other strategies in `inspect_ai.model`: `CompactionAuto` (provider-native, else summary), `CompactionNative`, `CompactionSummary` (an LLM summarises old history), `CompactionEdit` (clears old tool results/thinking). Docs: [Compaction](https://inspect.aisi.org.uk/compaction.html). For a fair benchmark, **Trim is the most predictable** (no extra model call, same for every model).

### 3b. Exact "last N tokens" window (Vending-Bench 1 style)

- [Vending-Bench 1](https://arxiv.org/abs/2502.15840) showed "the last N (30,000 in most of our experiments) tokens".
- You can do it yourself: before each `generate`, build `system + task + newest messages` that fit in N, measured with `await model.count_tokens(messages)` (exists on `Model` in 0.3.291). Drop leading `tool` messages so no tool result is orphaned.
- Tested on 0.3.291: works, full history still logged.
- **Downside:** the oldest message changes every turn, so the prompt prefix changes every turn and **prompt caching mostly stops working**. This can cost several times more. Also: pin the system + first task message, or the model forgets its job.
- `trim_messages(messages, preserve=0.7)` is a helper too. Note: it is **async** (`await trim_messages(...)`), even though one docs snippet shows it without `await`.

## 4. Hidden simulation state: `store` / `StoreModel`

- Docs: [Sample store](https://inspect.aisi.org.uk/agent-custom.html#agent-store).
- `store()` returns a per-sample key/value `Store`. Better: a typed `StoreModel` (it is a Pydantic `BaseModel`) read with `store_as(MyState)` from tools, agents and scorers. Scorers can also use `state.store_as(MyState)`.
- The model never sees the store unless a tool returns it. So put "true books", hidden fraud flags, etc. there.
- Every change is logged as a `StoreEvent` in the transcript. `store_from_events_as(events, MyState)` rebuilds the state from a log's events.
- Tested: tool wrote `SimState.day/cash`, scorer read them, and the final store appeared in `EvalSample.store`.
- Tip: keep the **real engine as a plain Python object** (see [project-structure-patterns.md](project-structure-patterns.md)) and keep only a small summary (or a serialised snapshot) in the `StoreModel`. Big Pydantic objects in the store make big logs.

```python
from pydantic import Field
from inspect_ai.util import StoreModel

class SimState(StoreModel):
    day: int = 0
    done: bool = False
    true_cash: float = 0.0
    violations: list[str] = Field(default_factory=list)
```

## 5. Seeding, epochs, repeats

- Seeds: put `seed` in `Sample.metadata`. For repeated runs combine it with `state.epoch` (1-based) if you want different worlds per epoch, or keep it fixed for "same world, different model sampling".
- `epochs=Epochs(5, ["mean"])` repeats each sample. Built-in reducers: `mean`, `median`, `mode`, `majority`, `max`, `pass_at_<k>` (e.g. `"pass_at_5"`), and more ([Reducing epochs](https://inspect.aisi.org.uk/metrics.html#reducing-epochs)).
- Model sampling seed: `GenerateConfig(seed=...)` / `--seed` (only some providers honor it, e.g. OpenAI, Google, Groq, Mistral). LLM output is **never** fully deterministic. Only your engine is.
- Many configs: `eval_set(...)` / `inspect eval-set` with retries ([Eval sets](https://inspect.aisi.org.uk/eval-sets.html)).

## 6. Model roles (cheap model for simulated people)

- Docs: [Model roles](https://inspect.aisi.org.uk/models.html#model-roles).
- Bind roles in `Task(model_roles={"customer": "openrouter/deepseek/deepseek-v4.1-flash"})`, in `eval(model_roles=...)`, or on the CLI: `--model-role customer=anthropic/claude-haiku-5-5`.
- Use it **inside** a tool/solver/scorer (not at import time): `get_model(role="customer")`. If the role is not bound, you get the main model, or `get_model(role="customer", default="...")`.
- Roles are recorded in the log: each `ModelEvent` has `.role`, and usage is split per role in `EvalSample.role_usage` and `EvalStats.role_usage`. Tested: the agent's cost and the "customer" role's cost were reported separately.
- Real examples in inspect_evals: `tau2` uses `get_model(role="user")` for the simulated customer (and has a **banking** domain), and `make_me_pay` uses roles `conartist` and `mark`.

```python
customer = get_model(role="customer")
reply = await customer.generate(f"You are {persona}. Reply to: {email_body}")
return reply.completion
```

## 7. Limits

- Docs: [Setting limits](https://inspect.aisi.org.uk/setting-limits.html).
- Per sample (Task, `eval()` or CLI): `message_limit`, `token_limit`, `turn_limit` (model generations), `time_limit`, `working_limit`, `cost_limit` (dollars).
- `token_limit` can be a formula, e.g. `"(input*0.1)+output:500k"`.
- Scoped limits in code: `with token_limit(100_000): ...`, also `message_limit()`, `turn_limit()`, `cost_limit()` from `inspect_ai.util`. Sub-agent limits: `handoff(agent, limits=[...])`, `as_tool(agent, limits=[...])`, `run(agent, input, limits=[...])`.
- When a sample limit hits, the sample stops and is **still scored**.
- Warning from the docs: truncation/compaction can keep the message count low, so a `message_limit` may never trigger. Use `turn_limit` or `cost_limit` as the hard stop.

## 8. Cost tracking

- Every model call records `ModelUsage`: `input_tokens, output_tokens, total_tokens, input_tokens_cache_write, input_tokens_cache_read, reasoning_tokens, total_cost`.
- `total_cost` is filled only if you give prices (dollars per **million** tokens):
  - Python: `set_model_cost("anthropic/claude-haiku-5-5", ModelCost(input=0.10, output=0.50, input_cache_write=0.125, input_cache_read=0.01))`.
  - CLI: `--model-cost-config pricing.yaml` (YAML/JSON, same four fields per model).
  - Gotcha (tested): `set_model_cost()` only accepts models in Inspect's model database. For others (e.g. `openrouter/deepseek/deepseek-v4.1-flash`) use `set_model_info(name, ModelInfo(cost=ModelCost(...)))`.
- `cost_limit` / `--cost-limit 2.00` stops a sample at a dollar budget (needs cost data for **every** model used, including role models).
- Built-in model info has context lengths but **no prices** (checked: `get_model_info(...).cost` is `None`), so you must supply prices.

## 9. Logs: what is recorded and how to read them

- Docs: [Log files](https://inspect.aisi.org.uk/eval-logs.html), [Log viewer](https://inspect.aisi.org.uk/log-viewer.html), [Dataframes](https://inspect.aisi.org.uk/dataframe.html).
- Format: `.eval` (default, compressed binary, ~1/8 the size of `.json`, loads samples one at a time). Written to `./logs` (or `--log-dir`, `INSPECT_LOG_DIR`).
- What's in each `EvalSample`: `messages` (full history, not the trimmed input), `output`, `scores`, `metadata`, `store` (final), `events`, `model_usage`, `role_usage`, `total_time`, `working_time`, `turn_count`, `limit`, `error`.
- `events` include `ModelEvent` (exact `input` the model saw, `output` with `usage`, `role`, `cache`), `ToolEvent` (function, arguments, result, error), `StoreEvent` (state changes), `CompactionEvent`, `SampleLimitEvent`, `InfoEvent`, `ScoreEvent`.
- Log your own sim events into the transcript: `transcript().info(data, source="sim")` (from `inspect_ai.log`).
- Header-level `EvalLog.stats.model_usage` and `stats.role_usage` give totals per model / per role.
- `inspect view` opens a web viewer (also a VS Code extension). `inspect log dump file.eval` prints JSON.
- Python reading:

```python
from inspect_ai.log import read_eval_log, read_eval_log_samples
from inspect_ai.analysis import samples_df, events_df

log = read_eval_log("logs/xxx.eval", header_only=True)   # fast: stats + results
print(log.stats.model_usage, log.stats.role_usage)
for s in read_eval_log_samples("logs/xxx.eval"):         # one sample at a time
    tool_calls = [e for e in s.events if e.event == "tool"]
df = samples_df("logs/")                                 # pandas, one row per sample
```

- Scorers that "read the logs": during scoring the transcript is live, but the simplest robust design is: **the engine keeps its own event list** and the scorer reads it from the store / engine. You can also re-score old logs offline with `inspect score` without re-running models.

## 10. Concurrency

- Docs: [Parallelism](https://inspect.aisi.org.uk/parallelism.html), [Model concurrency](https://inspect.aisi.org.uk/models-concurrency.html).
- `max_connections` (per model API) and `max_samples` (samples at once). Default is **adaptive connections**. A long-horizon run is sequential inside, so run many seeds/epochs side by side with `max_samples`.
- `max_samples` also controls how often samples are flushed to the log. A crash loses at most the in-flight samples. Retry with `inspect eval-retry`.

## 11. Providers (cheap models, OpenRouter)

- Docs: [Providers](https://inspect.aisi.org.uk/providers.html). Model names are `provider/model`, e.g. `anthropic/claude-haiku-5-5`, `openai/gpt-6-luna`, `google/gemini-3.8-flash`, `deepseek/deepseek-flash`, `openrouter/qwen/qwen3.8-flash`.
- OpenRouter: `pip install openai`, set `OPENROUTER_API_KEY`, use `openrouter/<vendor>/<model>`. Model args: `-M models=...` (fallbacks), `-M provider={...}` (pick/sort providers, quantization), `-M transforms=...`, `-M reasoning_enabled=false`.
- The OpenRouter provider (source, 0.3.291) sends an `x-session-id` per sample, so OpenRouter keeps the same upstream provider and the cache stays warm. For `openrouter/anthropic/*` it adds Anthropic `cache_control` breakpoints automatically.
- Free local testing: `mockllm/model` with `custom_outputs=` (tested; it still logs usage and cost).

## 12. Caching

- **Inspect output cache** (replay identical calls for free): `GenerateConfig(cache=True)` / `--cache 1W`, or `CachePolicy(expiry="1W", per_epoch=True, scopes={...})`. The key includes model, prompt, epoch, config and tools. Manage with `inspect cache list|clear|prune`. Useful when you re-run after fixing a bug in later days of the sim. Earlier identical turns are served from disk.
- **Provider prompt caching** (cheaper repeated prefixes): `cache_prompt` option (`auto`/true/false). Inspect places Anthropic breakpoints itself (system, tools, up to last user message). OpenAI/DeepSeek/Gemini cache automatically. Usage shows `CW` (cache write) and `CR` (cache read) tokens ([docs](https://inspect.aisi.org.uk/caching.html)).
- **Batch mode** (`--batch`, ~50% off) exists for OpenAI, Anthropic, Google, xAI and Together. The docs warn it is a **bad fit for agent loops**: each turn waits for a batch, so a 300-turn run could take days ([docs](https://inspect.aisi.org.uk/models-batch.html)). Skip it for the main agent.

## 13. Other things in inspect that may help

- `inspect_ai.tool.memory()`: a built-in file-like memory tool stored in the sample store (no sandbox). See [memory-tools.md](memory-tools.md).
- `checkpoint=` on `Task`/`eval` (checkpointing long runs, [docs](https://inspect.aisi.org.uk/checkpointing.html)). Not tested here.
- `span("day-12")` (from `inspect_ai.util`) groups events per sim day in the viewer.
