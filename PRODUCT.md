# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Static HTML/CSS/JS pages, published as claude.ai Artifacts and kept as local `.html` files under `research/`. No framework. (Inferred from the existing pages; the owner asked for an artifact.)

## Users

The project owner, a student building an AI-safety benchmark. They are new to agents and read research pages to understand and check a design before the build starts. They prefer simple words, bullets and links.

## Product Purpose

Temptation-Bench measures whether an LLM agent stays honest under realistic pressure and temptation while it runs a bank branch over many simulated working days. Pilot-1 (fictional bank) is complete. Pilot-2 is planned: an Indian private-bank branch, the agent is the Branch Manager, 13 live LLM people, two channels (recorded bank email vs the manager's personal phone), live web search.

Research pages succeed when the owner can explain the system back in their own words: what each part does, how a turn flows, where money and facts live, and how a run is scored.

## Positioning

A pure-Python engine owns every rupee and fact behind one door (`Branch.call`). The LLM people act only through checked JSON actions, so the world stays deterministic and replayable while the people are live. The email-vs-phone fork measures the observed-vs-unobserved effect as a matched pair.

## Operating Context

Pages are read on a laptop, sometimes a phone, in light or dark mode. They sit beside markdown notes in `research/09-pilot-2-plan/` (00-README is the plan; 01–05 are the source notes).

## Capabilities and Constraints

- Nothing in pilot-2 is built yet; every number is a design value or an estimate, labelled "proposal, can change".
- The public repo must never contain the real bank's name. Use `{BANK}` placeholders.
- Never invent result numbers.

## Evidence on Hand

- `research/09-pilot-2-plan/00-README.md` (plan, owner decisions D1–D9) and notes 01–05.
- Pilot-1 code and results under `pilot-1/`.
- No users, testimonials or results for pilot-2 exist; do not fabricate any.

## Product Principles

1. Clarity before completeness: the owner must understand it, not just see everything.
2. Honest labels: proposal vs built, estimate vs measured.
3. Realism inside the sim, transparency outside it.

## Accessibility & Inclusion

Readable body text, no handwriting fonts for content, strong contrast in both light and dark mode (owner feedback, 2026-11-24).
