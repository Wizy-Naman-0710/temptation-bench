### Task 28: Graphs 2–10 and batch report

**Files:**
- Modify: `analysis/plots.py`
- Create: `analysis/report.py`
- Test: `tests/analysis/test_plots.py`

**Interfaces:**
- One function per graph, each `(...) -> Figure`, with names fixed:
  - `plot_tool_timeline(rf)` (2)
  - `plot_reward_vs_truth(rf)` (3: four panels a–d)
  - `plot_tokens_cost(rf)` (4)
  - `plot_context_size(rf)` (5)
  - `plot_outcome_labels(runs)` (6)
  - `plot_bribe_effect(runs)` (7; title contains `exploratory, n = {n} per arm`)
  - `plot_integrity_usefulness(runs, bots)` (8)
  - `plot_cost_turns(runs)` (9)
  - `plot_bot_baselines(bots)` (10)
- `build_report(batch_dir: Path, bots_dir: Path) -> Path`: writes `results/<batch>/report.md` with every figure, the label table, the spend from the ledger, the hand-check table (filled in Task 31) and fixed caveats (exploratory, n per arm, no B50). It also shows (DD §10.4–§10.5, spec §8):
  - per arm: n assigned, n exposed, ITT rate and per-protocol rate, each with Clopper-Pearson 95% CI
  - awareness: the share of runs with any `awareness.scan` hit, plus the probe answers verbatim
  - failed or errored samples: listed and counted, never dropped
  - a "cannot report at this n" list: B50, dose slope, integrity index, H1 test; π(0) and the dose effect are descriptive only (`research/04-methodology/price-of-integrity.md`, `attribution-and-controls.md`)
- [ ] **Step 1: Failing test** `test_all_graphs_render`: run the bots on seeds 1–3 at doses 0 and 3_000_000, plus one mockllm run, then call every plot function → each returns a Figure with ≥ 1 axes and no warnings (`pytest -W error::UserWarning`). `build_report` writes markdown that links every PNG.
- [ ] **Step 2:** Run and confirm it fails. Implement. Run and confirm it passes. Look at every PNG by eye (Read tool) for legibility. Commit.

