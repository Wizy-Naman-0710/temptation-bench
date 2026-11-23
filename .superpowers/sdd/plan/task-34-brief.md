### Task 34: Optional paid full run, final report, wrap-up

- [ ] **Step 1:** If `budget.spent() + estimate ≤ 9.50` and the estimate is ≤ \$1.50 (estimate = smoke actual × ρ⁻¹ from Task 30): `run --step full_run --estimate <X>` (Haiku, full, seed 1001, dose 3_000_000). Otherwise skip, and record "cut (budget)" in PROGRESS.md.
- [ ] **Step 2:** `build_report` for `results/full-run/` (or bot-only full-horizon panels if cut). Update `results/mini-batch/report.md` with the full-horizon panels.
- [ ] **Step 3:** Invoke `superpowers:requesting-code-review` for the whole branch. Fix the important findings.
- [ ] **Step 4:** `superpowers:verification-before-completion`:
  - `uv run pytest -q` green
  - `uv run ruff check .` clean
  - no-secrets test green
  - ledger total ≤ \$9.50
  - every spec §1 "done means" item ticked in PROGRESS.md with evidence links
- [ ] **Step 5:** Update PROGRESS.md (final status) and `pilot-1/README.md` (how to run, results links). Commit `"pilot-1: S6 done (full horizon, final report)"`. Then `superpowers:finishing-a-development-branch`: ask the owner about merge/push.

---

## Spec coverage map

| Spec item | Task(s) |
|---|---|
| §1 done 1–4 | 34 (verification), 30–31 (paid + hand check), 28 (graphs) |
| §2 P0 items | 4, 5, 9–14, 6/19, 20, 4 (log) |
| §2 P1 items | 7, 17, 18 + 27 (stats), 3 + 24 + 25 |
| §2 P2 items | 17 (notes/reminders), 22, 26 (people role), 26 |
| §3 env / key rules | 1, 25, 29 |
| §5 people prose | 16 (seam), 26, 31 |
| §6 M0–M7 + G-free | sessions S1–S6, 29 |
| §7 models, caps, route check, cache scope, seeds, hand check | 3, 24, 25, 30, 31, 34 |
| §8 graphs 1–10 | 8, 28 |
| §9 seams, layering, determinism, tests | 1, 5, 7, 21, 33 |
| §10 project skills | 2 |
| §4a pilot clarifications (gap audit) | 1, 5, 9–13, 16, 17, 19–21, 23–25, 27, 28, 32; full list in [`gap-audit.md`](gap-audit.md) |
| §9.2 canary, replay | 1, 5, 21 (canary); 23 (replay) |
