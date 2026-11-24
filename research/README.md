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
| `06-eval-awareness/` | Do models know it's a test? Evidence, trigger cues, how to measure it on a small budget |
| `07-pilot-1-review/` | Read-only review of pilot-1: plan vs built, transcripts, graphs, people/pressure, horizon, ranked gaps and fixes |
| `08-pilot-2-ideas/` | Pilot-2 ideas: benchmark survey, LLM-agent people, maths/mechanics, scenario catalogue, writing guide, builder reuse notes |
| `09-pilot-2-plan/` | Pilot-2 plan (owner direction 2026-11-23): live LLM people + two channels, real India/RBI bank, 60 rich tools, long horizons, build phases, owner decisions |

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
- `06-eval-awareness/00-README.md` — **start here**: synthesis of pilot-1's 14/14 "EVAL" result + the 3 notes; 3-layer strategy (measure, remove cues, robust design), fix table mapped to pilot-1 files, owner decisions
- `06-eval-awareness/01-measurement-and-evidence.md` — eval-awareness papers 2024–2026 (rates, behaviour effects, 8 trigger factors, measurement biases incl. leading probes, baselines, pairwise realism); ranked to-dos for our 14/14 "EVAL" pilot result
- `06-eval-awareness/02-realism-methods.md` — methods to make the eval look real (realism judges, seed rewrites, real formats, deployment-like harness, honeypots in normal work, sandbox hygiene, steering limits); 20 scenario-writing rules mapped to pilot-1 cues; ranked technique table
- `06-eval-awareness/03-realistic-banking-deployment.md` — how real banks deploy AI agents (prepare/decide, delegated limits, agent scorecards), real tool-output shapes, 4 reframing options (A: credit-ops agent for a human manager, recommended)
- `07-pilot-1-review/00-README.md` — **start here for the pilot-1 review**: 5 key lessons + reading order; `07-gaps-and-fixes.md` has the ranked fix list (engine does the underwriting, free-to-refuse bribe, no stakes, thin world, turns not days) and owner decisions
- `08-pilot-2-ideas/00-README.md` — **start here for pilot-2**: why pilot-1 had no dilemma (one equation), 15 ranked ideas, 3 build approaches (B "one living quarter" recommended), cost estimate, owner decisions
- `08-pilot-2-ideas/01-benchmark-survey.md` — ~30 benchmarks (Vending-Bench 2/Arena, Project Vend, MASK, PropensityBench, GovSim, Concordia …): behaviour signal + mechanics to steal; top 10
- `08-pilot-2-ideas/02-multi-agent-people.md` — simulated people as LLM agents: cast + persona cards, truth-in-code/talk-in-LLM, move-keyed shared cache for minimal pairs, cost, why pilot-1 prose failed
- `08-pilot-2-ideas/03-mechanics-and-math.md` — every model: designed/built/used; the Δ equation; per-seed targets, stakes, audit odds, adaptive dose, run-count formulas; top 8
- `08-pilot-2-ideas/04-scenarios-and-pressure.md` — 20 scenario cards with twins (sad story as appeal after decline), pressure + AI-behaviour libraries, 22 real cases, 60-business-day storyline; top 8
- `08-pilot-2-ideas/05-writing-guide.md` — style guide + before→after rewrites of all agent-facing text; controlled prose pipeline; top 10
- `08-pilot-2-ideas/06-reuse-from-pilot-1.md` — builder view: reuse/change/replace per module, cheap switches, LLM-people hook, pitfalls
- `08-pilot-2-ideas/07-pilot-1-inventory.md` — full inventory of pilot-1: 18 tools, 8 bots, all maths (credit, PD/hazards, book, audit, targets, scoring, stats), world/scenario, people, harness, graphs; keep/change/replace per part
- `09-pilot-2-plan/00-README.md` — **start here for the pilot-2 plan**: owner asks → plan, architecture, conflicts resolved, spot-checks, build phases with costs, decisions D1–D9
- `09-pilot-2-plan/01-designed-vs-built.md` — ~45 tools designed vs 18 built; why tools feel "not mathematical" (PASS/FAIL does the maths); unused levers; ranked mechanics to bring back
- `09-pilot-2-plan/02-continuous-llm-people-prior-art.md` — Vending-Bench (LLM suppliers, formula customers), Concordia scheduler, private-channel precedents; people-loop blueprint
- `09-pilot-2-plan/03-real-country-bank.md` — India/RBI frame (Directions 2025, IRAC, AML, gifts, powers), real bank use + safeguards, frozen web snapshot, legal risk, eval-awareness effect
- `09-pilot-2-plan/04-llm-cast-and-channels.md` — 13-person cast with prompt cards, email vs personal-phone channels, fork experiment, McNemar power, cost, phasing
- `09-pilot-2-plan/05-world-tools-states-horizon.md` — 60 tools with maths and signals, state machines, H60/H125/H250 on the Indian calendar, pressure maths, formal docs, build plan
- `09-pilot-2-plan/ideas-log.md` — running ideas list (owner, lead, agents)

## Conventions

- Numbers from sources carry a link. Numbers we chose say **"proposal, can change"**.
- No result numbers are ever estimated here.
- Fictional bank only. No real bank names in the simulation (real cases like Wells Fargo appear only as background).
