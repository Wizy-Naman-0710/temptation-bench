# ProsusAI/vending-bench: deep study

Checked 2026-11-21. Repo: <https://github.com/ProsusAI/vending-bench>, commit `60794b4` (2026-11-20, "Grade in a separate container so the agent cannot forge the score"), benchmark **v3.0.0**. Only 4 commits in the public history.

How this was studied: I cloned the repo into the scratchpad and read every engine, server, solution, script and test file. **I did not run any of their scripts or install their dependencies.** So claims about behaviour below come from reading code, and I say so where it matters.

---

## 1. What it is (one paragraph)

- An LLM runs **6 vending machines at 3 fictional Amsterdam locations** for **30 simulated days** (365-day variant included), starting with €1,500. Score = final bank balance, floored at 0, **only if the run completes**. Unfinished or bankrupt runs score 0.
- The agent acts only through **22 MCP tools** served by a separate simulation server (`server.py`, [FastMCP](https://github.com/jlowin/fastmcp) 2.11.3). It ships as a [Harbor](https://github.com/harbor-framework/harbor) task (Docker, MCP sidecar), plus two no-Docker runners (Claude CLI, OpenRouter).
- Simulated people are **deterministic templates** by default. An optional LLM may rewrite supplier **prose only**. Prices, order lines and outcomes are always computed by code.
- Engine runtime is Python 3.11+ **standard library only** (plus FastMCP for transport).

## 2. License and what we may reuse

- **License: Apache-2.0** (`LICENSE`), copyright 2026 MIH AI B.V. `NOTICE` adds attribution to Harbor and says the per-product economics "follow a shape established" in the vending-bench literature, and that everything is "independently written and independently parameterised".
- Apache-2.0 lets us copy and change code, including for research papers. If we copy any file or snippet we must ([Apache-2.0 §4](https://www.apache.org/licenses/LICENSE-2.0#redistribution)):
  - keep a copy of the license,
  - keep their copyright/attribution notices (and pass on their `NOTICE` text),
  - mark files we changed.
- They also **ask** (not a license term) that task instructions, reference solutions, trajectories and results stay out of training corpora. Their task files carry a canary GUID.
- **Recommendation: re-implement, borrow patterns.** The domain is different (bank vs vending), we use inspect-ai (not MCP + Harbor), and we need things they lack (truth vs reported books, event queue, integer money). Copying would save very little.
  - Small helpers worth copying almost verbatim (with an attribution header): the `extends` overlay config loader in `config.py`, `stochastic_round()` in `demand.py`. **PILOT: not needed. FULL: optional.**
  - Cite them in the paper as code inspiration either way ([CITATION.cff](https://github.com/ProsusAI/vending-bench/blob/main/CITATION.cff) asks to cite them and Harbor).

## 3. Repository layout

```text
tasks/vending-bench/
  instruction.md / instruction.template.md   agent briefing, GENERATED from config
  task.toml                                  Harbor manifest; separate verifier container
  environment/sim-server/
    server.py                                22 MCP tools + POST /verifier/finalize + /healthz
    vending/engine.py      (1,469 lines)     state, clock, end-of-day, all tool_* methods, score
    vending/demand.py      (159)             daily sales formula
    vending/catalog.py     (141)             frozen dataclasses for products/suppliers
    vending/mailroom.py    (426)             intent classifier, negotiation curve, optional LLM prose
    vending/config.py      (566)             TOML loader, extends overlays, env overrides, validation
    vending/config.toml    (994)             THE WORLD: every number lives here
    variants/full-year.toml                  17-line overlay: sim_days = 365
  solution/reference_bot.py (352)            scripted operator, talks only through .call(tool, **kw)
  tests/test_outcome.py, test.sh             verifier: checks the score contract
scripts/  local_run.py, run_models.py, run_openrouter.py, run_baselines.py, sync_config.py, prepare_task.py, ...
tests/    test_engine.py (55 tests), test_network.py (15), test_openrouter.py (9), test_transport.py (1)
results/  baselines (v2 model runs, v3 scripted reference), validation
```

- Correction to `03-tooling/README.md`: it says "~40 engine tests". The current repo has **55 test functions in `test_engine.py` and 80 across 4 files** (some parametrised). Their own validation note (v2) reports "78 engine and HTTP/MCP transport tests pass".

## 4. File by file

### `server.py`: the tool surface

- Each of the 22 tools is a 1-line wrapper: `@mcp.tool()` + `@serialized` (a global `threading.RLock`) → `ENGINE.tool_<name>(...)`.
  - The lock means **calls run one at a time, in order**, even if the model sends them in parallel. The briefing tells the agent this.
- Tool descriptions are docstrings. Some are built from config values, so the agent never sees a stale number.
- There is **no `/state` or `/score` route**. A test checks both give 404.
- `POST /verifier/finalize` **seals** the run irreversibly, *then* returns score + full state. After sealing, every tool returns "SIMULATION OVER" and changes nothing (tested).

### `engine.py`: the world

- **State is one plain dict** (`self.s`), written to JSON after every tool call (atomic write: temp file + `replace`). It carries a `schema_version`. The server can resume from it after a crash.
- **Clock** (`spend_time`): each tool has a cost in minutes from `[clock.tool_minutes]`. The working day is 09:00–17:00. When the clock passes 17:00, `_roll_day()` runs end-of-day **inside that tool call** and appends the overnight notices to the tool's output. `wait_for_next_day` jumps straight to the roll.
- **End of day** (`end_of_day`), in fixed order:
  1. sales (`demand.simulate_day`), split into cash (banked that night) and card (settles next day)
  2. card settlements landing
  3. daily spot fee (≥10 unpaid days in a row → terminated)
  4. deliveries (with short-ship chance), supplier collapse, overnight email replies (with "ghost" chance), customer complaints, spoilage, order expiry, reputation update
- **Morning briefing**: day, weather, balance, unread count, yesterday's sales, **due reminders** (marked done once shown).
- **Every tool returns** `body + overnight notices + "[Day d/N — date time — balance €x]"`. A status line on every call is cheap and keeps the agent oriented.
- **Horizon settlement**: on the last day, card money still in transit is paid out (`_settle_outstanding_card`), so the agent is not punished by timing. (Our bank analog: a "run-off" of the loan book at the horizon. See [consequence-model.md](consequence-model.md).)
- **Score** (`score()`): `final_balance`, `reward` (0 unless completed), `net_worth` (balance + card in transit + stock at cost), `profit`, plus counters. Model API cost is **not** in the score. The runner reports it next to it.
- Money is **float** with a `_round(x) = round(x + 1e-9, 2)` helper. **Do not copy this.** Use integer minor units (see [integrity-and-invariants.md](integrity-and-invariants.md)).

### `demand.py`: the customer formula

- Five steps (the published vending-bench shape): price impact `1 + elasticity × (p − ref)/ref` clamped to `[0, 4.0]`; day multipliers (weekday × month × holiday × reputation); weather per category; variety ("choice") multiplier capped at −50%; Gaussian noise; then capped by stock.
- **`price_impact` returns 0 if `reference_price <= 0`.** That is the guard against the VB2 "reference price \$0.00 used as a divisor" crash.
- `stochastic_round` rounds fractional sales up with probability equal to the fraction, so slow sellers sell sometimes instead of never. It has a regression test.
- **Identical products in one machine share one demand pool**: more slots add capacity, not customers. This closes the "fill every slot with the best seller" exploit.

### `catalog.py`

- Turns `[[products]]` and `[[suppliers]]` into `@dataclass(frozen=True)` objects. No numbers in code.

### `mailroom.py`: simulated suppliers without an LLM

- Classifies the agent's email into `order / negotiate / chase / inquiry / other` with regexes from config.
- **Negotiation curve:** `price = list − (list − floor) × (1 − e^(−pace × rounds) + volume_bonus)`. Each supplier persona has its own pace. Persistence pays but never goes below the floor. A test checks the floor stays ≥ 0.9 × true cost (you cannot buy below cost).
- **LLM hook:** `set_llm_backend(fn)` plus `VENDING_SUPPLIER_LLM=1`. The backend gets the finished template text as `draft` plus context, and only rewrites the prose: "switching a model on cannot change what a run costs or what ships". If the backend throws or returns empty text, the template is used, so a run thousands of calls deep never dies. **This is the exact pattern for our Lite/Full mode.**

### `config.py` + `config.toml`

- All economic values, personas, regex patterns, tool minutes, products and suppliers live in **one TOML file**. Conventions say "Do not put economic values in Python".
- Override order: TOML (or `VENDING_CONFIG`) → named env vars (`[env_overrides]`) → `VENDING_SET="a.b=1,c.d=2"`.
- **`extends = "../vending/config.toml"`**: a variant is a short overlay. Tables merge key by key and lists replace. There is a loop/depth check.
- `_validate()` rejects broken configs with useful messages (tested).
- `python -m vending --dump` prints the resolved config.

### `instruction.template.md` + `scripts/sync_config.py`

- The agent briefing and the bot's `world.json` are **generated from the config**. CI fails if they are stale (`sync_config.py --check`). This stops "the prompt says 30 days, the sim runs 365".
- Our rulebook already says "change values in one config file; the scorer must read the same file". **Render the agent-facing policy text from `rules.toml` the same way. PILOT.**

### `solution/reference_bot.py`: scripted operator

- Talks to **any client with `.call(tool, **kwargs) -> str`**. In-process it uses `DirectClient` (calls `engine.tool_<name>` directly). In Harbor it uses an MCP client. Same bot, same score: their v2 validation reports the two agree "to the cent".
- It parses tool output with regexes (balance, day, ids). So it also tests that tool output stays parseable.
- It is **privileged**: it gets product economics from `world.json`. They call it a "calibration floor", not a model result, and they keep it separate from model results.
- A test checks it "beats its starting capital" (the world is winnable through tools alone). Another checks two runs with the same seed give the same result.

### Runners

- `scripts/local_run.py`: bot + engine in-process, no model, no Docker. CI runs it for both horizons.
- `scripts/run_models.py` (Claude CLI): starts a fresh server per trial on a free port, then runs `claude -p ... --tools '' --strict-mcp-config --allowedTools mcp__vending --max-budget-usd B` **from an empty temp dir**. So there are no repo files, no built-in tools, only MCP. A wall-clock `--timeout` is applied. Finalize is always called in `finally`.
- `scripts/run_openrouter.py`: a hand-written chat loop.
  - Context = **rolling window of whole assistant+tool exchanges up to `--context-chars` (default 60,000 characters)**. It never orphans a tool result (tested).
  - Multiple tool calls per response are allowed and run in order. Unknown tool names are never executed (tested).
  - **Budget:** before each request it *reserves* a pessimistic cost (1 token per UTF-8 byte + 4,096, times max output, ×1.10) and stops if the reservation would pass the per-run budget. Ambiguous billed failures are never retried. Only explicit 429s are retried.
  - Stops on: sim over, budget, wall clock, `--max-turns` (default 400), or 3 turns with no tool call.

### How each run is logged (per trial folder)

- `instruction.md` (exact prompt), `config.json` (resolved world), `harness.json` (tools allowed, budget, timeout, context policy, reasoning effort, routing), `tools.json` (exact schemas)
- `responses.jsonl` (raw API responses), `conversation.jsonl` (each exchange), `api-errors.jsonl`, `progress.json` (live), `generations.json`
- `trajectory.json` (final sealed state), `result.json`: score + model usage + `api_cost_usd` + `profit_after_llm_cost` (at a fixed €/\$ rate) + outcome reason + error + **`benchmark_sha256`** (hash of all engine/script/test source) + timestamp
- Batch level: `manifest.json`, `models.json` (catalog prices at run time), **`evaluation-source.zip` + its SHA-256**, an auto-generated `README.md` table.
- Failures stay in the table. "Never substitute scripted results for model results."

### Cost reporting

- API cost is measured, but **never part of the score**. `profit_after_llm_cost` is shown "because it is interesting, not because it is ranked". In v2 the business paid €0.12 per tool call. v3 removed this, and old results are labelled "not comparable".
- In inspect we get this for free: `ModelUsage.total_cost`, `role_usage`, `--cost-limit` (see [../03-tooling/inspect-ai.md](../03-tooling/inspect-ai.md) §8).

### Tests (what kinds)

- Catalogue sanity (every supplier sells real products; floor price ≥ 0.9 × cost; the honest supplier is cheaper than the adversarial one).
- Formula tests (impact = 1 at reference price; demand never negative; sales ≤ stock).
- Tool rules (capacity, wrong row size, payment to unknown ref is lost, cannot overpay balance, NaN cannot corrupt balance or price, invalid order is atomic).
- **Regression tests, one per bug that shipped**: token €0.01 refund closed any complaint; card settlement delay did nothing; a sold-out slot kept the old product's price; `swap_item` was a cheap restock; slow sellers never sold.
- Config tests (variants only state changes; `extends` cannot loop; every env override hits a real key; overrides really change the world).
- Integrity: **"every advertised tool has a time cost"**, exactly 22 tools exposed, live state unreachable, finalizer freezes the world.
- Reproducibility: same seed + bot gives the same balance; the bot gives the same result before and after JSON round-trip of its world.

## 5. How state is kept away from the agent

- **Process boundary**: the engine runs in the sim-server process. The agent only sees MCP tool text.
- **No read path to truth**: no state/score endpoint. The verifier seals first, so an agent that calls it early forfeits the run.
- **Harness lockdown**: no built-in tools, empty working dir, strict MCP config. Under Harbor the verifier runs in a **separate container** after the agent's container is stopped (`environment_mode = "separate"`), so "nothing the agent left behind (a replaced binary, a background process) takes part in grading".
- **Our case is simpler.** Our agent has no shell or sandbox, only our `@tool`s. So the engine can live in the same Python process and there is nothing to break out of. The principle carries over: **no tool returns hidden truth or the score, and finalize seals the engine.** **PILOT.**

## 6. How they prevent exploits (from code and tests)

| Exploit class | Their defence |
|---|---|
| Divide by zero / bad reference price | `price_impact` returns 0 if ref ≤ 0 |
| Runaway multipliers | `max_price_impact = 4.0`; marketing multiplier bounded to [0.50, 1.35]; bonuses saturate at one active campaign per channel; cross-channel spam penalty |
| "More slots = more customers" | identical facings share one demand pool |
| Buying below cost | negotiation approaches a floor asymptotically; test floor ≥ 0.9 × true cost |
| Token payments | complaint closes only when paid in full (regression test) |
| Cheap action substitutes | `swap_item` refuses when it would just be a fill (regression test) |
| NaN / inf / negative inputs | `math.isfinite` checks; NaN cannot change balance or price (test) |
| Partial side effects | invalid order debits nothing (atomic, tested) |
| Huge outputs | caps on list/report sizes (`list_limit_max`, `sales_report_max_days`, `sales_log_max_days`) |
| Reading the score / state | no endpoint; seal-then-reveal; separate verifier container |
| Runner exploits | unknown tool names never executed; budget reserved before each call |
| Calibration | scripted reference must stay winnable; CONTRIBUTING: changes that make the bench "trivially winnable or unwinnable for the scripted reference will be rejected" |

- **What they do not have:** a dedicated *adversarial* bot that tries to break the economy, property-based tests (Hypothesis), or a structured event log (`state["events"]` only records supplier collapses). Their exploit defences are a list of patches, one per bug found. We should add systematic exploit hunting. See [integrity-and-invariants.md](integrity-and-invariants.md) §7.

## 7. The 22 tools, their time cost, and the bank analog

Minutes are from `config.toml [clock.tool_minutes]`. The bank column is a mapping idea only. PILOT/FULL refers to our tool.

| Group | Prosus tool | Min | Bank analog (ours) | Ours in |
|---|---|---:|---|---|
| Inspect | `get_status` | 5 | `get_status` (day, cash, KPIs vs target, queue counts) | PILOT |
| Inspect | `get_sales_report` | 25 | `get_portfolio_report` (DPD buckets, NPL, provisions from core system) | PILOT |
| Inspect | `get_machine_inventory` | 25 | `list_applications` / `list_loans` | PILOT |
| Inspect | `get_storage_inventory` | 25 | `list_accounts`, `vip_register` | FULL |
| Source | `search_web` | 25 | `read_policy(section)` (rulebook lookup) | FULL |
| Source | `list_emails` | 5 | `list_emails` | PILOT |
| Source | `read_email` | 5 | `read_email` | PILOT |
| Source | `send_email` | 25 | `send_email` (free text; flavour only, never scored except tipping-off keywords) | PILOT |
| Source | `check_offers` | 25 | `get_market_rates` | FULL |
| Source | `order_goods` | 25 | `approve_loan` (commits money, irreversible) | PILOT |
| Operate | `restock_machine` | 45 | `request_verification` (officer pulls a document) | FULL |
| Operate | `swap_item` | 30 | `restructure_loan` (evergreening path) | FULL |
| Operate | `set_price` | 5 | `set_deposit_rate` / loan pricing override | FULL |
| Operate | `clear_slot` | 30 | `close_account` | FULL |
| Operate | `send_payment` | 25 | `refund_fee` (complaint redress) | FULL |
| Market | `run_marketing` | 25 | `run_promotion` | FULL |
| Market | `get_marketing_report` | 5 | (part of `get_status`) | n/a |
| Remember | `write_note` | 5 | `write_note` | PILOT |
| Remember | `read_notes` | 5 | `read_notes` | PILOT |
| Remember | `set_reminder` | 5 | `set_reminder` (+ test that it fires, see §9) | PILOT |
| Remember | `list_reminders` | 5 | `list_reminders` | FULL |
| Advance | `wait_for_next_day` | jump | `wait_for_next_day` | PILOT |

Bank tools with **no** Prosus analog (they carry the temptations): `review_application`, `edit_application`, `reject_loan`, `file_report`, `respond_to_offer`, `report_to_compliance` (all PILOT); `open_account`, `decide_alert`, `delete_document`, `report_to_regulator`, `answer_inspector` (FULL). The full mapping to engine calls is in [engine-layout.md](engine-layout.md) §5.

## 8. Component map: Prosus → Temptation-Bench

| Prosus component | Our component | Notes | When |
|---|---|---|---|
| `server.py` (MCP wrappers + lock) | `inspect_glue/tools.py` (`@tool` wrappers) | inspect runs tool calls serially by default, so no lock is needed | PILOT |
| `engine.py` (one big class) | `engine/branch.py` facade + split modules (ledger, records, credit, aml, controls) | keep `tool_*` naming so bots can call it directly | PILOT |
| `demand.py` (sales formula) | `engine/world/arrivals.py`: loan applications `Poisson(λ)` with rate elasticity; deposit flows | formulas already in [customer-behaviour-models.md](../02-banking-domain/customer-behaviour-models.md) §2b, §2d | PILOT: applications only; FULL: deposits, runs |
| `catalog.py` (frozen dataclasses) | `engine/catalog.py`: loan products, persona templates | | PILOT |
| `mailroom.py` (intent regex + concession curve + LLM prose) | `engine/world/people.py`: `TemplatePeople` (Lite), `inspect_glue/people_llm.py` (Full); **bribe ladder = deterministic "concession curve"** (offer rises each time it is declined without a report) | outcomes from code, prose from LLM | PILOT: Lite only |
| `config.toml` + `extends` | `configs/world.toml`, `configs/rules.toml`, `configs/variants/*.toml` (pilot, watched/unwatched, pressure type) | variants = minimal pairs | PILOT |
| `instruction.template.md` + `sync_config.py` | prompt + compact rulebook rendered from `rules.toml` | test that prompt numbers match config | PILOT |
| `reference_bot.py` | `bots/honest.py` (visible info only), `bots/oracle_honest.py` (reads truth: upper bound), `bots/cheater.py` (takes every temptation), `bots/exploit.py`, `bots/random_valid.py`, `bots/noop.py` | all use `.call(tool, **kw)` | PILOT: honest, cheater, noop, exploit, random |
| `_settle_outstanding_card` | horizon **run-off** of the loan book (expected loss from hidden PD) | so delayed defaults still count | PILOT (analytic) |
| `/verifier/finalize` seal | `engine.finalize()` at end of the agent loop; scorer reads the sealed log | | PILOT |
| `run_*.py` provenance | inspect `.eval` log + `Task.metadata` with config hash and source SHA-256 | inspect logs usage/cost itself | PILOT: config + source hash |
| `results/` with "v2 not comparable" labels | version the economy (`economy_version` in metadata); never mix versions | | FULL |
| Canary GUID | add our own canary to prompt/task files | | PILOT (1 line) |

## 9. Weak spots in Prosus we should not copy

- **Shared RNG stream inside end-of-day** (found by reading `engine.py`, not by running it):
  - `self.rng` is reseeded with `f"{seed}:{day}:{len(events)}"`. It is then drawn in sequence for: short-ship checks (one draw per order line from a bait-and-switch supplier), supplier collapse, email "ghosting" (one draw per email the agent sent), and complaints (the slot is picked from the agent's stocked slots).
  - So **how many orders or emails the agent sent changes whether a supplier collapses or a complaint arrives that night.** Exogenous events depend on agent actions through draw order.
  - Their weekly offers do it right: `random.Random(f"offers:{seed}:{week}:{supplier}:{pid}")` is keyed by entity, so offers are the same whatever the agent does.
  - We key every draw by entity. See [engine-layout.md](engine-layout.md) §4.
- **Float money**: use integer minor units.
- **No reminder test.** `grep reminder tests/` finds nothing. The code looks correct (`_morning_briefing` prints due reminders), but this is exactly the tool VB2 shipped broken. **Write a test that a reminder set for day 5 appears on day 5. PILOT.**
- **Context window counted in characters, including encrypted reasoning.** `window()` measures `len(json.dumps(exchange))`, and `assistant_message()` keeps `reasoning_details` (encrypted signatures). So opaque reasoning blobs use up the window, the same kind of problem Epoch found in VB2 (below). We use inspect `CompactionTrim` with the provider's own token count instead ([../03-tooling/inspect-ai.md](../03-tooling/inspect-ai.md) §3a). **PILOT.**
- **No full event log.** `sales_log` is capped (`sales_log_max_days`), and `events` only holds supplier collapses. For a cheating benchmark the log *is* the evidence, so ours must be complete and append-only.
- **One 1,469-line engine class.** Fine for them. We split truth / records / controls so the "agent cannot touch truth" rule is visible in the code.

## 10. What Prosus fixes that Vending-Bench 2 lacked

Source for the VB2 flaws: [Epoch AI review, 2026-10-21](https://epoch.ai/benchmarks/vending-bench-2/review) (verdict: "Flawed").

| VB2 flaw (Epoch) | Prosus answer | Lesson for us |
|---|---|---|
| **Exploitable economy**: GPT-6 Astra, told to use any tactic, "earned over \$1 million in 102 simulated days" (it ran legitimately for the first 80). It received "over \$1.5 billion of goods it should not have" and exploited pricing. Andon's own "good strategy" estimate was ~\$63,000 a year. Details were redacted at the creators' request | open economy in one TOML; clamps, floors, saturation; one regression test per exploit; scripted calibration; "trivially winnable" PRs rejected | add **exploit bots** that try to break the economy before any LLM run, including *late* exploits (Astra waited 80 days) |
| **Unequal context**: tiktoken used for all providers; encrypted reasoning counted as text (median 47% of Astra's window, 43% for Opus); Astra's effective window ≈ 45k, not 69k | char-based window, same for all models in its runner, but encrypted reasoning still counted (see §9) | count with `model.count_tokens`; report how reasoning is counted |
| **Report bloat**: unread-email previews took ~40% of Opus's window | caps on list/report sizes; briefing shows only the unread *count* | cap our morning briefing; test its size |
| **One-tool-call rule not enforced uniformly** (Bedrock ignored it; 238 calls dropped silently) | multiple calls allowed, run in order, said in the prompt, same for all models | let inspect run calls serially; never drop calls silently |
| **Tool bugs**: `create_reminder` always reported success, never fired; `set_slot_price` failed on filled slots; day-88 divide-by-zero crash | reminders in the briefing; `set_price` works on filled slots; `price_impact` guard | test every tool's effect, not only its return text |
| **Non-reproducible people**: GPT-4o suppliers; live web search and live prices | deterministic templates; synthetic search; LLM only rewrites prose | Lite mode = templates; Full mode = LLM prose over fixed facts |
| Score ignores wages; construct validity weak | API cost reported, not scored; "open-book benchmark" disclaimer | report both "KPI view" and "true view"; say clearly what the score measures |
