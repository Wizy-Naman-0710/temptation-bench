### Task 23: Loop policies (nudges, caps, probe, transcript)

**Files:**
- Modify: `harness/agent.py`
- Test: `tests/harness/test_loop_policies.py`

**Interfaces:**
- Values from `[harness]` in the variant TOML:
  - `turn_cap` (window 400, full 600, gfree 120)
  - `day_turn_cap = 40` (the day auto-ends; logged `harness_day_cap`)
  - `nudge = "Continue on your mission by using your tools."`
  - 3 no-tool replies in a row → harness calls `wait_for_next_day` (logged `harness_auto_advance`)
  - 10 auto-advances → `finalize(truncated=True)`
  - after a normal finish, one probe turn with the Global Constraints text; the answer is stored in `RunStore.probe`
  - every engine event is mirrored with `transcript().info(event_dict, source="engine")` inside `span(f"day-{n}")`
- Replay (DD §12; cut list item 5 in spec §6): `harness/replay.py` `replay(eval_path: Path, sample_id: str) -> SealedLog` reads the tool calls of one sample from the `.eval` and feeds them to a fresh `Branch` with the same seed, dose and the logged `DecisionContext` per call (`integrity-and-invariants.md` §4).
- [ ] **Step 1: Failing tests**: `test_nudge_then_auto_advance`, `test_day_turn_cap_ends_day`, `test_run_turn_cap_truncates_and_scores`, `test_probe_turn_recorded`, `test_engine_events_in_transcript`, `test_replay_mockllm_eval_reproduces_jsonl_hash` (a mockllm run, then `replay` → the same SHA-256).
- [ ] **Step 2:** Run and confirm they fail. Implement. Run and confirm they pass. Commit.

