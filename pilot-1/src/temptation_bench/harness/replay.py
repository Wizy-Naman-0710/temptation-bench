"""Replay one sample of a `.eval` into a fresh Branch (DD §12; spec §9.2, cut-list item 5).

The loop journals every engine input into the transcript, in order:
- `engine_call` (tools.call_engine): tool name, the exact engine arguments and the
  DecisionContext computed from the trimmed input actually sent;
- `harness` (agent._harness_wait): a hidden `harness_*` event the loop logged.

Replay feeds them, in transcript order, to `Branch.new` with the sample's seed, dose,
variant and people backend (prose: the same `configs/people_prose/seed_<n>.json`, checked
by its SHA-256 in the mirrored `run_config`), using the logged DecisionContext per call
(integrity-and-invariants.md §4), so compaction is not re-run. A run the loop ended early
(cap, error) is sealed `truncated=True`, as the loop's `finally` does. The result is the
same JSONL byte for byte.
"""

from __future__ import annotations

from pathlib import Path

from inspect_ai.event import InfoEvent, SpanBeginEvent
from inspect_ai.log import read_eval_log_sample

from ..engine.branch import Branch
from ..engine.config import load_config, runs_dir
from ..engine.model import DecisionContext, Refusal, SealedLog
from ..engine.people import make_people
from .agent import HARNESS
from .tools import ENGINE_CALL


class ReplayError(RuntimeError):
    """The `.eval` journal does not match the sample's tool calls."""


def _check_people(sample, people) -> None:
    """Under prose, replay must read the very pregen file the run read: the mirrored
    `run_config` carries its SHA-256 (template runs carry none)."""
    for e in sample.events:
        if isinstance(e, InfoEvent) and e.source == "engine" and isinstance(e.data, dict):
            if e.data.get("type") == "run_config":
                want = e.data["data"].get("people_sha256")
                have = getattr(people, "sha256", None) or None
                if want != have:
                    raise ReplayError(f"people prose file differs from the run's ({want})")
                return


def replay(eval_path: Path, sample_id: str, *, log_path: Path | None = None) -> SealedLog:
    # long strings (e.g. a CSV argument) are stored as attachment:// refs unless resolved
    sample = read_eval_log_sample(str(eval_path), id=sample_id, resolve_attachments=True)
    md = sample.metadata
    config = load_config(md["variant"])
    path = Path(log_path) if log_path else runs_dir() / "replay" / f"{sample_id}.jsonl"
    people = make_people(md.get("people", "template"), int(md["seed"]))
    _check_people(sample, people)
    branch = Branch.new(config, int(md["seed"]), int(md["dose"]), people=people, log_path=path)
    # A model tool call runs inside a span of type "tool" named after the function; the
    # loop's own wait_for_next_day runs outside any tool span.
    tool_spans = {
        e.id: e.name for e in sample.events if isinstance(e, SpanBeginEvent) and e.type == "tool"
    }
    for e in sample.events:
        if not isinstance(e, InfoEvent) or not isinstance(e.data, dict):
            continue
        if e.source == HARNESS:
            branch.harness_event(e.data["type"], e.data["data"])
        elif e.source == ENGINE_CALL:
            tool = tool_spans.get(e.span_id)  # None for the loop's own wait_for_next_day
            if tool is not None and tool != e.data["tool"]:
                raise ReplayError(f"journal says {e.data['tool']}, tool span {tool}")
            try:
                branch.call(e.data["tool"], ctx=DecisionContext(**e.data["ctx"]), **e.data["args"])
            except Refusal:
                pass  # refused in the run too; the engine logs it the same way
    return branch.finalize(truncated=not branch.over)
