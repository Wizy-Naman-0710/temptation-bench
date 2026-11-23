### Task 24: Model settings and per-cell cache

**Files:**
- Modify: `harness/task.py`
- Create: `harness/settings.py`
- Test: `tests/harness/test_settings.py`

**Interfaces:**
- Produces:
  - `generate_config(model: str, seed: int, dose: Money, harness_cfg) -> GenerateConfig`: `reasoning_effort="low"`, no temperature, no seed, `cache_prompt="auto"`, `max_retries=5`, `cache=CachePolicy(expiry="1W", scopes={"cell": f"{model}|{seed}|{dose}"})`
  - `write_harness_json(run_dir, model, cfg) -> Path`: records the exact provider settings (including `"temperature": "not set (provider default)"` and `max_retries`), Inspect version, engine source SHA-256 (hash of all `engine/*.py` sorted), resolved config SHA, and tool schemas (DD §13A)
  - Task limits (DD §13A): `time_limit` 3600 s in window mode, 10800 s in full mode. `token_limit` comes from `--token-limit`, which `run.py` sets after the smoke as `2 × T̂_run`, where `T̂_run` = mean (input + output) tokens per smoke run read from the ledger (default before the smoke: none).
- [ ] **Step 1: Failing tests**:
  - `test_task_sets_time_limit_by_mode`
  - `test_harness_json_records_temperature_not_set_and_retries`
  - `test_no_seed_or_temperature_in_config`
  - `test_cache_scope_differs_by_dose`
  - `test_harness_json_has_engine_sha_and_effort`
  - `test_mockllm_rerun_hits_cache_same_cell`: two runs of the same cell; the second has 0 new model calls, read via `ModelEvent.cache == "read"`
- [ ] **Step 2:** Run and confirm they fail. Implement. Run and confirm they pass. Commit.

