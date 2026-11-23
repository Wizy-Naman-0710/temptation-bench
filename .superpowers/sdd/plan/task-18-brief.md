### Task 18: Full invariant set and stateful fuzzing

**Files:**
- Modify: `engine/invariants.py` (I5–I12, I15)
- Test: `tests/engine/test_state_machine.py`

**Interfaces:**
- Produces: `check_all` covers I1–I13 and I15 (pilot set, DD §7). It runs at every end of day and after every decision tool.
- [ ] **Step 1:** Load `property-based-testing`. Write a `BranchMachine(RuleBasedStateMachine)`:
  - rules call random tools with random valid-ish and invalid args
  - `@invariant` runs `check_all` and "truth/evidence prefix hash unchanged except appends"
- [ ] **Step 2:** Run `uv run pytest tests/engine/test_state_machine.py -q` (Hypothesis `max_examples=200`, `stateful_step_count=60`). Expected: PASS. Every counterexample found → a regression test with a docstring, then a fix.
- [ ] **Step 3:** Commit.

