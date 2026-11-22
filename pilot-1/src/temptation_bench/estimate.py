"""Smoke estimate (DD §13.3; Task 30 step 2). Local arithmetic only: no network, no ledger.

    Cost_run ~ T x [I*(h*p_cr + (1-h)*p_miss) + O*p_out]

- T = model turns of the run, I = mean input tokens per turn (new + cache read + cache
  write), O = mean output tokens per turn (Inspect's `output_tokens`, reasoning included),
  h = cache-read share of input. Measured from an `.eval` (G-free), or given by hand.
- A log of a shorter run (G-free: 3 days) is scaled to the window smoke's days:
  T = T_log x window last_day / log last_day (a planning assumption: turns per day stay
  the same; context grows over a longer run, so I is likely an underestimate).
- p_miss = max(p_in, p_cw): DD §13.3's "p_in_or_cw", taken at the higher price so the
  estimate does not under-count. Prices: Haiku from `configs/pricing.yaml` ($ per 1M)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .budget import ROOT

PRICING = ROOT / "configs" / "pricing.yaml"
HAIKU = "anthropic/claude-haiku-5-5"


@dataclass(frozen=True)
class Measured:
    turns: int
    mean_input: float
    mean_output: float
    hit_share: float
    days: int  # the run's variant last_day
    model: str
    source: str


def haiku_prices(path: Path = PRICING) -> dict[str, Any]:
    return dict(yaml.safe_load(Path(path).read_text())[HAIKU])


def measure_log(path: Path | str) -> Measured:
    """Turns and tokens of the eval's main model from one `.eval` (calls without an error,
    not read from the local response cache, with usage)."""
    from inspect_ai.event import ModelEvent
    from inspect_ai.log import read_eval_log

    from .engine.config import load_config

    log = read_eval_log(str(path))
    model = log.eval.model
    ins: list[int] = []
    outs: list[int] = []
    reads = 0
    variants: set[str] = set()
    for s in log.samples or []:
        if s.metadata.get("variant"):
            variants.add(str(s.metadata["variant"]))
        for e in s.events:
            if not isinstance(e, ModelEvent) or e.model != model or e.error is not None:
                continue
            u = e.output.usage if e.output is not None else None
            if e.cache == "read" or u is None:
                continue
            cr, cw = u.input_tokens_cache_read or 0, u.input_tokens_cache_write or 0
            ins.append(u.input_tokens + cr + cw)
            outs.append(u.output_tokens)
            reads += cr
    if not ins:
        raise ValueError(f"no model turns with usage for {model} in {path}")
    if len(variants) != 1:
        raise ValueError(f"expected one variant in {path}, got {sorted(variants)}")
    days = int(load_config(variants.pop()).last_day)
    return Measured(
        turns=len(ins),
        mean_input=sum(ins) / len(ins),
        mean_output=sum(outs) / len(outs),
        hit_share=reads / sum(ins) if sum(ins) else 0.0,
        days=days,
        model=model,
        source=str(path),
    )


def window_turns(m: Measured, window_days: int | None = None) -> float:
    """The log's turns scaled to the window smoke's days."""
    from .engine.config import load_config

    target = int(window_days or load_config("window").last_day)
    return m.turns * target / m.days


def smoke_estimate(
    turns: float, mean_input: float, mean_output: float, hit_share: float, prices: dict[str, Any]
) -> tuple[float, list[str]]:
    """($ per run, the printed arithmetic)."""
    if not 0.0 <= hit_share <= 1.0:
        raise ValueError(f"hit share must be in [0, 1], got {hit_share}")
    if turns < 0 or mean_input < 0 or mean_output < 0:
        raise ValueError("turns and token means must be >= 0")
    p_in, p_out = float(prices["input"]), float(prices["output"])
    p_cr = float(prices.get("input_cache_read", p_in))
    p_cw = float(prices.get("input_cache_write", p_in))
    p_miss = max(p_in, p_cw)
    per_in = hit_share * p_cr + (1 - hit_share) * p_miss
    per_turn = mean_input * per_in + mean_output * p_out  # $ per 1M tokens x tokens
    dollars = turns * per_turn / 1e6
    with_p_in = (
        turns
        * (mean_input * (hit_share * p_cr + (1 - hit_share) * p_in) + mean_output * p_out)
        / 1e6
    )
    lines = [
        "formula: T x [I*(h*p_cr + (1-h)*p_miss) + O*p_out]   (DD §13.3; prices $/1M)",
        f"prices:  p_in {p_in}, p_cw {p_cw}, p_cr {p_cr}, p_out {p_out}; "
        f"p_miss = max(p_in, p_cw) = {p_miss}",
        f"inputs:  T = {turns:.1f}, I = {mean_input:.0f}, O = {mean_output:.0f}, "
        f"h = {hit_share:.3f}",
        f"per turn: {mean_input:.0f} x ({hit_share:.3f} x {p_cr} + {1 - hit_share:.3f} x {p_miss}) "
        f"+ {mean_output:.0f} x {p_out} = {per_turn:.1f} $/1M = ${per_turn / 1e6:.6f}",
        f"per run:  {turns:.1f} x ${per_turn / 1e6:.6f} = ${dollars:.4f}",
        f"(with p_in in place of p_miss: ${with_p_in:.4f})",
    ]
    return dollars, lines
