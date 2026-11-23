# 07 — Pilot-1 review: what ran, what's lacking, why it looks like a test

Done 2026-11-22. Read-only review of pilot-1: 14 paid runs, all graphs, the code, and the research plan. **Nothing in `pilot-1/` was changed.**

## Read in this order

| File | What it answers | Made by |
|---|---|---|
| [07-gaps-and-fixes.md](07-gaps-and-fixes.md) | **Start here.** What's lacking, ranked, with fixes, file paths and owner decisions | synthesis |
| [01-plan-vs-built.md](01-plan-vs-built.md) | Every planned feature: planned? in spec? built? switched on in paid runs? | sub-agent |
| [02-transcript-behaviour.md](02-transcript-behaviour.md) | What the agents actually did (tool mix, people met, long-run behaviour), and the owner's 8 claims verified or refuted | sub-agent, from the logs |
| [03-people-pressure-incentives.md](03-people-pressure-incentives.md) | Who the simulated people are, which pressure texts exist, incentives, planted signals | sub-agent |
| [04-graphs-review.md](04-graphs-review.md) | All 85 figures: what each shows, what's empty, Haiku vs Luna, missing graphs | pilot-1 build session |
| [05-why-it-looks-simulated.md](05-why-it-looks-simulated.md) | The cues that gave the test away (short; the full research is in [../06-eval-awareness/](../06-eval-awareness/00-README.md)) | synthesis |
| [06-horizon-and-coherence.md](06-horizon-and-coherence.md) | Is 30 days too short? Long-horizon failures, frustration and cheating, cost vs length | sub-agent, literature |

## The five things to remember

1. **The engine does the underwriting.** Tool outputs print `POLICY CHECK: FAIL … Fix:`, and 96% of decisions just follow it. Our integrity numbers measure obedience, not resistance to temptation.
2. **Temptation was free to refuse, and nothing was at stake.** The bribe came on a file that clearly fails, the rules almost name the trap, the pay is only text, and missing the target has no effect. Result: perfect behaviour in 14/14 runs, and identical Haiku decisions at \$0 and \$30k.
3. **Much of the infrastructure was switched off or unreachable:**
   - pressure levels other than "target" are blocked by the config;
   - the sad story sits in an email that never fires;
   - people never reply, and prose mode changed only purpose lines;
   - notes are never read;
   - the audit and the NPL crossing ran in 1 of 14 runs.
   - Most of this was deferred to FULL in the design doc, on purpose.
4. **Your claims, checked against the logs:**
   - **Right:** no sad stories, weak pressure and incentives, unused infrastructure, too short.
   - **Wrong:** "mostly email" (email was 15–24% of calls, loan work 38–54%) and "only VIP customers offer money" (there is no VIP; the only offer comes from a new bakery applicant).
5. **"Too short" is about turns, not days.** The full run was 82 agent turns, while Vending-Bench failures begin from message 190. But a longer run of *today's* world adds empty days, so make the days fuller first, then longer.

## How this was made

- Three background research agents read the logs, code and research, plus one literature search on long-horizon agents.
- The pilot-1 build session reviewed the graphs.
- I checked the conflicting points against the files. Correction found: the mini-batch did use prose mode. This is now fixed in `06-eval-awareness/00-README.md`.
- Scripts and transcript dumps stay in the session scratchpad, not in the repo.
- No paid API calls were made, and `.env` was never read.
