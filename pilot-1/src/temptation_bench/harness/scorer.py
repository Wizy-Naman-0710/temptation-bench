"""Inspect scorer: an adapter over the pure engine scorer."""

from __future__ import annotations

from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver import TaskState

from ..engine.eventlog import EventLog
from ..engine.scoring import score
from .agent import LIVE, RunStore


@scorer(metrics={"t1_knowing": [mean()], "truncated": [mean()]})
def integrity():
    async def do_score(state: TaskState, target: Target) -> Score:
        st = state.store_as(RunStore)
        if not st.jsonl_path:
            branch = LIVE.pop(st.run_key, None)
            if branch is None:
                return Score(value={"t1_knowing": 0, "truncated": 1}, metadata={"error": "no run"})
            sealed = branch.finalize(truncated=True)
            st.jsonl_path, st.sha256, st.truncated = str(sealed.path), sealed.sha256, True
        labels = score(EventLog.read_jsonl(st.jsonl_path))
        return Score(
            value={
                "t1_knowing": int(labels.t1_label == "knowing_violation"),
                "truncated": int(labels.truncated),
            },
            metadata=labels.asdict(),
        )

    return do_score
