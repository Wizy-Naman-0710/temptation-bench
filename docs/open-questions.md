# Open questions for the owner

Decisions only the owner can make, and the answers given so far. Update this file as answers come in.

## Answered (2026-11-21)

| Question | Answer |
|---|---|
| How should runs call the models? | **Direct provider APIs** (e.g. Anthropic and OpenAI keys). Prompt caching works reliably this way, and inspect-ai supports these providers natively. |
| Reasoning/thinking effort | **One fixed level for every model.** Still open: which level. Note that "medium" doesn't mean the same thing at every provider; we will record the exact setting in each log. |

## Still open (answer later)

1. **Which agent models to test?** The pilot has room for about 3. Prices per 1M input/output tokens, checked 21 Nov 2026 ([research/03-tooling/models-and-pricing.md](../research/03-tooling/models-and-pricing.md)):
   - Frontier: Claude Sonnet 5.5 \$2/\$10 · Claude Opus 5.5 \$4/\$20 · gpt-6.2-sol \$2/\$10
   - Cheap: Claude Haiku 5.5 \$0.10/\$0.50 · gpt-6-luna \$0.10/\$0.50 · DeepSeek v4.1 Flash ~\$0.05/\$0.20 (OpenRouter only, so it would break the "direct APIs" choice)
   - Earlier suggestion (not decided): Sonnet 5.5 + Haiku 5.5 + gpt-6-luna.
2. **Which fixed reasoning level?** For example, low or medium. Higher levels cost more per turn.
3. **Total budget cap for the smoke run plus the pilot.** This becomes a hard `--cost-limit`. A measured estimate will still be shown, and the owner asked, before every paid run.
4. **Approve the design doc** (`2026-11-21-temptation-bench-pilot-design.md`) once the Price of Integrity and simulation-limits sections are in.

## Decided by the designer, for the owner to check

- See §16.1 of the design doc (31 items).
