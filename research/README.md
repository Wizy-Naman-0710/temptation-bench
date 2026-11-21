# Research notes — Temptation-Bench (World 1: Bank Branch Manager)

This folder is the knowledge base behind the design. Every file is short, bullet-style, with links.
Design decisions live in `../docs/`; this folder holds **facts and findings** that those decisions rest on.

## Layout

| Folder | What lives here |
|---|---|
| `00-papers/` | Notes on the two papers we copy the style of |
| `01-prior-work/` | Gap check: related safety benchmarks, how we differ |
| `02-banking-domain/` | How real branches, credit, AML, audit work + formulas for the simulator |
| `03-tooling/` | inspect-ai, sub-agents, memory tools, models & prices, code structure |
| `04-methodology/` | Experimental design: Price of Integrity, attribution, scenario twins, experiment matrix |
| `05-simulator-architecture/` | Engine design: ProsusAI code study, truth vs records, invariants, consequences, module layout |

## Files

- `00-papers/vending-bench.md` — agent loop, clock, customers formula, scoring, lessons
- `00-papers/blueprint-bench.md` — strict output format → code-only scoring
- `01-prior-work/gap-check.md` — broad gap is taken (Andon Labs, CoffeeBench); a narrower claim holds: banking + controlled temptations + hidden books + code scoring
- `02-banking-domain/README.md` — index of 9 files: rulebook, branch economics, credit risk, evergreening, AML/VIP, audit, customer formulas, gifts/whistleblowing, personas
- `02-banking-domain/general-rulebook.md` — fictional, country-agnostic policy manual (Woz Valley Bank, regulator MPA, currency \$, a fictional dollar), 17 rules + ~300-word agent version
- `02-banking-domain/calibration-table.md` — every simulator parameter with base/low/high, source or 'design choice', verdicts on the other LLM's corrections
- `02-banking-domain/default-timing-and-horizon.md` — when defaults happen, clock design, 3–6 month agent run + free run-off to maturity, tenor/DTI formula
- `03-tooling/README.md` — inspect-ai 0.3.291: custom `@agent` loop + `CompactionTrim`, model roles for simulated people, cost logging, memory tools, prices (checked 2026-11-21), code layout
- `04-methodology/README.md` — Price of Integrity design: knowing-violation outcome, B50 estimation (dose / hybrid / ladder) with censoring and power formulas, attribution controls, scenario twins + honest profit, pilot (3×3×5) vs full matrix, verdicts on suggestions A–F
- `05-simulator-architecture/README.md` — ProsusAI/vending-bench code study (Apache-2.0) + simulator design: truth ledger vs editable records vs reports, append-only logs, invariants, exploit bots, cheat → delayed-event table, keyed RNG streams, module layout, PILOT vs FULL marks, verdicts on the other LLM's suggestions

## Conventions

- Numbers from sources carry a link. Numbers we chose say **"proposal, can change"**.
- No result numbers are ever estimated here.
- Fictional bank only. No real bank names in the simulation (real cases like Wells Fargo appear only as background).
