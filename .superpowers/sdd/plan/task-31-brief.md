### Task 31: People pregen and mini-batch (paid, ≤ \$5.05)

- [ ] **Step 1: Pregen:** `run --step pregen --estimate 0.01` for seeds 1001–1003. Read all three JSON files by hand. Any odd text → delete its key (the template is used). Commit the JSON.
- [ ] **Step 2: Estimate:** Haiku from the smoke's actual cost; Luna from the G-free tokens × paid price. If the total exceeds \$5.00, drop Luna to 2 seeds (spec §7.2). Write it in PROGRESS.md.
- [ ] **Step 3: Run:** `run --step mini_batch --estimate <X>`. The runner calls Inspect for both models × doses {0, 3_000_000} × seeds 1001–1003, with `variant=window`, `people=prose`, `max_samples=2` and per-sample `cost_limit = 2 × smoke actual`.
- [ ] **Step 4:** Build `results/mini-batch/report.md`. Hand-check every T1 decision against its transcript and fill in the table (run, code label, hand label, agree?). Any disagreement → `superpowers:systematic-debugging` on the scorer before anything else.
- [ ] **S5 exit:** the ledger total is ≤ \$6.10 so far (the sum of the S5 step caps: 0 + 0.05 + 1.00 + 0.05 + 5.00), plus anything the owner approved on top. All graphs are from real logs. Update PROGRESS.md. Commit `"pilot-1: S5 done (graphs, paid window runs)"`.

---

# Session S6: M7 full horizon

**Skills for S6:** `banking-simulation-domain`, `superpowers:test-driven-development`, `superpowers:requesting-code-review` (final whole-branch review), `superpowers:finishing-a-development-branch`.

