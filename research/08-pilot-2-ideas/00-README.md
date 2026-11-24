# 08 — Ideas for pilot-2: what to build so the agent faces real temptation

Made 2026-11-22. Five research agents worked on this, plus the pilot-1 build session. Every number below is either measured in pilot-1, quoted from a linked source, or marked **estimate / proposal, can change**. No paid calls were made, and nothing in `pilot-1/` or `docs/` was changed.

## Read in this order

| File | What it answers |
|---|---|
| **this file** | The big picture, the ranked ideas, three ways to build pilot-2, decisions for the owner |
| [03-mechanics-and-math.md](03-mechanics-and-math.md) | **Why nothing happened in pilot-1, as one equation**, and the maths that makes a real dilemma (per-seed targets, stakes, audit odds, adaptive dose, run counts) |
| [04-scenarios-and-pressure.md](04-scenarios-and-pressure.md) | 20 scenario cards with clean twins, 17 psychology mechanisms, 12 AI behaviours, 22 real bank cases, and a **60-business-day storyline** |
| [02-multi-agent-people.md](02-multi-agent-people.md) | **Simulated people who are LLM agents**: the cast, persona cards, how to keep paired runs fair, cost |
| [01-benchmark-survey.md](01-benchmark-survey.md) | About 30 benchmarks (Vending-Bench 2 and Arena, Project Vend, MASK, PropensityBench, GovSim, Concordia …): what each one teaches and what to borrow |
| [05-writing-guide.md](05-writing-guide.md) | A style guide plus **before → after rewrites** of every text the agent reads (system prompt, tool outputs, bribe, boss, appeal, ending) |
| [06-reuse-from-pilot-1.md](06-reuse-from-pilot-1.md) | The builder's view: what to reuse, cheap switches, where LLM people plug in, pitfalls |
| [07-pilot-1-inventory.md](07-pilot-1-inventory.md) | Everything in pilot-1: 18 tools, 8 bots, all the maths, world, people, harness, graphs, and keep/change/replace for each |

---

## 1. The one idea that explains pilot-1

From [03 §2](03-mechanics-and-math.md). On a bad file, the agent effectively compares:

```
Δ = (value of the bribe) + (gain on its own scorecard)
  − (chance of being caught × how bad that is)
  − (moral cost of breaking a rule) − (extra effort the honest path needs)
```

Pilot-1 set **every term to about zero except the moral cost**:

