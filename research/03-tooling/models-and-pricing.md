# Models and prices (checked 2026-11-21)

- All prices are **USD per 1 million tokens**, standard (non-batch) tier, unless marked otherwise.
- Prices change often. Re-check the linked page before any paid run.
- "Cache read" = price of input tokens served from the provider's prompt cache. "Cache write" = price to store a prefix (Anthropic 5-minute cache shown).
- Inspect model name = the string for `--model` / `model_roles`.
- Inspect 0.3.291 model database check (`get_model_info`): most names below are in it. These are **not**: `google/gemini-4-neon`, `openrouter/deepseek/deepseek-v4.1-flash`, `openrouter/qwen/qwen3.7-flash`, `openrouter/qwen/qwen4-max`, `openrouter/minimax/minimax-m3.1-flash`, `openrouter/meta-llama/llama-3.1-8b-instruct`. They can still be called, but set their prices with `set_model_info(...)`, because `set_model_cost(...)` refuses unknown models.
- Inspect's database stores context lengths but **no prices**. You must give prices yourself (see [inspect-ai.md § Cost tracking](inspect-ai.md#8-cost-tracking)).

## 1. Anthropic: <https://platform.claude.com/docs/en/about-claude/pricing> (checked 2026-11-21)

| Model | Inspect name | Input | 5m cache write | Cache read | Output | Tier |
|---|---|---|---|---|---|---|
| Claude Haiku 5.5 (prompt ≤100k tokens) | `anthropic/claude-haiku-5-5` | \$0.10 | \$0.125 | \$0.01 | \$0.50 | cheap |
| Claude Haiku 5.5 (prompt >100k tokens) | same | \$0.50 | \$0.625 | \$0.05 | \$2.50 | cheap |
| Claude Haiku 4.5 | `anthropic/claude-haiku-4-5` | \$1.00 | \$1.25 | \$0.10 | \$5.00 | older cheap |
| Claude Sonnet 5.5 | `anthropic/claude-sonnet-5-5` | \$2.00 | \$2.50 | \$0.10 | \$10.00 | mid/frontier |
| Claude Opus 5.5 | `anthropic/claude-opus-5-5` | \$4.00 | \$5.00 | \$0.20 | \$20.00 | frontier |
| Claude Fable 5.2 | `anthropic/claude-fable-5-2` | \$8.00 | \$10.00 | \$0.20 | \$40.00 | top frontier |

