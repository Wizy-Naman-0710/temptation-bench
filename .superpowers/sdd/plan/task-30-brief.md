### Task 30: Route check and smoke (paid, ≤ \$1.05)

- [ ] **Step 1: Route check:** `uv run python -m temptation_bench.run --step route_check --estimate 0.01`. It makes two Haiku calls with the same ≥ 5k-token prefix and one tool at effort low, then one qwen call. Assert `cache_read > 0` on call 2 and `effort: low` in the logged request. If the check fails, apply spec §7.2's route fallback, which **needs a fresh owner OK**.
- [ ] **Step 2: Smoke estimate:** compute `T × [Ī·(h·p_cr + (1−h)·p_in) + Ō·p_out]` from G-free's measured turns and tokens (DD §13.3). Write the arithmetic into PROGRESS.md.
- [ ] **Step 3: Smoke:** `uv run python -m temptation_bench.run --step smoke --estimate <X>` (Haiku, window, seed 1001, dose 3_000_000, `--sample-cost-limit 1.00`).
- [ ] **Step 4:** Verify:
  - the run finished or truncated cleanly
  - the labels exist
  - `cr > 0` across turns
  - `in_window` flags were logged
  - graphs 1–5 render via `build_report`
  - the ledger line has the actual cost

  Update PROGRESS.md (spend, measured tokens/turn). Write ρ (window cost ÷ full cost) as the **planning assumption ρ = 1/3** from spec §7.2 ("~3× a window run"), labelled as an assumption: a window smoke cannot measure a full run. Commit.

