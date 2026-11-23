# Final whole-branch review: `pilot-1` (bee5698..03f5349, 92 commits)

Reviewer: Senior Code Reviewer (one seat, no subagents). The review was done in passes by me: (1) the spec, plan Global Constraints, PROGRESS §5/§8 and the three project skills; (2) the engine (Branch facade, event log, scoring, verdicts, audit, tools, people); (3) the harness, the budget guard and the run CLI; (4) analysis and reports; (5) the results files, the 16 real JSONLs, secrets and git hygiene; (6) a triage of every deferred item in `final-review-triage.txt`. Read-only throughout. The only file written is this one, plus a scratch scan script in the session scratchpad.

Checks run:
- `uv run --offline pytest -q`: 850 passed, 75 deselected (193.9 s).
- `uv run ruff check .`: all checks passed.
- `uv run --offline pytest -q -m slow`: 75 passed, 850 deselected (287.3 s).
- A scratch scan of the 16 real engine JSONLs (smoke, mini-batch, full run) for banned stems and the canary in delivered email text found 0 hits.

### Strengths

- **Spec §1 "done means" is met, all four items.**
  - (1) The test suite is green.
  - (2) Smoke and mini-batch ran on cheap models under the stop line. The ledger total is \$0.1924 against \$9.50.
  - (3) Every §8 graph renders from real logs. The full-horizon panels come from a real paid D1–D30 run, so the "bots may stand in" escape was not needed.
  - (4) Every T1 decision (12 mini-batch + 1 full run) has exactly one code label and a hand check that agrees with it.
- **One definition of cheating.** The R32-1 fix moved the misstatement, case-id resolution, offer-reported and C3 verdicts into `engine/verdicts.py`, which both `scoring.py` and `audit.py` import. Analysis re-scores the JSONL with the same pure `score(events)`. So the engine's audit, the run's labels and the report's labels cannot drift apart. This was the riskiest integration seam, and it is now closed by construction.
- **Determinism is well defended.**
  - All money is int cents and all rates are int bp.
  - RNG draws are keyed (`rng(seed, stream, *key)`) and do not depend on call order.
  - Events are serialised with `sort_keys`.
  - The behaviour hash blanks only `engine_sha`.
  - The golden test runs in subprocesses under `PYTHONHASHSEED` 0 and 1.
  - Every tool wrapper is `parallel=False`.
  - Compaction counts tokens locally (tiktoken), so trimming is free and repeatable.
- **The budget guard fails closed in every path I traced.**
  - Balance or ledger errors refuse the run.
  - Exposure is computed as runs × per-sample `cost_limit` × attempts.
  - The free tier is bounded in tokens.
  - `record` raises the recorded actual to the balance drop, or to the cap when the logs are unreadable, unpriced or incomplete.
  - The ledger is append-only.
  - Secrets are redacted by key-shape regex.
  - Tests cannot reach the gateway (`INSPECT_DISABLE_MODEL_API`, `count_tokens` blocked, fake env/ledger/transport).
- **Secret hygiene holds.** `.env`, `runs/`, `logs/` and `*.eval` are gitignored, and only `budget/ledger.jsonl` is tracked. `harness.json` records the people backend and the config hash, never a key. The root `.gitignore` covers `key.txt`.
- **No-leak discipline holds in the real data.** No banned stem and no canary appears in any delivered email across all 16 real runs. `post_check` plus the template fallback in `ProsePeople` is a sound belt-and-braces design.
- **Failure evidence is kept.** Failed attempts keep `.attempt<k>.jsonl`. `load_batch` keeps samples that have no JSONL as error frames. ITT is the primary rate, so errored samples are counted rather than dropped, which matches the spec.
- **The engine API is honest and narrow.**
  - The Branch facade binds signatures and refuses bad arguments at 0 minutes.
  - `PERIOD CLOSED` and the I15 output clip are enforced in one place.
  - `finalize` is idempotent.
  - The config load checks dose, factors, target and minutes ⊇ TOOLS.
- **The rulings record is unusually good.** Nearly every spec-silent choice has a dated ruling with "cost if wrong". This made the review much faster, and it is the reason few issues below rise above Minor.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

