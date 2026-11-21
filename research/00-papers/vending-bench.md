# Vending-Bench (Andon Labs, Feb 2025)

- Paper: [arXiv 2502.15840](https://arxiv.org/abs/2502.15840) · local copy `~/Downloads/2502.15840v1.pdf`
- One line: an LLM agent runs a vending machine business for many simulated days. Each step is easy; runs fail because the agent loses coherence over time.

## Agent setup
- Basic tool-calling loop in [inspect-ai](https://inspect.aisi.org.uk/).
- **Context window cut to the last N tokens** (N = 30k by default; also tried 10k and 60k).
- **Memory tools** (read / write / delete): scratchpad, key-value store, vector DB (OpenAI `text-embedding-3-small`, cosine search).
- **Sub-agent** for "physical world" actions (stock machine, collect cash, set prices, check machine inventory).
  - Main agent talks to it with `sub_agent_specs`, `run_sub_agent`, `chat_with_sub_agent`.
  - Library: [multiagent-inspect](https://github.com/AndonLabs/multiagent-inspect).
- Remote tools for the main agent: read/send email, web search (Perplexity), check storage inventory, check money balance.
- If the agent replies without a tool call, the system says: *"Continue on your mission by using your tools."*

## Clock
- Every tool call moves time forward by **5 min, 25 min, 75 min or 5 h**, depending on the tool.
- `wait_for_next_day` skips ahead. Each morning: report of sales + new emails.
- Run length: **2,000 messages** (not a fixed number of days). Ends early if the agent can't pay the daily fee for 10 days in a row.
- About 25M tokens per run; 5–10 real hours per run. 5 runs per model.

## Simulated people
- **Suppliers:** each email sent to a real wholesaler address gets a GPT-4o reply. Facts about the supplier come from Perplexity. Ordering requires item names, quantities, delivery address and account number. Delivery takes a few days; a delivery email arrives.
- **Customers:** formula, run once per day per item:
  1. GPT-4o generates and caches, per item: price elasticity, reference price, base sales.
  2. Sales impact factor from % difference between price and reference price × elasticity, applied to base sales.
  3. Multipliers for day of week, month, weather.
  4. Variety multiplier: rewards good variety, punishes too many options (max 50% cut).
  5. Add noise, round, clip to `[0, inventory]`.
  - In formula form: `Q_t = clip(Q0 · f(P_t, P_ref, ε) · M_calendar · M_weather · M_variety + η_t, 0, I_t)`

## Config
- Start cash \$500. Daily fee \$2. Machine: 4 rows × 3 slots (2 small rows, 2 large).

## Scoring (all by code)
- **Primary:** final net worth = cash + uncollected cash in machine + unsold inventory at wholesale price.
- Also: units sold, days until sales stop, tool-use counts.
- Human baseline: one person, 5 hours, same interface.

## Main findings (reported by the paper, not by us)
- Very high variance between runs of the same model.
- Common failure: agent thinks an order arrived when it hasn't → tangents, "meltdowns" (e.g. emailing the FBI, threatening suppliers with "nuclear legal intervention").
- Failures are **not** explained by the context window filling up (weak correlation between "days until full memory" and "days until sales stop").
- More memory (60k) did worse than less memory (10k/30k) for GPT-4o mini.
- Removing the daily fee made the agent passive (loops of waiting). **Pressure drives activity.**

## What we reuse for Temptation-Bench
- Clock + time cost per tool + `wait_for_next_day` + morning report.
- Last-N-token context + three memory tools.
- Formula-driven crowd (customers) + LLM-played individuals (suppliers → our VIP, boss, auditor).
- Code-only primary score.
- Lesson: a recurring cost is needed, or agents go idle. Our version: branch operating cost + quarterly targets.
- Lesson: delivery-timing confusion caused most failures. Our world must make state **easy to check** (e.g. `check_books`) so we measure honesty, not confusion.
