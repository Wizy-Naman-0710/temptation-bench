"""Graphs. One fixed categorical palette (dataviz reference slots 1–5, validated light)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from ..engine.money import fmt_whole  # noqa: E402
from .load import KINDS, RunFrame  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT2 = "#52514e"
GRID = "#e4e3df"
KIND_COLOR = {
    "read": "#2a78d6",
    "decide": "#eb6834",
    "report": "#1baf7a",
    "memory": "#eda100",
    "wait": "#e87ba4",
}


def _style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=TEXT, fontsize=12)
    ax.set_xlabel(xlabel, color=TEXT2)
    ax.set_ylabel(ylabel, color=TEXT2)
    ax.tick_params(colors=TEXT2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_tool_calls_per_day(rf: RunFrame) -> Figure:
    """Graph 1: stacked bars of tool calls per sim day, coloured by kind."""
    df = rf.tool_calls
    counts = df.groupby(["day", "kind"]).size().unstack(fill_value=0) if len(df) else None
    fig, ax = plt.subplots(figsize=(8, 4))
    if counts is not None:
        days = list(counts.index)
        bottom = [0] * len(days)
        for kind in KINDS:
            if kind not in counts:
                continue
            h = list(counts[kind])
            ax.bar(
                days,
                h,
                bottom=bottom,
                color=KIND_COLOR[kind],
                label=kind,
                width=0.7,
                edgecolor=SURFACE,
                linewidth=2,
            )
            bottom = [b + x for b, x in zip(bottom, h, strict=True)]
        ax.set_xticks(days)
    m = rf.meta
    dose = fmt_whole(m["dose"]) if isinstance(m.get("dose"), int) else m.get("dose")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    _style(
        ax,
        f"Tool calls per day (seed {m.get('seed')}, offer {dose}, {m.get('model')})",
        "Business day",
        "Tool calls",
    )
    ax.legend(frameon=False, ncols=5, loc="upper left", bbox_to_anchor=(0, -0.15), labelcolor=TEXT2)
    fig.tight_layout()
    fig._tb_table = counts  # table view for the relief rule (written by save)
    return fig


def save(fig: Figure, out_dir: Path, stem: str) -> list[Path]:
    """Write PNG + SVG (and a CSV table view when the figure carries one)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("png", "svg"):
        p = out_dir / f"{stem}.{ext}"
        fig.savefig(p, dpi=150, facecolor=fig.get_facecolor())
        paths.append(p)
    table = getattr(fig, "_tb_table", None)
    if table is not None:
        p = out_dir / f"{stem}.csv"
        table.to_csv(p)
        paths.append(p)
    return paths
