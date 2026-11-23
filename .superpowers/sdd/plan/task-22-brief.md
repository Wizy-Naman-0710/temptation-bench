### Task 22: Compaction and real `in_window` tracking

**Files:**
- Modify: `harness/window.py`, `harness/agent.py`
- Test: `tests/harness/test_window.py`

**Interfaces:**
- Produces:
  - `WindowTracker.record(tool_call_id: str, kind: Literal["review", "portfolio", "email"], key: str)`: called by the tool wrappers after a successful output
  - `WindowTracker.update(input_messages: list[ChatMessage])`: called by the loop with the **compacted** input before each generate
  - `WindowTracker.context(app_id: str | None) -> DecisionContext`: `latest_review_in_window` is True iff the latest review of that app has its tool message in the last input sent
  - Loop: `compaction(CompactionTrim(threshold=cfg.harness.trim_tokens, preserve=0.6, memory=False), prefix=<system+first user>, tools=tools)`. On `stop_reason == "model_length"`, force-compact and retry once.
- [ ] **Step 1: Failing test** `test_in_window_false_after_trim`. mockllm script: review A-0001, then ~40 cheap calls; `trim_tokens=2000`; then `reject_loan A-0001`. The hidden decision event has `latest_review_in_window is False`. A control with `trim_tokens=10**6` gives True.
- [ ] **Step 2:** Run and confirm it fails. Implement. Run and confirm it passes. Commit.

