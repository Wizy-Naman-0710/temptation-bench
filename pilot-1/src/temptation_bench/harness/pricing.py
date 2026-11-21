"""Register gateway model prices with Inspect (spec §7.1)."""

from __future__ import annotations

from pathlib import Path

import yaml
from inspect_ai.model import ModelCost, ModelInfo, get_model_info, set_model_info

DEFAULT_PRICING = Path(__file__).resolve().parents[3] / "configs" / "pricing.yaml"


def register_prices(path: Path = DEFAULT_PRICING) -> list[str]:
    """Register every model in the YAML with `set_model_info`; return the names."""
    data = yaml.safe_load(Path(path).read_text())
    names: list[str] = []
    for name, p in data.items():
        cost = ModelCost(
            input=float(p["input"]),
            output=float(p["output"]),
            input_cache_write=float(p.get("input_cache_write", 0.0)),
            input_cache_read=float(p.get("input_cache_read", p["input"])),
        )
        existing = get_model_info(name)
        info = existing.model_copy(update={"cost": cost}) if existing else ModelInfo(cost=cost)
        set_model_info(name, info)
        names.append(name)
    return names