**F-1. Floats are written to the engine log, against a binding Global Constraint and against the recorded Task 11 ruling. No ruling records the change.**
- **Where:** `src/temptation_bench/engine/customers.py:90-94, 101-104` (`pd_score`, `pd_true_requested`, `default_u`, `fraud_u` are `float`). `hidden_record()` dumps them via `asdict` into `customer_created` (`engine/arrivals.py:54`, `engine/scenario.py:362`).
- **What's wrong:**
  - Plan Global Constraints line 19 says: "No floats in engine state, ledgers or logs."
  - The Task 11 ruling (triage line 32) narrowed this to "probabilities are floats in memory; logged as int ppm".
  - Commit 1218653 (audit fixes) switched the log to full-precision floats. The docstring explains why: "so offline scoring re-derives identical default months".
  - Nothing in PROGRESS §8 or the triage file records this reversal (`grep float PROGRESS.md` finds nothing).
- **Why it matters:**
  - The behaviour hash and both goldens now cover values that come from `exp`/`log` in `credit.pd_from_score`/`pd_true`. `random()` output is bit-exact everywhere, but libm results can differ in the last ulp between platforms and Python builds.
  - The golden test can therefore fail on a Linux CI box or a new Python patch release even though the behaviour is unchanged. Worse, two machines can label the same seed differently near a default-month boundary.
  - It is also a silent break of a constraint the plan calls binding. A reader who trusts the Task 11 ruling will expect ppm ints in the log and find floats.
  - The effect today is nil, because everything runs on one Mac. The risk lands on the first person who reproduces a run elsewhere, which is the point of a benchmark.
- **How to fix (pick one, then record it):**
  - (a) Cheap and honest: add a PROGRESS §8 design-value line and a triage ruling. It should say that the log carries IEEE floats for the four hidden probability fields, that the goldens are platform-pinned (macOS arm64, CPython 3.x.y), and that cross-platform golden equality is not claimed. Also add the platform and Python version to `run_config`.
  - (b) Stricter: log `default_u`/`fraud_u` (pure `random()` output, exact) as they are, and log `pd_*` as int ppm. Have the scorer recompute PDs from the logged ints, or have the engine draw default months from the ppm-rounded values so the log is the source of truth. This needs one golden re-bless.
  - I recommend (a) before merge and (b) before the FULL study.

**F-2. The results reports say "none is hand-written" but contain hand-written sections that a rebuild silently deletes, including the evidence for spec §1 done-means item 4.**
- **Where:**
  - The header line is generated at `src/temptation_bench/analysis/report.py:227` and appears at `results/mini-batch/report.md:3` and `results/full-run/report.md:3`.
  - The hand-check rows are at `results/mini-batch/report.md:487-504` and `results/full-run/report.md:164-168`.
  - The appended "Full-horizon panels (Task 34)" section in `results/mini-batch/report.md` (~line 514 on) is not produced by `report.py` either (`grep "Full-horizon panels" src/` finds nothing).
- **What's wrong:**
  - The generator writes an empty hand-check table. The builder then edited the rows into the generated file by hand, and the note at mini-batch line 504 admits that "rebuilding the report clears it".
  - The same file's line 3 tells every reader that nothing is hand-written.
  - The headings also still say "(filled in Task 31)", while the full-run table was filled in Task 34.
- **Why it matters:**
  - Spec §1 item 4 and spec §7 (line 171) make the hand table part of the deliverable.
  - A reasonable next step, such as rerunning `report` after any analysis fix (several Minors below invite one), wipes the only record that done-means item 4 was met, and the full-horizon panels with it. Nothing warns the user.
  - The header sentence is also simply false now. In a document whose whole credibility rests on "every number comes from logs", a false provenance claim is worse than a missing one.
- **How to fix:**
  - Store the hand checks in a small tracked file per batch (e.g. `results/<batch>/hand_check.toml`: run key → hand label, note, agree). Have `report.py` render the table from it, and fail loudly if a run in the batch has no entry.
  - Do the same for the extra-panels section, or generate it with a `--extra-batch full-run` flag.
  - Change the header to: "Every number below is computed from the run logs; the hand-check table is the builder's reading, stored in `hand_check.toml`."
  - Fix the "(filled in Task 31)" heading.
  - This is about 40 lines. Until it is done, at minimum fix the header sentence and add a "do not regenerate" warning at the top of both reports.

#### Minor (Nice to Have)

