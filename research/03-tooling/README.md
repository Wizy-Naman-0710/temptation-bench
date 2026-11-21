# 03 – Tooling research (checked 2026-11-21)

How to build a long-horizon, Vending-Bench-style simulation benchmark in Python, solo and on a small budget.

- **Versions checked:** inspect-ai 0.3.291, inspect-evals 0.29.0, inspect-swe 0.3.2 (all PyPI, Nov 2026). Also numpy 2.5.5, hypothesis 6.170.17, pydantic 2.14.4, sentence-transformers 6.3.0, fastembed 0.9.1.
- **How verified:** installed packages in a clean venv, printed real signatures, read docs source from the [inspect_ai repo](https://github.com/UKGovernmentBEIS/inspect_ai), and ran two free smoke evals with `mockllm`: a custom loop, a tool writing to a `StoreModel`, a cheap-model role, cost tracking, `CompactionTrim`, and reading the `.eval` log.
- Context7 MCP was not available (it needed authentication), so docs came from the official sites and GitHub.

## Files

| File                                                           | What's inside                                                                                                                                         |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| [inspect-ai.md](inspect-ai.md)                                 | Task/Solver/Scorer, `@tool`, agent loop with context trimming, store, seeds/epochs, model roles, limits, cost, logs, concurrency, OpenRouter, caching |
| [multiagent-and-subagents.md](multiagent-and-subagents.md)     | `multiagent-inspect` status, built-in `as_tool` / `handoff` / `run` / `deepagent` / `subagent`                                                        |
| [memory-tools.md](memory-tools.md)                             | VB1 vs VB2 memory, scratchpad / key-value / notes / reminders, local vs API embeddings                                                                |
| [models-and-pricing.md](models-and-pricing.md)                 | Price tables (Anthropic, OpenAI, Google, DeepSeek, OpenRouter) with links, caching and batch notes, example cost math                                 |
| [project-structure-patterns.md](project-structure-patterns.md) | Engine vs glue layout, heapq clock, seeded RNG streams, dataclasses/pydantic, JSONL log, testing with Hypothesis and scripted policies                |

## Top takeaways

1. **Use inspect-ai with a small custom `@agent` loop.** Not `react()` (it is built around "call `submit()` when done") and not `deepagent()` (it brings its own prompt, compaction and memory, which change behaviour per model). The sim clock decides when the run ends.
2. **Context truncation:** `compaction(CompactionTrim(threshold=30_000, preserve=0.6, memory=False), prefix=..., tools=...)` inside the loop. An int threshold is an absolute token count. This copies VB2 ("~69k tokens, keep ~61% of messages"). It keeps system + task messages, keeps the cache-friendly prefix stable between trims, and the full history is still logged. A strict per-turn "last N tokens" window (VB1) is possible with `model.count_tokens`, but it breaks prompt caching.
3. **Simulated people = model roles.** `Task(model_roles={"customer": "anthropic/claude-haiku-5-5"})` (or `--model-role customer=...`), then `get_model(role="customer").generate(...)` inside your tools. Usage is logged per role (`EvalSample.role_usage`, `EvalStats.role_usage`, `ModelEvent.role`). Use one fixed cheap people-model for every agent model.
4. **Tokens and cost are logged automatically.** Each `ModelEvent` has `output.usage` (input, output, cache write, cache read, reasoning tokens, `total_cost`). Per-sample and per-eval totals are in `model_usage` / `role_usage`. Dollars only appear once you give prices (`set_model_cost` / `set_model_info` or `--model-cost-config`). Inspect's model database has no prices. `--cost-limit` caps dollars per sample.
5. **Hidden world state** goes in a `StoreModel` (via `store_as`), plus your own pure-Python engine. Scorers read it with `state.store_as(...)`. All store changes are logged as `StoreEvent`s.
6. **`multiagent-inspect` is archived** (last commit 2025-02-05). Inspect's built-in `as_tool()` / `handoff()` / `run()` / `subagent()` replace it. Start single-agent anyway.
7. **Prompt caching is the biggest cost lever.** Illustrative math (assumptions, not results): a 300-turn Sonnet 5.5 run is ~\$16 uncached vs ~\$4 cached. Batch APIs (−50%) don't suit live agent loops.
8. **Cheap but good options (Nov 2026):** Claude Haiku 5.5 (\$0.10/\$0.50, keep prompts ≤100k), gpt-6-luna (\$0.10/\$0.50), DeepSeek v4.1 Flash via OpenRouter (~\$0.05/\$0.20), Qwen 3.8 Flash (\$0.15/\$0.47). Frontier: Sonnet 5.5 / Opus 5.5, gpt-6.2-sol, gemini-4-neon. On OpenRouter, **pin the provider and quantization** for comparable runs.
9. **Engine first, LLM last.** Deterministic engine + scripted policies + Hypothesis tests catch the bugs that hurt VB2 (silent reminder tool, divide-by-zero crash, exploitable economy). They cost \$0.
10. **Learn from VB2's flaws** ([Epoch review, 2026-10-21](https://epoch.ai/benchmarks/vending-bench-2/review)): count tokens with each provider's own tokenizer, test every tool, cap report sizes, and red-team your own economy.

## inspect_swe and inspect_evals: relevant?

- **[inspect_swe](https://github.com/meridianlabs-ai/inspect_swe)** (0.3.2, "Software Engineering Agents for Inspect AI"): runs real coding agents (`claude_code`, `codex_cli`, `gemini_cli`, `opencode`, `kimi_code`, `mini_swe_agent`, ...) inside a sandbox via the agent bridge. **Not needed** for a business sim. Skip it.
- **[inspect_evals](https://github.com/UKGovernmentBEIS/inspect_evals)** (0.29.0, [site](https://ukgovernmentbeis.github.io/inspect_evals/)): 100+ community evals. **Useful as code to read**, not to depend on:
  - `tau2` (incl. `tau2_banking`!): a user simulator via `get_model(role="user")`, domain tools, a DB-state scorer. Closest to a bank-branch world.
  - `make_me_pay`: two-model conversation with roles `conartist` and `mark`.
  - `agentic_misalignment`: port of Anthropic's [Agentic Misalignment](https://www.anthropic.com/research/agentic-misalignment) scenarios (blackmail, leaking). Related "temptation" work.
  - Also related: `agentharm`, `instrumentaleval`, `persistbench`.

## Open-source Vending-Bench re-implementations (GitHub search, 2026-11-21)

| Repo | Status | Worth reading for |
|---|---|---|
| [ProsusAI/vending-bench](https://github.com/ProsusAI/vending-bench) | Active (pushed 2026-11-20), Apache-2.0, 25★ | **Best reference.** Deterministic engine (`engine.py`, `demand.py`, `config.toml`), 22 MCP tools incl. `write_note` / `read_notes` / `set_reminder` / `list_reminders`, scripted `reference_bot.py`, 55 engine tests in `test_engine.py`, 80 total (recounted at commit `60794b4`), `--budget` and `--timeout` caps, cost reported separately. Not inspect-based (MCP + Harbor). |
| [markattarcolgate64/open-vending-bench](https://github.com/markattarcolgate64/open-vending-bench) | Unfinished (last push 2025-10-06), no license | Early recreation. Memory tools and sub-agent not done. Only for ideas. |
| Small/experimental: [Wayfound-AI/mini-vending-bench](https://github.com/Wayfound-AI/mini-vending-bench) (JS), [aijnek/vending_bench](https://github.com/aijnek/vending_bench), [Shell1500/vending_bench_deepseek](https://github.com/Shell1500/vending_bench_deepseek), [letterj/vending-bench](https://github.com/letterj/vending-bench), [webdevsha/vendsafe-lab](https://github.com/webdevsha/vendsafe-lab) (safety experiments on VB2) | 0–5★ | Not reviewed in depth. Low priority. |

- The official Andon Labs harness is **not** open source. Public VB2 details ([Andon page](https://andonlabs.com/evals/vending-bench-2)):
  - one simulated year, \$500 start, \$2/day fee, ends after 10 days unable to pay
  - ~69k-token window, trimmed keeping ~61% of messages
  - note-taking and reminder tools
  - adversarial LLM suppliers, delivery delays, refunds
  - score = final bank balance
  - 3,000–6,000 messages per run
- Epoch adds: suppliers are played by GPT-4o, and the harness enforces one tool call per turn ([review](https://epoch.ai/benchmarks/vending-bench-2/review)).
- VB1 ([arXiv 2502.15840](https://arxiv.org/abs/2502.15840)) was built on inspect-ai + `multiagent-inspect`, with a 30k-token window and scratchpad / key-value / vector-DB memory.
