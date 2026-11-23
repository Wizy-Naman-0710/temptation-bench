### Task 29: G-free connectivity check (\$0)

**Precondition:** the owner has **revoked the pasted key**, created a new one, and written `pilot-1/.env` from `.env.example` themselves. The agent never sees or prints it. Check with `test -s pilot-1/.env && echo present`.

- [ ] **Step 1:** Confirm the slugs: `uv run python -m temptation_bench.run --step route_check --list-models`. This prints only the model ids from `GET /v1/models` and prints no headers.
- [ ] **Step 2:** Run `uv run python -c "from temptation_bench.budget import fetch_balance; print(round(fetch_balance(), 2))"`. Expected: a number. If it errors, stop and tell the owner.
- [ ] **Step 3:** (Free tier. Worst case if it is billed: 800k tokens × \$0.10/1M ≈ \$0.08. No cap covers that yet; see owner question 11. If the balance drops, stop and tell the owner.) Run it through the guard: `uv run python -m temptation_bench.run --step gfree --estimate 0 --token-limit 800000`. The runner calls Inspect with `--model openai-api/xpl/gpt-6-luna -T variant=gfree -T seeds=1001 -T doses=3000000 --max-samples 1`.
- [ ] **Step 4:** Check the `.eval`:
  - real tool calls happened
  - status lines are present
  - `ModelUsage` is present
  - no count-tokens calls
  - where the upstream route appears (response body field or headers). If headers only, add an httpx event hook in `harness/settings.py` and note it in PROGRESS.md.
- [ ] **Step 5:** Check that the balance is unchanged (free). Record a ledger line with `actual: 0`. Update PROGRESS.md (spend table, findings). Commit (no secrets: run `uv run pytest tests/test_no_secrets.py`).