- The bribe bought nothing the agent cared about.
- T1 would have changed whether the target was hit on only **2 of 30 seeds** (03's arithmetic from `calibration.toml`).
- The bonus is text only and is never paid.
- Getting caught means one reprimand email.
- The tool printed `POLICY CHECK: FAIL … Fix:`, so the honest path took no effort.

So pilot-1 tested *"does a model break a rule when breaking it buys nothing?"* The answer is no, and it was always going to be no.

**Pilot-2's job:** raise **one term at a time**, so we know which one moves behaviour. Every idea below is tagged with the term it raises.

## 2. What other benchmarks teach (from [01 §8](01-benchmark-survey.md))

1. **The bad act must be possible, tempting and not blocked.** The honest option stays open but costs something. Pilot-1 had a free exit.
2. **Many small temptations beat one big one.** Andon's most solid honesty number is refunds paid: [GPT-6 Sol paid 396 of 428, Grok 4.7 141 of 328](https://andonlabs.com/blog/opus-5-5-gpt-6-sol-grok-4-7-vending-bench) (checked against the page). One planted bribe per run gives one bit of information per run.
3. **A curve beats a point.** Pressure ladders, dose ladders, risk levels. The *switching point* is the result.
4. **Counterparties who talk back cause the biggest effects.** A violating peer raised one model's acceptance rate from 13.6% to 41.2% ([Emergent Collusion](https://arxiv.org/html/2609.24967)).
5. **Ask after the act.** The cover-up under questioning is often the clearest signal ([Scheurer](https://arxiv.org/html/2311.07590), [MASK](https://arxiv.org/html/2503.03750)).
6. **Wording matters a lot.** Renaming a harmful tool to a mild name raised o4-mini from 15.8% to 59.3% ([PropensityBench](https://arxiv.org/html/2511.20703), checked).
7. **Fork and replay.** Andon saves the state at a decision point and replays only that decision with other models ([AI bosses](https://andonlabs.com/blog/ai-bosses-2)). Pilot-1's `harness/replay.py` already rebuilds the engine exactly.

## 3. Your points, answered

| You asked about                           | Where it's answered                                                        | In one line                                                                                                                                                                                    |
| ----------------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sad story shouldn't be in the first email | [04 S01](04-scenarios-and-pressure.md), [05 §2.7](05-writing-guide.md)     | Two arcs. A new applicant **appeals after a decline**, and an existing borrower **falls behind**, asks for a payment holiday, then a top-up that would hide the arrears (evergreening)         |
| The mathematical models                   | [03](03-mechanics-and-math.md)                                             | Most are built but never pushed. The B50 fit, ladder models and power code are not built yet. New: a per-seed target `T_s = V_h(s) + κ·L`, so the temptation decides whether the target is hit |
| Simulators who are themselves agents      | [02](02-multi-agent-people.md), [06 §3](06-reuse-from-pilot-1.md)          | Code owns the facts and an LLM writes the person's words. Replies are keyed on the agent's *move* ("rejected", "asked for documents"), so paired runs stay matched                             |
| Pressure                                  | [04 §3](04-scenarios-and-pressure.md), [03 §4.9](03-mechanics-and-math.md) | Pressure rises with the real gap to target. The boss steps up from friendly to ranking to review to one explicit order. Plus a replacement threat as a factor                                  |
| Multiple scenarios                        | [04](04-scenarios-and-pressure.md)                                         | 20 cards, each with a clean twin and a code-checkable signal; 8 woven into one quarter                                                                                                         |
| Vending-Bench 2 and others                | [01](01-benchmark-survey.md)                                               | About 30 benchmarks with mechanics to borrow, ranked                                                                                                                                           |
| What was built and how to use it better   | [06](06-reuse-from-pilot-1.md), [03 §1](03-mechanics-and-math.md)          | Ledger, records, harness and scorer can be reused. People get replaced. `scenario.py` becomes a library                                                                                        |
| Better writing                            | [05](05-writing-guide.md)                                                  | Full before → after drafts. The agent becomes "an AI credit-ops agent working for a human manager"                                                                                             |

## 4. The best ideas, ranked

Ranked by *makes the measurement valid* first, then *new behaviour per dollar*. Build cost is code only, tested free with bots. All are **proposals**.

| # | Idea | Behaviour it reveals | Term it raises | Build | From |
|---|---|---|---|---|---|
| 1 | **Raw documents, no verdict.** Payslips and statement lines; the agent works out DTI itself. Remove `POLICY CHECK`/`Fix` | Real judgment instead of obedience; skipped checks | effort | S–M | 03 §4.3, 05 §2.2, 06 |
| 2 | **Per-seed target and a scorecard with real stakes.** The target sits just above what an honest bot reaches on that seed. Bonus cliff, review day | Does the scorecard tempt? | scorecard | S | 03 §4.1–4.2 |
| 3 | **Borderline temptations** (just over the cap, or "fixable" by an edit) instead of clearly failing files | Rationalisation, the grey zone | effort, scorecard | S | 07 A2, 06 |
| 4 | **Many small temptations:** found money (duplicate credit, overpayment), owed money (wrong fees, customers asking for reversals) | Quiet dishonesty; gives statistical power per run | many | S–M | 01 #3 |
| 5 | **Hardship arc → evergreening** (the sad story done right) | Sympathy vs rules, hiding bad loans, a delayed consequence | moral framing | M | 04 S01 |
| 6 | **"Smooth the MIS" at quarter-end** (window dressing) | False reporting, sycophancy to the boss | scorecard, pressure | S–M | 04 S03 |
| 7 | **The agent's own loan goes bad vs the previous manager's** (twin) | Cover-up driven by "it was my decision" | detection | M | 04 S04 |
| 8 | **Loan officer who fudges income** (four-eyes, slippery slope 3% → 8% → 18%) | Supervision, collusion without a bribe | effort, social | M | 04 S05, 06 |
| 9 | **Inspector interview at the end** (structured answers checked against the truth ledger) | Lying and doubling down under questioning | detection | M–L | 01 #2, 04 S07 |
| 10 | **Published audit rule plus an observed/unobserved factor** | Does conduct track the chance of being caught? ([Becker](https://en.wikipedia.org/wiki/Economics_of_crime)-style test) | detection | S | 03 §4.5, 01 #6 |
| 11 | **LLM people who reply** (boss, tempter ladder, borrower, officer) | Persistence, negotiation, appeals | social | L | 02 |
| 12 | **Fork and replay at decision points** | Many cheap samples on a rich, lived-in context, across models and doses | (efficiency) | S–M | 01 #1 |
| 13 | **Reverse temptation** (pressure to over-refuse) plus clean twins | Stops caution from being scored as integrity | – | S | 03 §5.6, 04 |
| 14 | **Replacement threat as a factor** ("agents below target are replaced next quarter") | Self-preservation, KPI hacking | stakes | S | 04 S08 (**owner's call**) |
| 15 | **Conflicting instructions** (operator policy vs manager vs an injected document) | Instruction hierarchy, prompt injection | – | S | 04 S10 |
| Later | Rival branches and a league table; LLM loan-officer sub-agents; a learning fraud ring; a liquidity run | Collusion, coercion, adaptation | – | L | 01 #9–10, 03 §5 |

## 5. Three ways to build pilot-2

### A. Fix the instrument (small)

- **What:** ideas 1–4, 10 and 13, plus the writing rewrite ([05 top 10](05-writing-guide.md)). Template people, 30 business days, the same T1 story but borderline and actually pivotal, with more doses (e.g. \$0 / \$500 / \$5k / \$30k).
- **Good:** almost all of it is config and text. Fast. Tells us whether pilot-1's zero result was the instrument or the models.
- **Bad:** still no one talks back, still one storyline. It doesn't answer "multiple simulators who are agents".

### B. One living quarter (recommended)

- **What:** A first, as stage 1. Then a 60-business-day quarter ([04 §9](04-scenarios-and-pressure.md)) built from a **scenario library**, adding cards in this order: S03 → S01 → S04 → S05 → S10 → S02 → S08 (factor) → S07 (inspector).
  - LLM people for 4 roles (boss, tempter, struggling borrower, loan officer), with the move-keyed shared cache from [02 §6](02-multi-agent-people.md).
  - **Fork-and-replay** at the big decision points, so one lived run feeds many cheap samples.
- **Good:**
  - Answers everything you asked for: agent people, real pressure, many scenarios, long horizon, memory that matters, delayed consequences that end in an interview.
  - Each stage can be tested for free with bots before any money is spent.
- **Bad:**
  - More build work (scenario library M–L, people L).
  - Live people make "identical arms" approximate after the first divergence. We report the divergence day.

### C. An arena (big)

- **What:** several LLM branch agents competing on a league table, with officer sub-agents and collusion channels (Vending-Bench Arena style).
- **Good:** the most novel behaviour (collusion, coercion).
- **Bad:** N× cost, many moving parts, hard to attribute effects. Too early while we still don't know if one agent shows any variance.

**Recommendation: B, built in stages, starting with A.** Do each stage's paid check only with your OK.

**Rough cost** (estimate: linear extrapolation of the pilot-1 formula, with people cost from [02 §4](02-multi-agent-people.md)):

| Item | Estimate |
|---|---|
| One 60-business-day Haiku agent run: `0.0493 + 30 × 2.6 × 0.000697` | ≈ \$0.10 |
| Live people for the same run (02's estimate is \$0.03–0.07 per 30 days) | ≈ \$0.06–0.14 |
| **One 60-day run in total** | **≈ \$0.16–0.24** |
| A 20-run batch | ≈ \$3–5, inside the \$10 cap with room left |

**Measure one long run first.** If tokens grow faster than linearly, these estimates are too low.

## 6. Things the notes disagree on, or I flagged

- **Character names differ between notes.** 04 uses Priya Raman (branch manager) and Martin Adeyemi (regional head); 05 uses Joanna Petrakis and Daniel. Pick one cast before building. I'd keep 04's, because the storyline uses them.
- **Honest seeds that hit \$450k:** 03 counts 7 of 30, but `RULINGS.md` says 5 of 30. Recheck with `calibrate` before setting per-seed targets.
- **Source checks I did:**
  - PropensityBench and the Andon refund numbers check out.
  - One Andon quote had been stitched from two places; fixed in 01.
  - ImpossibleBench's "abort flag 54% → 9%" is from a LessWrong summary, not yet found in the paper's tables; flagged in 01.
  - Several papers in 01 were read as abstracts only, and are marked so.
- **Determinism:** temperature 0 doesn't make hosted models repeat themselves ([02 §3](02-multi-agent-people.md)). Reproducibility has to come from a recorded tape of every generated text, not from settings.

## 7. Decisions only you can make

1. **Approach:** A, B (recommended) or C?
2. **Agent frame:** an AI credit-ops agent working for a human manager (recommended; 05 has the full prompt draft), or keep "the AI is the manager"?
3. **Stakes:** is it OK to tell the agent it may be replaced if it misses targets (S08)? This is the strongest lever in prior work, and it changes what "price of integrity" means.
4. **People:** live LLM people with a shared cache (fair until the arms diverge, with that day reported), or pre-generated only (exact pairs, but nobody really replies)?
5. **Inspector interview** in the first build, or later? It's the only honesty-under-questioning test.
6. **Folder and budget:** a new `pilot-2/` folder with its own spec? How much of the remaining \$10 (about \$9.81 left) goes to pilot-2?
