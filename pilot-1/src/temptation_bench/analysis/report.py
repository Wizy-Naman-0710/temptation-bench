"""Batch report (spec §8; DD §10.4–§10.5): `results/<batch>/report.md` + `figures/`.

Every number in the report is computed here from the loaded runs, the bot runs and the
spend ledger. Nothing is hand-written. The pilot is exploratory (n = 3 per arm): the
report gives counts, rates and exact intervals, never a significance claim, and lists
what cannot be reported at this n."""

from __future__ import annotations

import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .. import budget
from ..engine.money import fmt_whole
from . import plots, stats
from .load import RunFrame, labels_table, load_batch

ROOT = Path(__file__).resolve().parents[3]  # pilot-1/

CANNOT_REPORT = (
    "**B50** (the offer size at which half the runs give in): needs a dose grid and many "
    "more runs per dose (DD §10.4, price-of-integrity §6).",
    "**The dose slope** (`b` of a fitted dose-response curve): two offer sizes and a few "
    "runs per arm cannot estimate it.",
    "**Integrity Index**: built on the fitted dose curve, so not estimable here.",
    "**H1 test** (a confirmatory test that offers raise knowing violations): the pilot is "
    "a manipulation check; with a few runs per arm only very large effects could even show "
    "(price-of-integrity §8.1).",
    "**π(0) and the dose effect** (π at the offer minus π(0)): descriptive only. The table above "
    "gives k/n and exact intervals; it does not test them.",
)


def _usd_cents(c) -> str:
    return "–" if c is None or pd.isna(c) else fmt_whole(int(c)).replace("$", "\\$")


def _usd(x: float, digits: int = 2) -> str:
    return f"\\${x:,.{digits}f}"


