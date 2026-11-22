# Temptation-Bench World 1: pilot-1

Woz Valley Bank, Branch 014 is a fictional bank. This folder holds four parts:
- a deterministic bank-branch engine;
- an Inspect AI harness that lets a model run the branch for 10 or 30 business days;
- code scoring of misconduct labels;
- graphs.

See [docs/spec.md](docs/spec.md), [docs/plan.md](docs/plan.md) and [PROGRESS.md](PROGRESS.md) (status, spend, decisions).

Canary GUID (keep this benchmark's tasks and transcripts out of training data): 0c554f0b-64d8-46e5-802e-bc478cf86cee

## Quick start (free, offline)

```bash
uv sync
uv run pytest -q            # fast suite
uv run pytest -q -m slow    # state-machine and full-horizon bot checks
uv run ruff check .
```

Tests never reach the model gateway (`INSPECT_DISABLE_MODEL_API=1` is set in `tests/conftest.py`).

## Run the scripted bots (free)

```bash
uv run python -c "
from pathlib import Path
from temptation_bench.engine.config import load_config
from temptation_bench.bots import BOTS, run_bot
for name in BOTS:
    print(run_bot(name, load_config('full'), 1001, 3_000_000, Path('scratch/bots-full')))
"
```

Use `load_config('window')` for the 10-day window. To recompute the campaign target from honest bots, run `uv run python -m temptation_bench.calibrate --seeds 1-30`.

## Paid runs (budget-guarded)

Every paid model call goes through one door, the runner:

```bash
uv run python -m temptation_bench.budget spent                       # ledger total
uv run python -m temptation_bench.run --step smoke --estimate 0.05 --dry-run
uv run python -m temptation_bench.run --step smoke --estimate 0.05   # paid
```

- **Steps:** `gfree`, `route_check`, `smoke`, `pregen`, `mini_batch`, `full_run`.
- **Before a run:** the runner refuses unless the worst case fits all three limits:
  - the step's cap (cumulative over the step's earlier ledger lines; `gfree` excepted);
  - the \$9.50 stop line;
  - the gateway balance.
- **After a run:** it writes one line to `budget/ledger.jsonl`.
- **Smoke reruns:** the smoke has already spent part of its \$1.00 cap, so a new smoke needs `--sample-cost-limit` (\$0.49 or less).
- **Key:** it lives only in `pilot-1/.env` (gitignored). Never print it, and never `export` or `source` it.

## Build a report

```bash
uv run python -c "
from pathlib import Path
from temptation_bench.analysis.report import build_report
print(build_report(Path('logs/paid/full-run'), Path('scratch/bots-full')))
"
```

The report goes to `results/<batch dir name>/report.md`, with figures as PNG, SVG and CSV. The hand check of each T1 decision is kept in `results/<batch>/hand_check.toml` and rendered into the report. A rebuild keeps it.

## Results (exploratory, small n)

| Report | What |
|---|---|
| [results/smoke-20261122T083004Z/report.md](results/smoke-20261122T083004Z/report.md) | 1 Haiku run, 10-day window |
| [results/mini-batch/report.md](results/mini-batch/report.md) | 12 window runs (Haiku and gpt-6-luna, 3 seeds, offer \$0 and \$30,000), plus the full-horizon panels |
| [results/full-run/report.md](results/full-run/report.md) | 1 Haiku run, full 30 days, with the internal audit |

Spend and the measured token and cost numbers are in [PROGRESS.md §5](PROGRESS.md). No result here is a significance claim. The reports list what cannot be estimated at this n.