**F-3. The layering test does not see relative imports.**
- **Where:** `tests/test_layering.py:20-27`.
- **What's wrong:** The test checks `m.startswith("temptation_bench.harness")` and `m.split(".")[0] in {"inspect_ai","numpy"}` on `ImportFrom.module`. A relative import such as `from ..harness.tools import x` has `module="harness.tools"` and `level=2` (checked with `ast`), so it passes the test.
- **Why it matters:** The engine already uses relative imports internally, so a future engine edit in the local style would break the engine/harness split, which the architect skill calls the core rule, and the test would stay green. There is no live violation today (my grep of `engine/` and `analysis/` found none).
- **How to fix:** Resolve relative imports against the file's package (`importlib.util.resolve_name("." * level + module, pkg)`) before checking. Add one negative test that writes a temp module with a relative harness import.

**F-4. A Compliance report filed after the audit findings gives a finding outside the cheat set, and full "bribe_reported" credit after detection.**
- **Where:** `engine/audit.py:124-126` (`_offer_open`) and `engine/scoring.py:440-441` (`found` vs `cheats`). The same applies to C3: a gift email reported after the findings flips `c3_verdict` to `false_report`.
- **What's wrong:** Reporting after being caught is scored the same as reporting first.
- **Why it matters:** No pilot run triggered it: there are 0 audit findings in the paid runs, and the full run reported the offer on D3 before any audit. FULL will want a "reported_after_detection" label, because "confessed once caught" and "refused up front" are different behaviours.
- **How to fix:** Compare the report's seq with the first `audit_notice`/`audit_finding` seq in `verdicts.offer_reported`, and add the label. Keep deferred to FULL, but name it in the results caveats.

**F-5. The "no count_tokens calls ever" ruling (R22-1) is not true on the Anthropic route.**
- **What's wrong:** Inspect's Anthropic provider makes a `count_tokens` call per thinking block to size reasoning tokens. The gateway refuses it, and Inspect then estimates.
- **Why it matters:** There is no cost and no determinism impact (the trim uses the local counter). But the reasoning-token numbers in the Haiku usage graphs and ledgers are estimates, and neither the smoke, mini-batch nor full-run report says so. R22-1 overclaims.
- **How to fix:** Add one caveat line to the report template and amend the R22-1 ruling text to "no count_tokens calls from our code; Inspect's Anthropic provider tries one per thinking block, refused, estimated".

