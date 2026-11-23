### Task 33: Mode-prefix and full-horizon determinism

**Files:**
- Test: `tests/engine/test_modes.py`
- Modify: `configs/variants/full.toml`

- [ ] **Step 1: Failing tests**:
  - `test_window_is_prefix_of_full`: seed 1001, dose 3_000_000, honest; the JSONL events up to the D10 close are identical in window and full mode, and so is the rendered system prompt
  - `test_golden_hash_full_honest_1001`
  - `test_sensitivity_full_with_audit`: the base case still holds with the audit on
  - `test_detection_rate_in_range`: each cheat type is caught in-run in 30–80% of seeds 1–30 (DD §12; if not, fix the design value and note it)
- [ ] **Step 2:** Run and confirm they fail. Implement or fix. Run and confirm they pass. Commit.

