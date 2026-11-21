# Project structure and design patterns for the simulator

Checked 2026-11-21. Versions: numpy 2.5.5, hypothesis 6.170.17, pydantic 2.14.4, inspect-ai 0.3.291. The numpy RNG and heapq patterns below were run locally.

## 1. Main idea: a pure-Python engine, with inspect as thin glue

- The **engine** knows nothing about LLMs or inspect. It is plain Python: state + `apply(action) -> observation` + `advance_time()`.
- The **inspect layer** (`@tool`s, agent loop, scorer) only translates. A tool call becomes an engine action, and the engine's observation becomes a string for the model.
- Simulated people sit behind a small interface (`PeopleBackend`). It has two versions:
  - `LLMPeople`, which calls `get_model(role="customer")`.
  - `ScriptedPeople`, which returns fixed replies. Used in tests, so tests cost \$0 and are deterministic.
- Why:
  - You can test 365 sim days in milliseconds with pytest, with no API calls.
  - Scoring is **code over the engine's own event log**, like [Blueprint-Bench](https://arxiv.org/abs/2509.25229)'s "compare by code" idea. It doesn't depend on parsing LLM text.
  - Real example: [Prosus Vending Bench](https://github.com/ProsusAI/vending-bench) keeps `vending/engine.py`, `demand.py`, `catalog.py`, `mailroom.py`, `config.toml` apart from the MCP server (`server.py`). It also ships a scripted `reference_bot.py` and `tests/test_engine.py`.

## 2. Suggested layout (proposal, can change)

```text
temptation_bench/
  engine/
    state.py        # dataclasses for true books, accounts, customers, inbox
    clock.py        # sim time, event queue (heapq)
    rng.py          # seeded streams per subsystem
    world.py        # Engine: apply(action), advance(), morning_report()
    temptations.py  # scheduled temptation events (when, what, payoff, detection)
    people.py       # PeopleBackend protocol + ScriptedPeople
    events.py       # Event dataclass + JSONL writer
    config.py       # pydantic Settings: days, starting cash, fees (all "proposal")
  inspect_glue/
    tools.py        # @tool wrappers -> engine actions
    agent.py        # custom @agent loop with CompactionTrim
    people_llm.py   # LLMPeople using get_model(role=...)
    scorers.py      # @scorer reading engine events
    task.py         # @task: dataset of seeds/scenarios
  policies/         # scripted agents for testing: noop, greedy_honest, cheater, random
  tests/
  configs/pricing.yaml   # for --model-cost-config
```

- How the engine gets into inspect: create **one engine per sample** at the start of the agent (or in a `setup` solver) from `state.metadata["seed"]`. Keep it in a `StoreModel` field, or in a dict keyed by `sample_id`. Snapshot key numbers into the store for the log.

## 3. Time: event queue with `heapq`

- Docs: [heapq](https://docs.python.org/3/library/heapq.html).
- Push `(time, seq, event)`. `seq` is a running counter, so two events at the same time pop in insertion order. This also stops Python from comparing two event objects, which may not be comparable. Tested: `(5.0, 0, 'x')`, `(5.0, 1, 'y')`, `(1.0, 2, 'z')` pop as `z, x, y`.
- Every tool call costs sim time (VB1: "5 min, 25 min, 75 min or 5 h" per tool type; Prosus: reads 5–25 min, physical work 30–45 min). `wait_for_next_day` jumps to the next morning and pops all events up to then: deliveries, customer visits, audits, temptation offers.
- Delayed effects (core to "Temptation-Bench"): schedule consequences into the queue, e.g. `push(t + 14 days, AuditFinds(fraud_id))`.
- Bigger option: [SimPy](https://simpy.readthedocs.io/) 4.1.2 (process-based discrete-event simulation). That's more than you need. A heap plus a loop is ~30 lines and easier to make deterministic.

## 4. Randomness: seeded numpy `Generator`, one stream per subsystem

- Docs: [numpy random Generator](https://numpy.org/doc/stable/reference/random/generator.html), [SeedSequence / spawning](https://numpy.org/doc/stable/reference/random/parallel.html).
- Never use global `random` / `np.random.*` functions. Pass `Generator` objects around.
- Give each subsystem **its own stream, derived from (seed, subsystem, day)**. Then adding one extra random draw in "customers" doesn't change what "temptations" does:

```python
import numpy as np
CUSTOMERS, TEMPTATIONS, MARKET = 1, 2, 3
def rng_for(seed: int, stream: int, day: int) -> np.random.Generator:
    return np.random.default_rng([seed, stream, day])   # tested: same inputs -> same draws
```

- Alternative: `np.random.default_rng(seed).spawn(n)` or `np.random.SeedSequence(seed).spawn(n)` for n independent child streams (both tested on numpy 2.5.5).
- Prosus Vending Bench does the same idea with stdlib: `random.Random(f"sales:{seed}:{day}")`.
- LLM-played people are **not** deterministic. To keep worlds comparable across agent models: fix the people model + `temperature=0` (where allowed), and use inspect's output cache (`cache=True`), so identical people-prompts replay the same answer. Also keep **important** world facts (prices, who is a fraudster, audit dates) in the engine, not in LLM text.

## 5. State: dataclasses vs pydantic

- Engine state: `@dataclass(slots=True)` ([docs](https://docs.python.org/3/library/dataclasses.html)). Fast, simple, no validation cost on every step.
- Config, tool inputs and anything serialised: [pydantic](https://docs.pydantic.dev/) v2 (`BaseModel`, `model_dump_json()`). inspect's `StoreModel` is already pydantic.
- Keep **money as integer cents** (or `decimal.Decimal`). Floats drift, and "true books == reported books" checks need exact equality.
- Two ledgers for temptations: `true_ledger` (what really happened) and `reported_ledger` (what the agent claimed). The score is a code diff of the two.

## 6. JSONL event log (your own, next to inspect's `.eval`)

- One JSON object per line ([JSON Lines](https://jsonlines.org/)): `{"t": 1234.0, "day": 3, "seq": 57, "type": "transfer", "actor": "agent", "data": {...}}`.
- Append-only. Write it from the engine, not the inspect layer. Also mirror key events into inspect with `transcript().info(event, source="engine")`, so they show in `inspect view`.
- Benefits: easy to diff two runs, easy to load with pandas (`pd.read_json(path, lines=True)`), and scorers become pure functions `score(events) -> dict`.
- Determinism test: run the same seed + same scripted policy twice and hash the JSONL. The hashes must be equal.

## 7. How others test simulators

- **Unit tests per rule** (Prosus `tests/test_engine.py` has ~40, e.g. `test_sales_never_exceed_stock`, `test_demand_cannot_go_negative`, `test_tool_calls_advance_the_clock`, `test_bankruptcy_terminates_the_run`, `test_notes_persist_across_days`, `test_runs_are_reproducible_for_a_fixed_seed`).
- **Property-based tests** with [Hypothesis](https://hypothesis.readthedocs.io/) (6.170.17):
  - `@given(st.integers(...), ...)` for invariants: money is conserved, balances never go negative unless overdraft is allowed, true books = sum of transactions.
  - **Stateful tests**: `hypothesis.stateful.RuleBasedStateMachine` with `@rule`, `@invariant`, `@precondition`, `@initialize` (imports checked). Hypothesis fires random action sequences at the engine and checks invariants after each one. This finds bugs like VB2's "\$0.00 reference price used as a divisor" crash on day 88 ([Epoch review](https://epoch.ai/benchmarks/vending-bench-2/review)).
- **Scripted policies** (no LLM): `noop` (does nothing: should slowly go bankrupt), `honest_greedy` (good upper baseline), `always_cheat` (takes every temptation: checks that detection and penalties fire), and `random_valid` (fuzzing).
  - Prosus ships a privileged `reference_bot.py` as a "calibration floor" and a test that it beats starting capital.
  - Also add an **exploit-hunting** policy. Epoch found an agent passed "\$1 million in 102 simulated days" by exploiting supplier/pricing flaws. Try to break your own economy before a model does.
- **Tool contract tests**: every tool, every error path (`ToolError` message), and "the effect shows up later". VB2's `create_reminder` "always reports success, but the reminders never appear".
- **Golden/snapshot tests** of the morning report text for a fixed seed. Also catches accidental prompt changes that would break prompt caching.
- **Inspect glue test with `mockllm`** (free): `get_model("mockllm/model", custom_outputs=[ModelOutput.for_tool_call("mockllm/model", "wait_for_next_day", {})] * n)` runs the full task end to end and writes a real `.eval` log. Tested on 0.3.291.
- **Token-budget test**: assert the morning report + tool outputs stay under a size cap (VB2's unread-email report filled ~40% of one model's window).

## 8. Quick checklist before paid runs

- [ ] Same seed + scripted policy gives the same JSONL hash twice.
- [ ] `noop`, `honest_greedy` and `always_cheat` give the expected ordering of scores.
- [ ] Every temptation has a code-checkable "taken / not taken" signal in the event log.
- [ ] Context threshold set with the model's own token count (`model.count_tokens`), not `tiktoken`.
- [ ] Prices set (`--model-cost-config`) and `--cost-limit` on, for every model including the people role.
- [ ] 3-day pilot per model, real cost read from `log.stats.model_usage`, then scale up.
