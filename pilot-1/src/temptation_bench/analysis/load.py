"""Load sealed engine JSONL (and optionally an Inspect .eval) into frames for analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..engine.eventlog import EventLog

TOOL_KIND: dict[str, str] = {
    "get_status": "read",
    "list_applications": "read",
    "review_application": "read",
    "get_portfolio_report": "read",
    "list_emails": "read",
    "read_email": "read",
    "edit_application": "decide",
    "approve_loan": "decide",
    "reject_loan": "decide",
    "escalate_to_rcc": "decide",
    "file_report": "report",
    "send_email": "report",
    "log_gift": "report",
    "report_to_compliance": "report",
    "write_note": "memory",
    "read_notes": "memory",
    "set_reminder": "memory",
    "wait_for_next_day": "wait",
}
KINDS = ("read", "decide", "report", "memory", "wait")


@dataclass
class RunFrame:
    tool_calls: pd.DataFrame
    meta: dict = field(default_factory=dict)


def load_run(jsonl_path: Path, eval_path: Path | None = None) -> RunFrame:
    events = EventLog.read_jsonl(jsonl_path)
    cfg = next((e.data for e in events if e.type == "run_config"), {})
    rows = [
        {
            "seq": e.seq,
            "day": e.day,
            "minute": e.minute,
            "tool": e.data["tool"],
            "kind": TOOL_KIND.get(e.data["tool"], "read"),
            "outcome": e.data["outcome"],
        }
        for e in events
        if e.type == "tool_call"
    ]
    cols = ["seq", "day", "minute", "tool", "kind", "outcome"]
    meta = {
        "seed": cfg.get("seed"),
        "dose": cfg.get("dose"),
        "mode": cfg.get("mode"),
        "model": "bot",
    }
    if eval_path is not None:
        from inspect_ai.log import read_eval_log

        meta["model"] = read_eval_log(str(eval_path), header_only=True).eval.model
    return RunFrame(pd.DataFrame(rows, columns=cols), meta)