- Batch API: **50% off** input and output ([pricing page](https://platform.claude.com/docs/en/about-claude/pricing#batch-processing)). Cache discounts stack with batch.
- 1-hour cache write = 2× base input. Cache read is 0.1× on most models, 0.05× on Opus 5.5 / Sonnet 5.5, and 0.025× on Fable 5.1/5.2.
- Claude 4.7+ models use a newer tokenizer that gives "approximately 30% more tokens for the same text". Compare cost per run, not per token.
- **Haiku 5.5 gets 5× more expensive above 100k-token prompts. Keep the agent window under 100k** (e.g. a 30k–60k trim threshold).
- Prompt caching docs: <https://platform.claude.com/docs/en/build-with-claude/prompt-caching>. Inspect adds Anthropic cache breakpoints automatically (`cache_prompt="auto"`).

## 2. OpenAI: <https://developers.openai.com/api/docs/pricing> (checked 2026-11-21; old URL platform.openai.com/docs/pricing redirects here)

| Model | Inspect name | Input | Cached input | Output | Tier |
|---|---|---|---|---|---|
| gpt-5-nano | `openai/gpt-5-nano` | \$0.05 | \$0.005 | \$0.40 | cheapest |
| gpt-6-luna | `openai/gpt-6-luna` | \$0.10 | \$0.01 | \$0.50 | cheap |
| gpt-5.6-luna | `openai/gpt-5.6-luna` | \$0.20 | \$0.02 | \$1.20 | cheap |
| gpt-5-mini | `openai/gpt-5-mini` | \$0.25 | \$0.025 | \$2.00 | cheap |
| gpt-6.1-terra | `openai/gpt-6.1-terra` | \$1.00 | \$0.05 | \$5.00 | mid |
| gpt-6.2-sol | `openai/gpt-6.2-sol` | \$2.00 | \$0.10 | \$10.00 | frontier |
| gpt-6.2-astra | `openai/gpt-6.2-astra` | \$8.00 | \$0.40 | \$40.00 | top frontier |

- Batch and Flex tiers are about **half** the Standard price (my reading of the tables). Some newer models also have cheaper "background" requests (−30% for a 2h window, −40% for an 8h window).
- Caching is automatic. The page also lists "30m write" / "12h write" columns for some models without explaining them. [OpenRouter's caching guide](https://openrouter.ai/docs/guides/best-practices/prompt-caching) says GPT-5.6+ charge 1.25× for cache writes.
- Inspect added support for "GPT-6.2 Astra and GPT-6.2 Sol" in 0.3.291 ([changelog](https://github.com/UKGovernmentBEIS/inspect_ai/blob/main/CHANGELOG.md)).

## 3. Google Gemini: <https://ai.google.dev/gemini-api/docs/pricing> (redirects to <https://aistudio.google.com/docs/pricing>, checked 2026-11-21)

| Model | Inspect name | Input | Cache read | Output | Notes |
|---|---|---|---|---|---|
| gemini-2.5-flash-lite | `google/gemini-2.5-flash-lite` | \$0.10 | \$0.01 | \$0.40 | cheapest; free tier |
| gemini-3.5-flash-lite | `google/gemini-3.5-flash-lite` | \$0.30 | \$0.03 | \$2.50 | free tier |
| gemini-3.8-flash | `google/gemini-3.8-flash` | \$0.75 | \$0.075 | \$3.75 | **rises to \$1.50 / \$7.50 on 2027-01-01**; free tier |
| gemini-4-hydrogen | `google/gemini-4-hydrogen` | \$1.50 | \$0.075 | \$7.50 | free tier |
| gemini-4-carbon | `google/gemini-4-carbon` | \$2.00 | \$0.10 | \$10.00 | **rises to \$4 / \$20 on 2026-12-01** |
| gemini-4-neon | `google/gemini-4-neon` | \$3.00 | \$0.15 | \$15.00 | frontier; #1 on VB2 leaderboard |

- Explicit context caching also charges storage per hour (e.g. \$0.50–\$1.00 per 1M tokens per hour on Flash models). Implicit caching is automatic.
- Batch = 50% of Standard on the page.
- `gemini-2.5-flash` and `gemini-2.5-pro` are marked deprecated, and get re-routed on 2026-12-01.

## 4. DeepSeek direct: <https://api-docs.deepseek.com/quick_start/pricing> (checked 2026-11-21)

| Model | Inspect name | Input (cache miss) | Input (cache hit) | Output |
|---|---|---|---|---|
| deepseek-flash | `deepseek/deepseek-flash` | \$0.30 peak / \$0.15 off-peak | \$0.006 / \$0.003 | \$1.20 / \$0.60 |
| deepseek-v4-pro | `deepseek/deepseek-v4-pro` | \$1.32 / \$0.66 | \$0.044 / \$0.022 | \$3.96 / \$1.98 |

- "Off-peak rates are half of the peak rates." Peak = 01:00–04:00 and 06:00–10:00 UTC, Mon–Fri. Weekends are off-peak.

## 5. Open-weight and other models via OpenRouter: <https://openrouter.ai/models>

- Source: the official OpenRouter API `GET https://openrouter.ai/api/v1/models` (checked 2026-11-21). The list price shown is OpenRouter's per-model price. **Real price depends on which upstream provider serves you** (see note below).
- Inspect name = `openrouter/<id>`. All rows below list tool-calling support.

| OpenRouter id | Input | Output | Cache read | Context |
|---|---|---|---|---|
| `meta-llama/llama-3.1-8b-instruct` | \$0.02 | \$0.04 | – | 131k |
| `openai/gpt-oss-20b` | \$0.017 | \$0.085 | \$0.0085 | 131k |
| `qwen/qwen3.7-flash` | \$0.03 | \$0.13 | \$0.006 | 1M |
| `z-ai/glm-5.3-flash` | \$0.04 | \$0.078 | \$0.03 | 1M |
| `deepseek/deepseek-v4.1-flash` | \$0.05 | \$0.20 | ~\$0.001 | 1M |
| `openai/gpt-oss-120b` | \$0.09 | \$0.36 | – | 131k |
| `meta-llama/llama-4-scout` | \$0.10 | \$0.30 | – | 1.3M |
| `qwen/qwen3.8-flash` | \$0.15 | \$0.47 | \$0.016 | 1M |
| `minimax/minimax-m3.1-flash` | \$0.15 | \$0.60 | \$0.015 | 1M |
| `meta-llama/llama-4-maverick` | \$0.35 | \$1.00 | \$0.17 | 524k |
| `deepseek/deepseek-v4-pro` | \$0.90 | \$1.50 | \$0.20 | 1M |
| `qwen/qwen4-max` | \$1.425 | \$4.275 | \$0.071 | 1M |
| `google/gemma-4-31b-it:free` | \$0 | \$0 | – | 262k (free, rate-limited) |

- **Provider variance:** for `deepseek/deepseek-v4.1-flash`, the endpoints API (`/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints`) listed 10+ providers at \$0.05–\$0.12 input and \$0.20–\$0.90 output, with **different quantizations (fp4, fp8, mxfp4)**. For a benchmark, **pin one provider and quantization** with Inspect `-M provider={...}` ([OpenRouter provider routing](https://openrouter.ai/docs/features/provider-routing)). Otherwise runs are not comparable.
- OpenRouter caching ([guide](https://openrouter.ai/docs/guides/best-practices/prompt-caching)): automatic for OpenAI, DeepSeek, Grok, Moonshot, Z.AI and Gemini 2.5+. Anthropic needs `cache_control` (Inspect adds it for `openrouter/anthropic/*`). Sticky routing keeps you on one provider for 60 min of activity. Inspect sends an `x-session-id` per sample.
- OpenRouter also resells Anthropic/OpenAI/Google at the same list prices, e.g. `anthropic/claude-haiku-5.5` \$0.10/\$0.50 and `openai/gpt-6-luna` \$0.10/\$0.50. One key, one bill.

## 6. What to pick (proposal, can change)

- **Simulated people (customers, auditors, regional boss):** `anthropic/claude-haiku-5-5`, `openai/gpt-6-luna` or `openrouter/deepseek/deepseek-v4.1-flash`. Use **one fixed model for every run**, so the "world" is the same for every agent model. VB1 and VB2 used GPT-4o for suppliers ([Epoch review](https://epoch.ai/benchmarks/vending-bench-2/review)).
- **Cheap agents under test:** Haiku 5.5, gpt-6-luna, gemini-3.5-flash-lite, deepseek-v4.1-flash, qwen3.8-flash, gpt-oss-120b.
- **Frontier agents under test:** Sonnet 5.5 / Opus 5.5, gpt-6.2-sol, gemini-4-neon (top of the VB2 leaderboard on 2026-11-21).
- Before a paid run: do a tiny pilot (e.g. 3 sim days), read the real `ModelUsage` from the log, then scale up.

## 7. Batch API and prompt caching for long agent loops

- **Prompt caching matters most.** Each turn re-sends the whole window (e.g. 30k tokens) and adds only ~1–2k new tokens. With caching, ~90% of input is billed at the cache-read price (0.1× or lower).
- **Caching only works if the prefix stays the same.** A sliding "last N tokens" window changes the first message every turn and breaks the cache. Chunked trimming (`CompactionTrim`, VB2's "keep 61%") keeps the prefix stable until the next trim.
- Don't put the current sim time or date in the **system prompt**. Put it in the newest message, or the cache breaks every turn.
- **Batch APIs (~50% off)** are a poor fit for the main agent loop: every turn waits for a batch (minutes to hours). They are fine for **offline** jobs: LLM-judge passes over finished logs, or generating personas/emails before the run.
- Anthropic's 5-minute cache is refreshed by each hit. Fast sims (tools return instantly) stay warm.

## 8. Illustrative cost arithmetic (assumptions, NOT measured results)

- Assumptions (proposal): 30 sim days × 10 agent turns/day = 300 turns. Average window input = 25k tokens. Output = 400 tokens/turn. So total input = 7.5M tokens, total output = 0.12M tokens. With caching, assume 90% cache reads and 10% cache writes.
- Formula: `cost = in_tokens × (0.9×cache_read + 0.1×cache_write) + out_tokens × output_price`.

| Agent model | No caching | With caching (assumed 90% hits) |
|---|---|---|
| Haiku 5.5 | 7.5×0.10 + 0.12×0.50 = **\$0.81** | 6.75×0.01 + 0.75×0.125 + 0.06 = **\$0.22** |
| Sonnet 5.5 | 7.5×2 + 0.12×10 = **\$16.20** | 6.75×0.10 + 0.75×2.50 + 1.20 = **\$3.75** |
| Opus 5.5 | 7.5×4 + 0.12×20 = **\$32.40** | 6.75×0.20 + 0.75×5 + 2.40 = **\$7.50** |

- Simulated people: e.g. 60 calls × (1.5k in + 300 out) on Haiku 5.5 ≈ 0.09×0.10 + 0.018×0.50 ≈ **\$0.02**. Tiny.
- Big unknown: **reasoning tokens** are billed as output. VB2 reports "60-100 million tokens in output during a run" for a full simulated year. So measure in the pilot.
