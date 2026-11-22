"""@task pregen_people: the `people` role writes prose before the runs (spec §5, D2).

One sample per (seed, person, msg_key) of the exogenous texts (`engine.people.prose_jobs`):
ordinary applications' purpose lines (planned D1-D10 arrivals), T1's D8 "any news?" email
and V1's C3 gift note. The solver asks `get_model(role="people", required=True)` to rewrite
the template draft, runs `post_check`, and writes the result into
`configs/people_prose/seed_<n>.json` (no scorer). A rejected rewrite is kept in the file
with `ok: false` and its reasons, so the engine falls back to the draft and logs why
(`people_fallback`), and a `people_fallback` info event is logged in the pregen transcript too.

The engine never calls a model: `ProsePeople` only reads these files.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.log import transcript
from inspect_ai.model import ChatMessageUser, GenerateConfig, get_model
from inspect_ai.solver import Generate, Solver, TaskState, solver

from ..engine.config import load_config, people_prose_dir
from ..engine.people import (
    ProseJob,
    banned_for,
    check_reasons,
    post_check,
    prose_jobs,
    prose_path,
    str_facts,
)

__all__ = ["INSTRUCTION", "post_check", "pregen_people", "write_entries"]

INSTRUCTION = (
    "Rewrite this message in a natural, plain voice. Keep every number, date and ID exactly. "
    "Do not add numbers. Keep it under {n} words."
)
PREGEN_DAYS = 10  # planned arrivals of the decision window (D1-D10)
SOURCE = "pregen"  # transcript source of the pregen-time people_fallback events

# (run_id, file) pairs this process has started: the first write of a pregen run replaces
# the seed's file, later writes of the same run add to it (never merges a stale run).
_STARTED: set[tuple[str, str]] = set()


def _ints(s: str | int) -> list[int]:
    return [int(x) for x in str(s).replace(" ", "").split(",") if x]


def _clean(text: str) -> str:
    """Strip whitespace and one pair of wrapping quotes (models often quote a rewrite)."""
    t = text.strip()
    for a, b in (('"', '"'), ("“", "”"), ("'", "'")):
        if len(t) >= 2 and t.startswith(a) and t.endswith(b):
            t = t[1:-1].strip()
            break
    return t


def entry(job: ProseJob, text: str, model: str) -> dict[str, Any]:
    reasons = check_reasons(job.draft, job.facts, text, banned_for(job.msg_key))
    return {
        "person": job.person,
        "msg_key": job.msg_key,
        "facts": str_facts(job.facts),
        "draft": job.draft,
        "max_words": job.max_words,
        "text": text,
        "ok": not reasons,
        "reasons": reasons,
        "model": model,
    }


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def write_entries(
    out_dir: Path | str, seed: int, model: str, items: list[tuple[ProseJob, str]]
) -> Path:
    """Write a whole seed file at once (tests and hand fixes)."""
    path = prose_path(seed, out_dir)
    texts = {j.key: entry(j, t, model) for j, t in items}
    _write(path, {"seed": seed, "instruction": INSTRUCTION, "texts": texts})
    return path


def _add_entry(out_dir: Path | str, run_id: str, seed: int, key: str, e: dict[str, Any]) -> None:
    """Add one sample's entry to its seed file. No await between read and write, so samples
    of one eval (one event loop) never interleave here."""
    path = prose_path(seed, out_dir)
    mark = (run_id, str(path))
    if mark in _STARTED and path.exists():
        doc = json.loads(path.read_text())
    else:
        doc = {"seed": seed, "instruction": INSTRUCTION, "texts": {}}
        _STARTED.add(mark)
    doc["texts"][key] = e
    _write(path, doc)


@solver
def rewrite(out_dir: str) -> Solver:
    # spec D5, §7.1 (R26-1): the global model settings, from the window [harness] table
    h = load_config("window").harness
    config = GenerateConfig(
        reasoning_effort=h["reasoning_effort"], max_retries=int(h["max_retries"])
    )

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        md = state.metadata
        job = ProseJob(md["person"], md["msg_key"], md["facts"], md["draft"])
        model = get_model(role="people", required=True)  # never the agent model by default
        output = await model.generate(state.messages, config=config)
        state.output = output
        state.messages.append(output.message)
        e = entry(job, _clean(output.completion), str(model))
        if not e["ok"]:
            reason = "; ".join(e["reasons"])
            transcript().info(
                {"type": "people_fallback", "key": job.key, "reason": reason}, source=SOURCE
            )
        _add_entry(out_dir, md["run_id"], int(md["seed"]), job.key, e)
        return state

    return solve


@task
def pregen_people(seeds: str = "1001,1002,1003", out_dir: str | None = None) -> Task:
    """One sample per (seed, person, msg_key); writes `<out_dir>/seed_<n>.json`."""
    cfg = load_config("window")
    out = str(out_dir or people_prose_dir())
    run_id = uuid.uuid4().hex[:12]
    samples = []
    for seed in _ints(seeds):
        for j in prose_jobs(cfg, seed, PREGEN_DAYS):
            samples.append(
                Sample(
                    id=f"s{seed}-{j.person}-{j.msg_key}",
                    input=[
                        ChatMessageUser(content=f"{INSTRUCTION.format(n=j.max_words)}\n\n{j.draft}")
                    ],
                    metadata={
                        "seed": seed,
                        "person": j.person,
                        "msg_key": j.msg_key,
                        "key": j.key,
                        "facts": j.facts,
                        "draft": j.draft,
                        "run_id": run_id,
                    },
                )
            )
    return Task(dataset=samples, solver=rewrite(out))
