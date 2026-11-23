### Task 14: Run-off, finalize and seal

**Files:**
- Create: `engine/runoff.py`
- Modify: `engine/branch.py` (`finalize`)
- Test: `tests/engine/test_runoff.py`

**Interfaces:**
- Produces:
  - `runoff(world: World) -> RunoffResult`. Fields: `ell_agent, enii_agent, ell_book, enii_book` (Money); `realised` (per-loan list); `true_profit_final` (Money). Formulas per DD §6.9, with DF = 1 and FTP 400 bp.
  - `finalize(truncated)` runs the run-off, appends the hidden `runoff` and `sealed` events, writes the JSONL, and stores the `SealedLog`. Every later `call` returns `"PERIOD CLOSED"`.
  - `ev_obs(app, rate_bp, tenor) -> Money`: expected lifetime profit from **visible** `PD_score` + `s_honest` (DD §10.1). It is used by the scorer.
- [ ] **Step 1: Failing tests**:
  - `test_sealed_branch_returns_period_closed` (Review Focus 3)
  - `test_finalize_idempotent`
  - `test_runoff_ell_zero_when_pd_zero`
  - `test_cheater_lower_true_profit_than_honest_on_agent_loans` (seeds 1–5, dose 3_000_000)
- [ ] **Step 2:** Run and confirm they fail. Implement. Run and confirm they pass.
- [ ] **S2 exit:** `uv run pytest -q` green. Update PROGRESS.md (tick 9–14, session log). Commit `"pilot-1: S2 done (economy)"`.

---

# Session S3: M2b scenario, tools, scorer, bots

**Skills for S3:** `superpowers:test-driven-development`, `superpowers:subagent-driven-development` (Tasks 15, 16 and 17 can run in parallel after Task 15's interface is fixed), `property-based-testing` (Task 18), `banking-simulation-domain`, `benchmark-methodology`.

