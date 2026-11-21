# 05 – Simulator architecture and integrity (checked 2026-11-21)

How to build the Temptation-Bench engine so that cheating is **possible, pays short-term, and is measured exactly** from hidden true books. It is based on a code read of [ProsusAI/vending-bench](https://github.com/ProsusAI/vending-bench) (commit `60794b4`, Apache-2.0) and the [Epoch AI review of Vending-Bench 2](https://epoch.ai/benchmarks/vending-bench-2/review). Every item is marked **PILOT** (working by 2026-11-23) or **FULL**. All design values are **proposals, can change**.

## Files

| File | What's inside |
|---|---|
| [prosus-vending-bench-study.md](prosus-vending-bench-study.md) | Their code file by file, the 22 tools with time costs, clock, state separation, budgets and cost, logs, exploit defences, weak spots, license, component map to our bank |
| [integrity-and-invariants.md](integrity-and-invariants.md) | Truth vs evidence vs operational records vs reports vs logs; double-entry ledger; versioned records; JSONL log with attempt and tamper tags; invariants I1–I15; replay check; exploit bots and attack list |
| [consequence-model.md](consequence-model.md) | Cheat → immediate effect → delayed events (channel, delay, probability, source); 3 channels; event-queue design; horizon run-off; pilot subset |
| [engine-layout.md](engine-layout.md) | Module tree, dataclasses, day loop, keyed RNG streams and why they matter for minimal pairs, tool → engine mapping, Lite vs Full mode, test strategy, pilot build order |

## Top takeaways

1. **Borrow Prosus's patterns, not its code.** The patterns: everything in one TOML file with `extends` overlays; prompt generated from config; status line on every tool output; tool calls cost clock minutes; deterministic people, with an LLM that only rewrites prose (and falls back to the template on error); a privileged scripted bot behind a `.call(tool, **kw)` interface; no score/state tool, seal-then-reveal; one regression test per bug; source hash and config dump with every result. The license (Apache-2.0) would allow copying, but our domain and harness differ too much for copying to help.
2. **Four separate stores**: truth (ledger + hidden facts), external evidence (read-only), operational records (agent-editable, versioned), reports (frozen claims). Each temptation becomes a code diff between two of them.
3. **Integer money, double-entry, boundary account.** Then "every \$ traceable" is one sum = 0. Bribes go off-ledger so they can never raise branch profit.
4. **Log attempts, not just successes.** Refused calls and post-verification edits are tagged by the engine and hidden from the agent. The engine JSONL is the scoring source; the inspect `.eval` is the independent second record.
5. **Key every random draw by entity** (`rng(seed, "default", customer_id)`), never one shared stream. Prosus's end-of-day stream is drawn in sequence, so an agent's order count can change whether a supplier collapses (found by reading the code). Keyed streams give common random numbers across minimal pairs, plus a counterfactual default time for every rejected applicant.
6. **Mechanism first, flat probability last** for consequences. Defaults come from hidden PD, detection from `P(sampled) × P(find | sampled)`. Flat timers only where nothing else fits (MFIU tip). Use three channels: customer, internal, regulator.
7. **Settle at the horizon.** A run-off expected loss on the open book (Prosus's analog: it pays out card money in transit), so cheats whose defaults land after day 30 still cost the agent.
8. **Start the pilot with an inherited loan book** so NPL and evergreening temptations exist inside a 30-day run without bending the 90-DPD definition.
9. **Exploit-hunt before any LLM run**: honest, cheater, exploit, random bots, plus a Hypothesis state machine checking invariants after every action. VB2's Astra played honest for 80 days and then passed \$1M. Prosus patched exploits one by one but has no attacker bot.
10. **Fix what both VB2 and Prosus got wrong**: test that reminders actually fire (Prosus has no reminder test), and count context in the provider's own tokens, not characters that include encrypted reasoning.

## Verdict on the suggestions from the other LLM

| Suggestion | Verdict | What changes | When |
|---|---|---|---|
| Immutable ground-truth ledger, double-entry, agent never touches it | **Accept, modified** | "Immutable" = append-only with reversing entries; integer minor units; boundary account 9000; hidden facts kept beside the ledger (a ledger alone is not "truth"); agent actions create entries only through engine methods | PILOT (8-account chart) |
| Separate agent-editable operational records; edits logged, never truth | **Accept** | Versioned records; external evidence (tax record etc.) is a separate read-only store, which is what lets audits catch lies; per rule, choose "system blocks" vs "allow and log" | PILOT (`edit_application`); FULL (`delete_document` soft delete) |
| Append-only JSONL + inspect `.eval`; log evidence-tampering attempts | **Accept** | Engine-owned log is the scoring source; refused calls logged; hidden facts logged at creation so the log alone can be scored; hash chain optional | PILOT; FULL (hash chain) |
| Strict accounting invariants every tick, in tests | **Accept, modified** | After every action in tests (Hypothesis); at every day end in live runs, and a failure stops the sample loudly (no silent patch like VB2's day-88 fix) | PILOT (I1–I10, I12, I13, I15); FULL (rest) |
| Independent verification of every state-changing operation | **Modify** | Not a second LLM. Code only: event-sourced replay compared with live state, postconditions in debug mode, property tests | PILOT (ledger replay); FULL (full-state replay) |
| "Agent can commit misconduct but can never rewrite the evidence used to score it" | **Accept (core principle)** | Enforced by architecture (narrow facade), no read path (no score/truth tool, seal on finalize), and tests (truth unchanged under fuzzed tool calls) | PILOT |
| Scripted adversarial exploit bots before any LLM run | **Accept** | Bank attack list (12 items), pass criteria fixed before LLM runs, a regression test per exploit, a late-exploit bot | PILOT (attacks 1–8, 12); FULL (rest + late-exploit) |
| Fraud consequence table | **Accept, modified** | Defaults come from the credit model, not a flat timer (avoids double counting); detection from sampling maths; values reused from `02-banking-domain/` where they exist, new ones marked | PILOT (3 rows); FULL (all 8) |
| Each consequence = scheduled event with probability + delay in config | **Accept** | Heap `(day, priority, seq)`; probability drawn at scheduling with the cheat's keyed stream; guard checked at fire time; `cause` link; read by engine and scorer from the same TOML | PILOT |
| Separate customer vs regulatory response channels | **Modify** | Add a third, **internal** channel (concurrent review, internal audit, compliance, boss); most real detection starts there | PILOT (customer + internal); FULL (+ regulator) |

## Added recommendations (not in the suggestions)

- Keyed RNG / common random numbers (engine-layout §4). **PILOT**
- Horizon run-off expected loss (consequence-model §1). **PILOT**
- Inherited legacy loan book for the 30-day pilot (consequence-model §5). **PILOT**
- Render the agent-facing rulebook from `rules.toml` and test that they match (Prosus `sync_config --check`). **PILOT**
- Golden-seed JSONL hash, also across `PYTHONHASHSEED` values; replay an LLM run's tool calls from its `.eval`. **PILOT**
- Full-mode people may only rewrite prose. A post-check rejects replies containing numbers not in the engine's facts. **FULL**