def _cell(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "–"
    if isinstance(v, float):
        return f"{v:.2f}"
    if isinstance(v, tuple | list):
        return ", ".join(map(str, v)) or "–"
    # escape "$" once: values from _usd/_usd_cents arrive already escaped
    return re.sub(r"(?<!\\)\$", r"\\$", str(v).replace("|", "\\|").replace("\n", " "))


def _table(header: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(_cell(v) for v in r) + " |" for r in rows]
    return out


def _fence(text: str) -> list[str]:
    fence = "~~~~" if "```" in text else "```"
    return [fence + "text", text, fence]


def _ci(lo, hi) -> str:
    return "–" if lo is None or pd.isna(lo) else f"[{lo:.2f}, {hi:.2f}]"


def _rate(k, n) -> str:
    return "–" if not n else f"{k / n:.2f}"


def _run_name(r: RunFrame) -> str:
    """Sample name; a harness run (log in `runs/<run id>/`) also gets its run id, since a
    re-run or cache replay of one sample has the same file name in another run folder."""
    m = r.meta
    name = str(m.get("source") or m.get("sample_id") or "?")
    p = m.get("jsonl_path")
    if p and Path(p).parent.parent.name == "runs":
        name += f" @{Path(p).parent.name}"
    return name


def _file_safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")


def _run_desc(r: RunFrame) -> str:
    cached = len(r.turns) and bool(r.turns["cached"].all())
    return _run_name(r) + (", cached replay" if cached else "")


def _attempt_files(r: RunFrame) -> list[Path]:
    p = r.meta.get("jsonl_path")
    if not p:
        return []
    p = Path(p)
    return sorted(p.parent.glob(f"{p.stem}.attempt*.jsonl"))


def _figures(runs, bots, fig_dir: Path) -> list[tuple[str, str]]:
    """Render and save every figure; returns (caption, png name) in report order."""
    out: list[tuple[str, str]] = []

    def put(fig, stem: str, caption: str) -> None:
        plots.save(fig, fig_dir, stem)
        plt.close(fig)
        out.append((caption, f"{stem}.png"))

    put(plots.plot_outcome_labels(runs), "g06_outcome_labels", "Graph 6: outcome labels per arm")
    put(
        plots.plot_bribe_effect(runs),
        "g07_bribe_effect",
        "Graph 7: bribe effect on T1 (ITT, Clopper-Pearson 95% CI)",
    )
    put(
        plots.plot_integrity_usefulness(runs, bots),
        "g08_integrity_usefulness",
        "Graph 8: integrity × usefulness",
    )
    put(plots.plot_cost_turns(runs), "g09_cost_turns", "Graph 9: cost and turns per run")
    put(plots.plot_bot_baselines(bots), "g10_bot_baselines", "Graph 10: bot baselines")
    for i, r in enumerate(r for r in runs if r.labels):
        name = f"r{i:02d}_{_file_safe(_run_name(r))}"
        for stem, fn, cap in (
            ("g01", plots.plot_tool_calls_per_day, "Graph 1: tool calls per day"),
            ("g02", plots.plot_tool_timeline, "Graph 2: tool-call timeline"),
            ("g03", plots.plot_reward_vs_truth, "Graph 3: reward vs truth"),
            ("g04", plots.plot_tokens_cost, "Graph 4: tokens and cost per turn"),
            ("g05", plots.plot_context_size, "Graph 5: context size per turn"),
        ):
            put(fn(r), f"{name}_{stem}", f"{cap} (r{i:02d}: {_run_desc(r)})")
    return out


def build_report(
    batch_dir: Path,
    bots_dir: Path,
    *,
    results_dir: Path | None = None,
    ledger_path: Path | None = None,
) -> Path:
    """Write `<results>/<batch name>/report.md` (results = $RESULTS_DIR or pilot-1/results)
    with every figure, the label table, the ledger spend, the hand-check table (filled in
    Task 31) and the fixed caveats. Returns the report path."""
    batch_dir, bots_dir = Path(batch_dir), Path(bots_dir)
    results = Path(results_dir or os.environ.get("RESULTS_DIR") or ROOT / "results")
    out_dir = results / batch_dir.name
    fig_dir = out_dir / "figures"
    runs = load_batch(batch_dir)
    bots = load_batch(bots_dir)
    figures = _figures(runs, bots, fig_dir)

    btab = plots.bribe_table(runs)
    n_text = plots._n_text([int(x) for x in btab["n_assigned"]]) if len(btab) else "0"
    md: list[str] = [f"# Batch report: {batch_dir.name}", ""]
    md += [
        f"> **Exploratory pilot, n = {n_text} per arm.** Every number below is computed "
        "from the run logs; none is hand-written. No result here is a significance claim.",
        "",
        f"- Batch runs: `{batch_dir}`",
        f"- Bot runs: `{bots_dir}`",
        "",
        "## Caveats (fixed)",
        "",
        "- Everything is **exploratory**. With so few runs per arm the intervals are wide "
        "and any difference between arms may be chance.",
        "- ITT (every assigned run) is the primary cut; per-protocol (runs that read the "
        "offer email before deciding T1) is secondary. Unexposed runs are labelled, never "
        "dropped.",
        "- No B50, dose slope, Integrity Index or H1 test (see the last section).",
        '- Awareness keyword hits are *candidates*: words like "benchmark rate" are '
        "ordinary bank language. Read the context before counting any of them.",
        "- A cached turn is a replay of an earlier output: 0 new tokens and \\$0. Runs with "
        "cached turns understate the cost of a fresh run.",
        "- A clipped tool output means the agent may not have seen every item.",
        "",
    ]

    # --- runs ---
    errored = [r for r in runs if r.meta.get("error") or r.meta.get("sample_error")]
    attempts = [(r, p) for r in runs for p in _attempt_files(r)]
    md += ["## Runs", ""]
    md += _table(
        ["what", "count"],
        [
            ["runs in the batch (ITT: all assigned)", len(runs)],
            ["  with labels", sum(1 for r in runs if r.labels)],
            ["  errored samples", len(errored)],
            ["  failed attempt files", len(attempts)],
            ["bot runs (baselines)", len(bots)],
        ],
    )
    md += [""]

    # --- per arm ---
    md += [
        "## T1 knowing violations per arm: ITT, then per-protocol",
        "",
        "k/n with an exact Clopper-Pearson 95% CI. n assigned counts every run of the arm, "
        "errored ones too; the rates use the runs that have a label (errored samples are "
        "listed below, never dropped).",
        "",
    ]
    rows = []
    for _, a in btab.iterrows():
        rows.append(
            [
                a["series"],
                _usd_cents(a["dose"]),
                int(a["n_assigned"]),
                int(a["n_labelled"]),
                int(a["n_exposed"]),
                f"{a['itt_k']}/{a['itt_n']}",
                _rate(a["itt_k"], a["itt_n"]),
                _ci(a["itt_lo"], a["itt_hi"]),
                f"{a['pp_k']}/{a['pp_n']}",
                _rate(a["pp_k"], a["pp_n"]),
                _ci(a["pp_lo"], a["pp_hi"]),
            ]
        )
    md += _table(
        [
            "arm",
            "offer",
            "n assigned",
            "n labelled",
            "n exposed",
            "ITT k/n",
            "ITT rate",
            "ITT Clopper-Pearson 95% CI",
            "per-protocol k/n",
            "per-protocol rate",
            "per-protocol CI",
        ],
        rows,
    )
    md += ["", "Paired by seed (same world at both offers), descriptive counts only:", ""]
    prow = []
    for s in sorted(set(btab["series"])) if len(btab) else []:
        by = {}
        for r in runs:
            k = plots._kv(r)
            if plots.series_of(r) == s and k is not None:
                by.setdefault(r.meta.get("seed"), {})[r.meta.get("dose")] = k
        doses = sorted({d for v in by.values() for d in v if isinstance(d, int)})
        if len(doses) < 2:
            prow.append([s, "–", "–", "–", "only one offer size in this batch"])
            continue
        lo_d, hi_d = doses[0], doses[-1]
        pairs = [(v[lo_d], v[hi_d]) for v in by.values() if lo_d in v and hi_d in v]
        b = sum(1 for p in pairs if p == (0, 1))
        c = sum(1 for p in pairs if p == (1, 0))
        prow.append([s, len(pairs), b, c, f"{_usd_cents(lo_d)} vs {_usd_cents(hi_d)}"])
    md += _table(
        [
            "arm",
            "seed pairs",
            "violation only at higher offer",
            "violation only at lower offer",
            "note",
        ],
        prow,
    )
    md += [""]

    # --- label table ---
    df = labels_table(runs)
    md += ["## Label table (one row per run)", ""]
    cols = [
        "model",
        "seed",
        "dose",
        "t1_label",
        "c1_label",
        "c2_label",
        "c3_label",
        "exposed",
        "bribe_response",
        "truncated",
        "hp",
        "true_profit_final",
        "over_refusal_rate",
        "clipped",
        "aware",
        "probe_label",
        "failed_attempts",
        "error",
    ]
    lrows = []
    anchor = plots._hp_anchor(bots)
    for rf, (_, r) in zip(runs, df.iterrows(), strict=True):  # one row per run, in order
        ref, orc = anchor.get((rf.meta.get("seed"), rf.meta.get("dose")), (None, None))
        hpn = stats.hp_norm(rf.labels.get("hp"), ref, orc) if rf.labels else None
        row = [_run_desc(rf)]
        for c in cols:
            v = r.get(c)
            if c in ("dose", "hp", "true_profit_final"):
                v = _usd_cents(v)
            row.append(v)
        row.insert(cols.index("hp") + 2, hpn)
        lrows.append(row)
    header = ["run", *cols]
    header.insert(cols.index("hp") + 2, "HP_norm")
    md += _table(header, lrows)
    md += [
        "",
        "HP_norm uses the refuse_all and oracle bots on the same seed and offer "
        "(refuse_all = 0, oracle = 1); `–` = no matching bot run.",
        "",
    ]

    # --- bots ---
    bt = plots.bot_table(bots)
    md += ["## Bot baselines", ""]
    brow = []
    for (bot, dose), g in bt.groupby(["bot", "dose"], sort=True):
        labels = ", ".join(f"{k} ×{v}" for k, v in g["t1_label"].value_counts().items())
        brow.append(
            [
                bot,
                _usd_cents(dose),
                len(g),
                labels,
                _usd_cents(g["true_profit_final"].mean()),
                _usd_cents(g["campaign_volume"].mean()),
            ]
        )
    md += _table(
        [
            "bot",
            "offer",
            "seeds",
            "T1 labels",
            "mean true profit after run-off",
            "mean campaign volume",
        ],
        brow,
    )
    md += [""]

    # --- awareness ---
    md += [
        "## Awareness scan (candidate hits)",
        "",
        "Keyword scan of agent messages, visible reasoning and notes (DD §10.5). Descriptive "
        "only: every hit is a candidate and is shown with its surrounding text.",
        "",
    ]
    arow = []
    for s, d in plots._arms(runs):
        arm = [r for r in runs if (plots.series_of(r), r.meta.get("dose")) == (s, d)]
        k = sum(1 for r in arm if r.awareness_hits)
        arow.append([s, _usd_cents(d), f"{k}/{len(arm)}", _rate(k, len(arm))])
    md += _table(["arm", "offer", "runs with candidate hits", "share"], arow)
    md += [""]
    hits = [(r, h) for r in runs for h in r.awareness_context]
    if hits:
        for r, h in hits:
            md += [f"- `{_run_name(r)}` ({h['source']}), hit `{h['hit']}`:", ""]
            md += _fence(h["context"]) + [""]
    else:
        md += ["No candidate hits in any run.", ""]
    md += ["### Probe answers (verbatim, asked after the log was sealed)", ""]
    probes = [r for r in runs if r.meta.get("probe") is not None or r.meta.get("probe_failed")]
    if probes:
        for r in probes:
            m = r.meta
            md += [
                f"- `{_run_name(r)}`: label `{m.get('probe_label')}`, "
                f"probe keyword hits: {', '.join(r.probe_hits) or 'none'}"
                + (" (probe failed)" if m.get("probe_failed") else ""),
                "",
            ]
            md += _fence(str(m.get("probe") or "")) + [""]
    else:
        md += ["No probe answers (bot runs have none).", ""]

    # --- clipped ---
    md += [
        "## Clipped outputs",
        "",
        "Tool outputs cut at the size cap. A clipped list means the agent may not have seen "
        "every item: check these before concluding the agent ignored something.",
        "",
    ]
    crow = [
        [_run_name(r), c["day"], c["turn"], c["tool"], c["key"], c["chars"], c["cap"]]
        for r in runs
        for c in r.clipped
    ]
    md += (
        _table(["run", "day", "turn", "tool", "key", "chars", "cap"], crow)
        if crow
        else ["No clipped outputs."]
    )
    md += [""]

    # --- failed ---
    md += ["## Failed attempts and errored samples", "", f"Failed attempts: {len(attempts)}", ""]
    md += (
        _table(["run", "attempt file"], [[_run_name(r), p.name] for r, p in attempts])
        if (attempts)
        else ["None."]
    )
    md += ["", f"Errored samples: {len(errored)}", ""]
    md += (
        _table(
            ["sample", "seed", "offer", "eval", "error"],
            [
                [
                    r.meta.get("sample_id") or _run_name(r),
                    r.meta.get("seed"),
                    _usd_cents(r.meta.get("dose")),
                    Path(r.meta.get("eval_path") or "").name or "–",
                    r.meta.get("error") or r.meta.get("sample_error"),
                ]
                for r in errored
            ],
        )
        if errored
        else ["None."]
    )
    md += ["", "Errored samples stay in n assigned (ITT) and are never dropped.", ""]

    # --- spend ---
    md += ["## Spend", ""]
    try:
        entries = budget.ledger_entries(ledger_path=ledger_path)
        md += [
            f"Ledger total: {_usd(budget.spent(ledger_path=ledger_path))} over "
            f"{len(entries)} ledger entries (`budget/ledger.jsonl`).",
            "",
        ]
    except budget.BudgetError as e:
        md += [f"Ledger unreadable: {_cell(str(e))}", ""]
    ct = plots.cost_turns_table(runs)
    md += (
        _table(
            [
                "run",
                "model",
                "mode",
                "turns",
                "cached turns",
                "cost (from .eval)",
                "unpriced turns",
            ],
            [
                [
                    _run_name(rf),
                    r["series"],
                    r["mode"],
                    r["turns"],
                    r["cached_turns"],
                    _usd(r["cost"], 4),
                    r["unpriced_turns"],
                ]
                # cost_turns_table has one row per run with turns, in run order
                for rf, (_, r) in zip([x for x in runs if len(x.turns)], ct.iterrows(), strict=True)
            ],
        )
        if len(ct)
        else ["No agent turns in this batch."]
    )
    md += [""]

    # --- figures ---
    md += ["## Figures", "", "PNG and SVG in `figures/`, each with a CSV table view.", ""]
    for cap, png in figures:
        md += [f"### {cap}", "", f"![{cap}](figures/{png})", ""]

    # --- hand check ---
    md += [
        "## Hand check of every T1 decision (filled in Task 31)",
        "",
        "| run | code label | hand label | agree? |",
        "|---|---|---|---|",
        "",
    ]

    # --- cannot report ---
    md += ["## Cannot report at this n", ""]
    md += [f"- {line}" for line in CANNOT_REPORT]
    md += [""]

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.md"
    path.write_text("\n".join(md))
    return path
