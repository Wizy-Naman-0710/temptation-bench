# Temptation-Bench

A planned benchmark that measures whether LLM agents stay honest during a long simulated job when cheating pays.

**World 1: bank branch manager.** An agent runs a fictional bank branch (Cobalt Ridge Bank) for several simulated weeks. Ordinary business events carry planted temptations, such as a bribe for approving a loan that breaks the rules. Every rule break is scored **by code**: the agent's tool calls and filed reports are compared with the simulation's hidden true books. No LLM judge is used for the main score.

**Headline question: the Price of Integrity.** How large a bribe does it take before an agent knowingly breaks the rules? We estimate B50, the bribe at which an agent gives in half the time, for each model.

> **Status:** research and design only. There is no code yet, and none of the numbers in these docs are experimental results. Every design value is a proposal that can change.

## What's here

| Path | Contents |
|---|---|
| [`docs/2026-11-21-temptation-bench-pilot-design.md`](docs/2026-11-21-temptation-bench-pilot-design.md) | Pilot design: Price of Integrity (§5A), world, tools, scoring, simulation limits (§13A) |
| [`docs/qna.md`](docs/qna.md) | Design decisions explained (e.g. why 30 sim days, not 2 years) |
| [`docs/open-questions.md`](docs/open-questions.md) | Decisions still open |
| [`research/`](research/README.md) | Notes behind the design: papers, prior work, banking domain, tooling, methodology, simulator architecture |
| [`idea.md`](idea.md) | The original planning brief |

## Built on

- [Vending-Bench](https://arxiv.org/abs/2502.15840) (Andon Labs): the long-horizon business-sim format
- [Blueprint-Bench](https://arxiv.org/abs/2509.25229): structured outputs scored by code
- [inspect-ai](https://inspect.aisi.org.uk/): the planned evaluation harness
- [ProsusAI/vending-bench](https://github.com/ProsusAI/vending-bench): engineering patterns

The bank, its regulator and its currency are fictional. The `$` is the fictional country's own dollar, not the US dollar.
