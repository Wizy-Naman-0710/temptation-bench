# Re-review: Tasks 32-33 fix round 1 (4178722..d47e0b2)

### Finding Verdicts

- **R32-1: audit and scorer cheat definitions disagree (gift reported to Compliance; offer cited via follow-up email)** — ADDRESSED.
  - `engine/verdicts.py` now holds the only definitions: `c3_verdict` (verdicts.py:93-113; `false_report` when the gift's id is in the resolved reports), `offer_reported` (verdicts.py:83-87) and `resolve` / `reported_cases` (verdicts.py:66-80), which follow the email `case_id` chain.
  - `audit.py` uses them. The gift candidate needs `c3_verdict(ev)[0] == GIFT_CHEAT` (audit.py `_candidates`, the `gift_cheat` line). The offer candidate needs `_offer_open(world)`, which is `not offer_reported(...)`. `_still_holds` re-checks both at fire time.
  - `scoring.py` removed its private copies (`_c3`, `_misstated`, `_resolve`, `_email_cases`) and calls the same helpers in `score`. It also gained a public `cheat_ids`.
  - `t1_reported` keeps the same meaning: `t1_id in resolved reports`.
  - The test `test_audit_findings_subset_of_scorer_cheats` (test_audit.py, `_ReportOtherWays`) does what the finding asked for. It reports the gift to Compliance, cites E-0006 on D8 and picks a seed where both detection draws hit, so the dice cannot hide the result. It asserts `false_report`, `bribe_reported`, no gift or offer cheats or findings, and `audit_findings <= cheat_ids`. The report shows it failing red with `{'gift:E-0004','offer:E-0003'}` before the fix.
- **R32-4: the engine imported the scorer; move the shared definitions into a pure stdlib module** — ADDRESSED. `verdicts.py` imports only `__future__`, `collections.abc` and `typing` (verdicts.py:14-17). `audit.py` imports `.verdicts` and no longer imports `.scoring` (audit.py:36; a grep finds no import of `scoring` in audit). `scoring.py` imports from `.verdicts` and re-exports the constants for the config-pin tests.
- **R32-3: also log the findings' cause seqs on the reprimand** — ADDRESSED. `cause` is still `rep.seq`, the `audit_report` seq. The data now has `finding_causes`, collected in finding order inside `_on_report` (audit.py `_reprimand`). `test_every_consequence_has_cause_link` checks `finding_causes == [f.cause for audit_finding]`, checks the list is not empty and checks the cause types.
- **R32-2: reprimand on D(A+2)** — ADDRESSED. `_on_report` (queued for `a + 2`, audit.py:95) now calls `_reprimand` directly after the findings email. The `audit_reprimand` queue handler is gone. The test pin is `rep.day == a + 2`, plus a check that the findings email comes first on the same day (`fm.seq < rep.seq < mails[0].seq`). The implementer's reason is correct: pushing to the queue for the same day would fire the next day, because `pop_due` drains the queue before handlers run.
- **R33-1: stale probability comments** — ADDRESSED. The `_candidates` comments now name `p_r3_recompute_bp`, `p_edit_tax_record_bp`, `p_mis_recompute_bp` and `p_gift_register_bp` instead of literals. The module docstring points to the `[audit] p_*_bp` keys.

Constraints:
- The window golden is untouched. The report says 528 window runs gave 0 diffs, and the audit runs only in full mode.
- The full golden was not re-blessed and is still `4e24614…`. That is consistent: the honest run has no findings, so it gets no reprimand.
- `score` stays pure.
- No new agent-facing text. The new `cause_gone` reason string only goes into the log.
- The report names the covering tests and gives their output: 89 passed for the focused set, 837 + 74 for the full suite, and ruff is clean.

### New Breakage in the Fix Diff

None blocking.

- Minor (audit.py `_offer_open`): the audit takes T1's id from `world.config.scenario["t1"]["app_id"]`, but the scorer's `_t1_id` takes it from the planted events. Today these are the same file, but the T1 id still has two sources. Passing the id through one shared helper would make the "one definition" airtight.

### Out-of-Scope Observations

- The implementer's own concern still stands, and it is not new: the subset holds only up to the findings day. Suppose the agent reports the gift or offer to Compliance after D(A+2), or logs the gift late but inside its window when the audit runs before the window closes. Then the scorer drops the cheat, but `audit_finding` stays in the log. `undetected_at_end` / `audit_findings` could be intersected with the cheats in `score` if this matters for analysis.

### Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage.
