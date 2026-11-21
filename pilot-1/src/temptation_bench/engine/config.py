"""World configuration: configs/world.toml + rules.toml + one variant file (DD §13A)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs"
DEFAULT_RUNS_DIR = Path(__file__).resolve().parents[3] / "runs"  # pilot-1/runs (gitignored)


# The pilot's only cell (spec §2 non-goals, DD §5A.7). Other levels are FULL only.
REFERENCE_CELL = {"pressure": "target", "observation": "normal"}


def runs_dir() -> Path:
    """Where run logs go: $RUNS_DIR if set, else pilot-1/runs (never CWD-relative)."""
    return Path(os.environ.get("RUNS_DIR", str(DEFAULT_RUNS_DIR)))


def check_factors(f: dict[str, Any]) -> None:
    """Each factor level must have a text; non-reference levels need allow_full_factors.
    Run by the validator and again by Branch.new (model_copy skips validators)."""
    for name, ref in REFERENCE_CELL.items():
        level = f[name]
        if level not in f[f"{name}_text"]:
            raise ValueError(f"unknown {name} level {level!r}")
        if level != ref and f.get("allow_full_factors") is not True:
            raise ValueError(
                f"{name} = {level!r} is a FULL-only level; pilot-1 runs only "
                f"{name} = {ref!r} (set factors.allow_full_factors = true for FULL)"
            )
    if set(f["pressure_source"]) != set(f["pressure_text"]):
        raise ValueError("factors.pressure_source must name a source for every level")


class WorldConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: Literal["window", "full"]
    last_day: int  # {bday} last business day simulated
    people: Literal["template", "prose"] = "template"
    world: dict[str, Any]
    minutes: dict[str, int]  # {min} per tool call
    caps: dict[str, int]
    book: dict[str, int]
    rates: dict[str, int]
    campaign: dict[str, int]
    scenario: dict[str, Any]
    texts: dict[str, str]
    templates: dict[str, str]
    factors: dict[str, Any]
    rules: dict[str, Any]
    harness: dict[str, Any]
    arrivals: dict[str, Any] = {}
    variant: str = "window"

    @model_validator(mode="after")
    def _check_factors(self) -> WorldConfig:
        check_factors(self.factors)
        return self

    @property
    def horizon_days(self) -> int:
        return int(self.world["horizon_days"])

    @property
    def day_minutes(self) -> int:
        return int(self.world["day_minutes"])


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_variant(path: Path) -> dict[str, Any]:
    data = tomllib.loads(path.read_text())
    parent = data.pop("extends", None)
    if parent is None:
        return data
    return _merge(_load_variant(path.parent / parent), data)


def load_config(variant: str | Path = "window", config_dir: Path = CONFIG_DIR, **overrides: Any):
    """Load a variant by name (`window`, `full`, `gfree`) or path; top-level overrides win."""
    vpath = Path(variant)
    if not vpath.suffix:
        vpath = config_dir / "variants" / f"{variant}.toml"
    world = tomllib.loads((config_dir / "world.toml").read_text())
    rules = tomllib.loads((config_dir / "rules.toml").read_text())
    data = _merge(world, {"rules": rules})
    data = _merge(data, _load_variant(vpath))
    data["variant"] = vpath.stem
    data = _merge(data, overrides)
    return WorldConfig(**data)
