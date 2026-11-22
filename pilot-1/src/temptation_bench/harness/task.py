"""@task temptation_bench: one sample per (seed, dose)."""

from __future__ import annotations

import uuid

from inspect_ai import Task, task
from inspect_ai.dataset import Sample

from temptation_bench.engine.config import load_config
from temptation_bench.engine.people import make_people
from temptation_bench.harness.agent import FIRST_MESSAGE, branch_manager, setup_run
from temptation_bench.harness.pricing import register_prices
from temptation_bench.harness.scorer import integrity


def _ints(s: str | int) -> list[int]:
    return [int(x) for x in str(s).replace(" ", "").split(",") if x]


@task
def temptation_bench(
    variant: str = "window",
    seeds: str = "1001",
    doses: str = "3000000",
    people: str | None = None,
    token_limit: int | None = None,
) -> Task:
    """`time_limit` comes from the variant's `[harness] time_limit_s` (window 1 h, full 3 h;
    DD §13A). `people` ("template" | "prose") defaults to the variant's `people`; prose
    reads `configs/people_prose/seed_<n>.json` ($PEOPLE_PROSE_DIR). `token_limit` (default
    none) is set by the runner after the smoke (2 x mean smoke tokens per run); Inspect's
    own `--token-limit` also overrides it."""
    register_prices()
    config = load_config(variant)
    harness = config.harness
    people = people or config.people  # the variant's `people` unless the caller sets it
    for seed in _ints(seeds):  # fail before any model call: bad name or missing prose file
        make_people(people, seed)
    run_id = uuid.uuid4().hex[:12]
    samples = [
        Sample(
            id=f"s{seed}-d{dose}",
            input=FIRST_MESSAGE,
            metadata={
                "seed": seed,
                "dose": dose,
                "variant": variant,
                "run_id": run_id,
                "people": people,
            },
        )
        for seed in _ints(seeds)
        for dose in _ints(doses)
    ]
    return Task(
        dataset=samples,
        solver=[setup_run(), branch_manager(variant)],
        scorer=integrity(),
        time_limit=int(harness["time_limit_s"]),
        token_limit=None if token_limit is None else int(token_limit),
    )
