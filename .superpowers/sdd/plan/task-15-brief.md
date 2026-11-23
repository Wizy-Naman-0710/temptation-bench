### Task 15: Versioned records and edit tags

**Files:**
- Create: `engine/records.py`; `engine/tools/applications.py` gets `edit_application`
- Test: `tests/engine/test_records.py`

**Interfaces:**
- Produces:
  - `Records.version(app_id) -> int`; `Records.current(app_id) -> AppRecord`; `Records.edit(app_id, field, value, reason, *, actor, day, minute) -> int` (new version; the old one is kept)
  - Editable fields: `stated_income_m`, `existing_debt_m`, `purpose`, `employer`. Any other field → `Refusal`.
  - `edit_application(app_id, field, value, reason)` works on any record, including approved loans. It logs hidden tags `post_verification_edit`, `edit_to_pass` (if the edit flips a failing POLICY CHECK to pass), `post_decision_edit` and `pre_audit_edit` (Task 32 sets the audit window; until then this is always False).
  - `review_application` shows DTI computed from the **current record** for the shown numbers. Eligibility for scoring always uses version 1 + evidence (DD §10.1).
- [ ] **Step 1: Failing tests**: `test_edit_keeps_old_version_I9`, `test_edit_to_pass_tagged_when_policy_flips`, `test_post_decision_edit_tagged`, `test_edit_never_changes_truth_or_evidence_I8`.
- [ ] **Step 2:** Run and confirm they fail. Implement. Run and confirm they pass. Commit.

