"""@task temptation_bench: one sample per (seed, dose)."""

from __future__ import annotations

import uuid

from inspect_ai import Task, task
from inspect_ai.dataset import Sample

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
    people: str = "template",
) -> Task:
    register_prices()
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
    return Task(dataset=samples, solver=[setup_run(), branch_manager(variant)], scorer=integrity())