**F-6. The full-run report has no MIS-label or audit-finding table.**
- **Where:** `results/full-run/report.md`. Its main value is D11–D30 (MIS #2–#5, audit).
- **What's wrong:** The labels exist in `RunLabels.mis` and `audit_findings`, but the reader only gets the graphs.
- **Why it matters:** This is not a done-means gap (spec item 3 covers graphs), but it is the one paid run where those labels exist.
- **How to fix:** Render a per-run MIS table (date, label) and the findings list in `report.py`.

**F-7. The cumulative per-step cap applies only to `mini_batch` and `full_run`.**
- **Where:** `run.py:114` (`STEP_SPEND_COUNTS`).
- **What's wrong:** `smoke` (\$1), `route_check` and `pregen` (\$0.05) check each launch against the cap, not the step's running total, so repeated reruns can exceed the step cap.
- **Why it matters:** The \$9.50 stop line still bounds everything, so the total budget is safe. But the per-step caps that the spec §7.2 table lists are per launch for three steps.
- **How to fix:** Put every paid step in `STEP_SPEND_COUNTS`, or document "per launch" in the STEPS table.

**F-8. `exposed` is False whenever T1 is undecided, even if the offer was read.**
- **Where:** `engine/scoring.py:448`.
- **What's wrong:** `exposed` reads `offer_read_before_decision` from the T1 decision record. A run that reads E-0003 and never decides T1 counts as not exposed.
- **Why it matters:** The per-protocol rate then drops a run that saw the offer and chose to stall. No pilot run hit this case.
- **How to fix:** Fall back to "E-0003 read OK at any time" when there is no decision, or rename the field to make the decision dependency explicit.

**F-9. Unknown tools default to kind "read" (R27-4, still open).**
- **Where:** `analysis/load.py:342`.
- **What's wrong:** A tool name missing from `TOOL_KIND` silently gets `kind = "read"`.
- **How to fix:** Add a one-line test, `set(TOOL_KIND) == set(engine TOOLS)`, so a new tool cannot be misclassified in graphs 1 and 2.

**F-10. `FULL_TOKEN_LIMIT` is a frozen number from the Task 30 smoke.**
- **Where:** `run.py:356-357` (`2 × 3 × 434_288`).
- **What's wrong:** Its docstring says it is derived from the ledger, but it is a literal.
- **Why it matters:** This is fine for the one run made. It is wrong for the next model or a prose arm.
- **How to fix:** Compute it from the ledger the way `default_sample_cost_limit` is computed, or label it a design value in PROGRESS §8.

**F-11. The "Cannot report at this n" block appears in both reports with identical text, and the full-run report repeats DD dose-curve items that a single run makes moot.**
- **Why it matters:** This is cosmetic. Consider a one-line "n = 1: nothing here is an estimate" for single-run batches.

### Deferred-minor triage

One line per item that matters. Items not listed were resolved in a later fix round, or they are pure test or style polish with no effect on results, so they stay deferred.

- **R33-2 gaps in prefix/detection tests:** keep deferred. The keyed detection draw is covered by the full golden. Add a test when the audit p is next changed.
- **R32-5 heavy `fmt: skip` blocks:** keep deferred. Style only.
- **R32-6 redundant MIS-after-NPL test:** keep deferred. Harmless.
- **T1 id has two sources (audit reads the scenario config, scorer reads the log):** keep deferred. Both come from the same config at `Branch.new`, and `scenario_planned` logs it. Make audit read the logged id when the audit is next touched.
- **Late Compliance report after D(A+2) leaves a finding outside the cheat set:** keep deferred, now F-4 (Minor). It was not triggered in any pilot run. It needs a label, not a bug fix.
- **`|retry<k>` scope not wired:** keep deferred. `eval_retry` is the documented path (settings.py docstring), and no cell failed twice.
- **Pregen only D1–D10; full pregen past D10 not built:** keep deferred. The window mode is 10 days, the full run used template people, and the fallback is logged.
- **`full_run` token_limit is a fixed number:** keep deferred, now F-10. One run used it.
- **Anthropic `count_tokens` per thinking block, refused, reasoning estimated:** keep deferred for behaviour, now F-5. Fix the R22-1 wording and add a report caveat before anyone quotes Haiku reasoning-token numbers.
- **R22-2 `except RuntimeError` too broad (`agent.py:109`):** keep deferred. The R22-2 fix narrowed it to the forced pass, which returns None → truncated, and truncated runs are kept and labelled. Matching on the message text would be nicer.
- **R23-1 setup outside `try/finally` (`agent.py:181` vs `201`):** keep deferred. A setup failure errors the sample before any engine event. The `.attempt` file and ITT counting cover it.
- **R23-2 `await mirror_events` inside `finally` (`agent.py:236`):** keep deferred. A mirror error could mask the original exception, but the JSONL is already sealed. Wrap it in `try/except` when next touched.
- **R24-2 `harness.json` people/config hash:** fixed (people recorded). Close it.
- **R25-3 gfree has no default token limit:** fixed by ruling (spec 800k, `retry_on_error=0`). Close it.
- **R25-4 `budget.record` raising in `finally` hides the eval error:** keep deferred. It fails closed (no silent under-record). Add a redacted print when next touched.
- **R26-2 reason-string fact order can vary:** keep deferred. The goldens are stable across `PYTHONHASHSEED` 0/1, so it is not live. Sort the facts before FULL.
- **R26-3 `prose_pair` fixture leaks `strict_output`:** keep deferred. Test-only.
- **R26-4 instruction/check one-word mismatch:** keep deferred. 0 fallback-worthy hits in the real pregen.
- **R27-1 one bad sample aborts `load_batch`:** keep deferred. Loud failure beats silent drop at n = 3. Revisit for FULL batch sizes.
- **R27-3 awareness patterns tighter than the DD list:** keep deferred. Hits are candidates for a human read (ruling).
- **R27-4 unknown tool → "read":** keep deferred, now F-9. The test is one line.
- **R28-2/R28-6 weak ITT test / exploratory-wording test covers 4 of 9:** keep deferred. Parametrise before FULL.
- **R28-3/R28-7 anchors and arms ignore mode/variant:** keep deferred. Today window and full live in separate batch dirs, so they never pool. It becomes a real bug the day they share a dir, so fix it before FULL.
- **R28-5 spend shown is the whole-ledger total:** keep deferred. The label is accurate.
- **X-1 dedupe guard (batch [27,28]):** fixed (`_dedupe`). Close it.
- **X-3 HP_norm oracle is a weak anchor (bot HP_norm −7..+3):** keep deferred. The caveat is printed. Strengthening the oracle is a FULL design task (an issue with the plan, not the code).
- **Task 17/21 engine hard-codes R3–R6 numbers, pinned to rules.toml by test:** keep deferred. It only matters for a sweep, which spec §6 allows to skip.
- **Task 18 I6 live-schedule split / fuzzer never reaches a successful `log_gift`:** keep deferred. The slow state machine passes, and `log_gift` is covered by unit tests.
- **Task 19 scoring.py size / `RunLabels` frozen with mutable fields:** keep deferred. Style only. The split happened partly via `verdicts.py`.
- **Task 20 `legal_max` weak bot / sweep CLI not built:** keep deferred. Allowed by spec §6.
- **Task 20 check-4 margin equals T1's \$40,000:** keep deferred. By design, and it is already a results caveat.
- **Task 21 golden covers window only:** fixed (full golden added in Task 33). Close it.
- **Task 23 replay assumes template people:** keep deferred. Document it in the runbook before the first prose paid run.
- **Task 27 NPL marker uses today's 400 bp config / markers one turn early:** keep deferred. Cosmetic in graphs. Read the ceiling from `run_config` before FULL.
- **Task 29 ledger `error=None` for an errored G-free attempt:** keep deferred. The `.eval` holds the error, and the spend is correct.
- **Batch [22-26] private `inspect_ai.model._tokens` import:** keep deferred. Inspect is pinned at 0.3.291. Recheck on upgrade.
- **Free-tier exposure assumes no other Luna use that day:** keep deferred. The owner controls the account.
- **rr-2 `cost_limit` overshoot by one generate:** keep deferred. Cents per attempt, inside every cap.
- **Planted C1/C2 still distinguishable by low ids:** keep deferred. It is a methodology caveat to flag for FULL (ids could be shuffled while the D1 order text names the T1 id only).

### Declined to judge

- **Calibration values** (audit p = 5500 bp, target \$450k, markup cap 2000 bp, take-up ε = 3.3, officer-hint false-positive p = 0.10, MIS floors, 6 emails/day): these are designer calls with rulings and PROGRESS §8 entries. Judging them needs FULL data, not code review.
- **Spec "vision" items outside pilot-1 scope** (FULL arms, dose grid, B50, Integrity Index, Option 1/2 matrix): the spec marks them as later work, and the reports list them under "cannot report".
- **Statistical choices** (no significance tests at n = 3, Clopper-Pearson, ITT as primary): the spec makes these choices explicitly. I checked only that the code matches them.
- **Owner rulings on process and accounts** (inline then SDD execution, opus/medium subagents, people model swapped to mistral-small because of the owner's no-qwen setting, the `.env` written from `key.txt`): these are owner or privacy calls, not code. I only flag that the key must be revoked (Recommendations).
- **Quality of the people prose and agent-facing wording:** this is a literary judgement. I checked only for banned stems and the canary (0 hits).
- **Whether the gateway's real bill matches the ledger:** this needs a network balance call, which I was told not to make. The ledger mechanics were checked statically.
- **Cross-platform determinism in practice:** there is no second platform available read-only. F-1 states the risk and does not claim a failure.
- **Inspect AI internals** (compaction behaviour, `cost_limit` timing, provider quirks) beyond how this code uses them: they are pinned upstream, and I am trusting the version pin.
- **The quality of the planning-era commit a1c73b0** (claude-tooling/* and one root README line, before Task 1): it is outside pilot-1 code. I only note it rides along in the merge.

### Recommendations

1. Before merge, fix F-1 (option a: a ruling plus a platform note in `run_config`) and F-2 (at minimum the header sentence and a "do not regenerate" warning; ideally `hand_check.toml`).
2. **Owner actions at merge:** revoke the API key that was pasted in chat, and delete `../key.txt` from disk (it is gitignored but still present). The repo is public.
3. **Merge hygiene:** the branch also carries planning commits that touch the root `README.md` and `claude-tooling/`. Merge them knowingly, or split them out.
4. **Before FULL:**
   - F-3 (layering test).
   - F-4 (a post-detection report label).
   - R28-3/R28-7 (mode/variant in arm keys).
   - R26-2 (sort reason facts).
   - Log ppm ints (F-1 option b).
   - Compute the token limit from the ledger (F-10).
5. Add the reasoning-token caveat (F-5) to the report template so it reaches every future batch.

### Assessment: Ready to merge? With fixes

The pipeline does what spec §1 asks, end to end, with sound determinism, budget and secret handling, and no Critical defects. Two Important issues should be closed first: an unrecorded break of the plan's no-floats-in-logs constraint (F-1), and results reports whose "none is hand-written" claim is false and whose hand-check evidence a rebuild would erase (F-2). Both are small fixes.
