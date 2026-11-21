# Multi-agent and sub-agents (main agent + "physical world" sub-agent)

Checked 2026-11-21 against `inspect-ai` 0.3.291 (installed, signatures printed) and GitHub.

## 1. Andon Labs `multiagent-inspect`: archived, don't use

- Repo: <https://github.com/AndonLabs/multiagent-inspect>
- Status (GitHub API, 2026-11-21): **archived = true**. Last commit 2025-02-05 ("2k messages limit"). PyPI `multiagent-inspect` 0.0.7, uploaded 2025-02-05. Apache-2.0. 24 stars.
- What it did: `init_sub_agents([SubAgentConfig(...)])` gave the main agent 3 tools: `sub_agent_specs`, `run_sub_agent`, `chat_with_sub_agent`. It plugged into the old `basic_agent(init=...)` solver.
- This is the tool set [Vending-Bench 1](https://arxiv.org/abs/2502.15840) used for its sub-agent (stocking, collecting cash, setting prices, reading machine inventory).
- It was written for inspect ~0.3.6x (early 2025). Inspect has changed a lot since then (the Agent API, `react`, compaction). Expect breakage, and don't depend on it.

## 2. Built-in replacements in inspect 0.3.291

All in `inspect_ai.agent` unless noted ([Multi agent docs](https://inspect.aisi.org.uk/multi-agent.html), [Deep agent docs](https://inspect.aisi.org.uk/deepagent.html)).

| Need | Built-in | Notes |
|---|---|---|
| Sub-agent as a tool (string in, string out) | `as_tool(agent, description=None, limits=[], max_output=0)` | Sub-agent sees **only** the input string. It returns its last assistant message. Closest to `run_sub_agent`. |
| Hand the whole conversation to another agent | `handoff(agent, description=None, input_filter=None, output_filter=content_only, tool_name=None, limits=[])` | Shown to the model as `transfer_to_<name>`. Sub-agent sees shared history. Filters: `remove_tools`, `last_message`, `content_only`. |
| Code-driven workflow | `await run(agent, input, limits=[...])` | Copies the input. Returns a new `AgentState` (or `(state, LimitExceededError)` when limits are given). |
| Batteries-included long-horizon agent | `deepagent(tools=..., subagents=[...], memory=True, todo_write=True, compaction="auto", ...)` | Gives an `agent()` delegation tool, built-in `research()`, `plan()`, `general()` sub-agents, a `memory()` tool, `todo_write()`, and an opinionated system prompt. |
| Define a custom sub-agent for `deepagent` | `subagent(name=, description=, prompt=, tools=, model=, fork=False, memory=False, limits=, compaction=)` | `model=` can be a cheaper model. `memory="readwrite"/"readonly"` shares the parent's memory. |
| Give each agent its own tool state | `inspect_ai.util.tool_state_scope()` | Otherwise agents in one sample share `memory()` and similar tools. |

- So yes: **inspect now has built-in sub-agent support that replaces multiagent-inspect.** The one feature not built in is `chat_with_sub_agent` (asking the sub-agent questions afterwards). You can rebuild it in ~30 lines: keep the sub-agent's `AgentState` in a `StoreModel` and call `run()` again on it.

## 3. Recommendation for a bank-branch sim (solo, small budget)

- **Start with one agent, no sub-agent.** The inspect docs say multi-agent setups "often don't out-perform simple `react()` agents". Measure against a single-agent baseline first ([Methodology](https://inspect.aisi.org.uk/multi-agent.html#methodology)).
- The deepagent docs also say: on shorter hard benchmarks they "do not observe performance differences between the `react()`, `deepagent()`, and `claude_code()` agents".
- If you want the Vending-Bench "physical world" split (e.g. a teller sub-agent that counts cash or moves boxes):
  - Write the sub-agent as a small custom `@agent` (or `react(name=..., description=..., tools=[...])`) with only the "physical" tools.
  - Expose it with `as_tool(teller_agent, limits=[turn_limit(10)])`. This copies VB1's `run_sub_agent` and is easy to log and score.
  - Each sub-agent call shows up as a nested span in the log, with its own `ModelEvent`s.
- **Don't use `deepagent()` for the benchmark agent**, because:
  - Its system prompt, auto-compaction and memory nudges change behaviour in ways that differ by model. That makes the results harder to read.
  - VB2's lesson ([Epoch review](https://epoch.ai/benchmarks/vending-bench-2/review)) is that harness details (context counting, auto-compaction) change scores a lot: +17% for one model, −44% for another.
- Simulated people (customers, auditors, regional manager) are **not agents in this sense**. They are plain `get_model(role="customer").generate(...)` calls made inside your tools or engine hooks. See [inspect-ai.md § Model roles](inspect-ai.md#6-model-roles-cheap-model-for-simulated-people).

## 4. Example: VB1-style sub-agent with built-ins

```python
from inspect_ai.agent import as_tool, react
from inspect_ai.util import turn_limit

teller = react(
    name="teller",
    description="Branch teller who performs physical actions in the branch.",
    prompt="You are the branch teller. Do exactly what the manager asks.",
    tools=[count_vault_cash(), move_cash_to_atm()],
)
teller_tool = as_tool(teller, limits=[turn_limit(10)])
# give teller_tool to the main (manager) agent's tool list
```

- Note: `react()` sub-agents end with a `submit()` call by default. That is fine for a bounded sub-task.
