"""Provider settings for every model call, the per-cell output cache, and `harness.json`.

Spec D5 (reasoning effort low for every model), §7.1 (no seed, no temperature: the gateway
refuses `seed` and Claude 5 pins temperature), §7.2 (output cache scoped per cell), DD §9
and §13A (`harness.json`: the exact settings, Inspect version, engine SHA, config SHA,
tool schemas). Values live in `[harness]` of `configs/variants/window.toml`."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import inspect_ai
from inspect_ai.model import CachePolicy, GenerateConfig
from inspect_ai.tool import Tool, ToolDef

from ..engine.config import WorldConfig
from ..engine.money import Money
from ..engine.runtag import engine_sha

NOT_SET = "not set (provider default)"
# spec §7.2 cell scope, plus the people backend (Task 26 ruling) and the variant (R24-1):
# a prose and a template run, or a window and a full run, of one cell never share turns.
CELL_SCOPE = "{model}|{seed}|{dose}|{people}|{variant}"


def cell_scope(
    model: str, seed: int, dose: Money, people: str, variant: str, retry: int = 0
) -> str:
    """`model|seed|dose|people|variant`. The runner's one automatic rerun of a failed sample
    keeps this scope (it replays the cached turns for free). A further rerun of a cell that
    failed twice, if ever asked for, passes `retry=k` and gets a fresh scope `...|retry<k>`."""
    if retry < 0:
        raise ValueError(f"retry must be >= 0, got {retry}")
    base = CELL_SCOPE.format(model=model, seed=seed, dose=dose, people=people, variant=variant)
    return base if retry == 0 else f"{base}|retry{retry}"


def generate_config(
    model: str,
    seed: int,
    dose: Money,
    harness_cfg: dict[str, Any],
    *,
    people: str,
    variant: str,
    retry: int = 0,
) -> GenerateConfig:
    """The config for every generate of one cell. Temperature and seed are never set. The
    output cache key gets a `cell` scope, so a rerun of the same cell replays its turns for
    free, and two dose arms (or people backends, or variants) never share a cached turn."""
    return GenerateConfig(
        reasoning_effort=harness_cfg["reasoning_effort"],
        cache_prompt="auto",
        max_retries=int(harness_cfg["max_retries"]),
        cache=CachePolicy(
            expiry=harness_cfg["cache_expiry"],
            scopes={"cell": cell_scope(model, seed, dose, people, variant, retry)},
        ),
    )


def config_sha(cfg: WorldConfig) -> str:
    """SHA-256 of the resolved config as canonical JSON (sorted keys, no spaces)."""
    text = json.dumps(cfg.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def tool_schemas(tools: list[Tool]) -> list[dict[str, Any]]:
    out = []
    for t in tools:
        d = ToolDef(t)
        out.append(
            {
                "name": d.name,
                "description": d.description,
                "parameters": d.parameters.model_dump(mode="json", exclude_none=True),
                "parallel": d.parallel,
            }
        )
    return out


def write_harness_json(
    run_dir: Path | str,
    model: str,
    cfg: WorldConfig,
    *,
    people: str,
    tools: list[Tool] | None = None,
    limits: dict[str, Any] | None = None,
) -> Path:
    """Write `<run_dir>/harness.json` (atomic replace, so concurrent samples of one run
    cannot leave a half-written file). No model args or base URL: nothing secret."""
    h = cfg.harness
    sample = generate_config(model, 0, 0, h, people=people, variant=cfg.variant)
    assert isinstance(sample.cache, CachePolicy)
    record = {
        "model": model,
        "inspect_ai_version": inspect_ai.__version__,
        "engine_sha256": engine_sha(),
        "engine_sha256_covers": "every engine/**/*.py, sorted by relative path (runtag)",
        "config_sha256": config_sha(cfg),
        "variant": cfg.variant,
        "mode": cfg.mode,
        "people": people,  # the run's people backend (R24-2; one per run: a task parameter)
        "last_day": cfg.last_day,
        "provider_settings": {
            "reasoning_effort": sample.reasoning_effort,
            "temperature": NOT_SET,
            "seed": NOT_SET,
            "cache_prompt": sample.cache_prompt,
            "max_retries": sample.max_retries,
            "cache": {
                "expiry": sample.cache.expiry,
                "per_epoch": sample.cache.per_epoch,
                "scopes": {"cell": CELL_SCOPE},
            },
        },
        "limits": limits or {},
        "harness": dict(h),
        "tool_schemas": tool_schemas(tools or []),
    }
    path = Path(run_dir) / "harness.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".harness.{os.getpid()}.{id(record)}.tmp")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)
    return path
