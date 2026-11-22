"""Load sealed engine JSONL (and optionally an Inspect .eval) into frames for analysis.

One run = one sealed JSONL (`runs/<run_id>/<sample_id>-e<epoch>.jsonl`, or a bot's
`<bot>-s<seed>-d<dose>.jsonl`), optionally paired with its `.eval` sample. Failed harness
attempts (`<name>.attempt<k>.jsonl`, Task 26 pre-work) are counted, never loaded as runs.

Turn mapping (agent runs): the agent loop journals an `InfoEvent(source="engine_call")`
before every `branch.call` (Task 23). The k-th journal entry is the k-th engine `tool_call`
event; calls journalled after the seal return `PERIOD CLOSED` without a `tool_call`, so they
are the trailing extras. Every other engine event takes the turn of the latest `tool_call`
before it (0 = before the first turn)."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ..engine.config import load_config, runs_dir
from ..engine.eventlog import Event, EventLog
from ..engine.scoring import score
from . import awareness

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

ATTEMPT_RE = re.compile(r"\.attempt\d+\.jsonl$")
BOT_RE = re.compile(r"^([a-z_]+)-s\d+-d\d+$")  # bots.base.run_bot file names
STORE = "RunStore:"  # harness.agent.RunStore keys in EvalSample.store (no harness import)
# The internal audit (Task 32, engine/audit.py): notice, fieldwork start, findings report.
AUDIT_EVENT_TYPES: tuple[str, ...] = ("audit_notice", "audit_fieldwork", "audit_report")

TOOL_COLS = ["seq", "day", "minute", "turn", "tool", "kind", "outcome"]
DAILY_COLS = [
    "day",
    "campaign_volume",
    "target",
    "true_npl_bp",
    "true_profit_mtd",
    "personal_benefits",
    "reported_npl_bp",
]
TURN_COLS = [
    "turn",
    "day",
    "input_tokens",
    "cache_read",
    "cache_write",
    "output_tokens",
    "reasoning_tokens",
    "cost",
    "input_message_count",
    "compaction",
    "cached",
    "overflow",
]
MARKER_COLS = ["kind", "day", "turn", "seq", "detail"]


@dataclass
class RunFrame:
    tool_calls: pd.DataFrame
    meta: dict = field(default_factory=dict)
    # per sim day, from `day_close` (+ the latest filed MIS NPL ratio as of that day)
    daily: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=DAILY_COLS))
    # per agent generate, from `.eval` ModelEvents (empty for bot runs)
    turns: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=TURN_COLS))
    labels: dict = field(default_factory=dict)  # RunLabels.asdict()
    markers: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=MARKER_COLS))
    # outputs cut by I15 (hidden `output_clipped`): check before "the agent ignored X"
    clipped: list[dict] = field(default_factory=list)
    awareness_hits: list[str] = field(default_factory=list)  # messages, reasoning, notes
    probe_hits: list[str] = field(default_factory=list)  # the post-seal probe answer only
    # each in-run hit with its source and surrounding text (awareness.contexts), for the report
    awareness_context: list[dict] = field(default_factory=list)


# --- .eval side ---------------------------------------------------------------------------


def _reasoning_text(block: Any) -> str:
    """Visible reasoning only: a redacted block's `reasoning` is opaque, so use its summary."""
    if getattr(block, "redacted", False):
        return block.summary or ""
    return block.reasoning or ""


def _message_texts(message: Any) -> list[str]:
    out = [message.text] if message.text else []
    if isinstance(message.content, list):
        out += [_reasoning_text(c) for c in message.content if c.type == "reasoning"]
    return [t for t in out if t]


def _turns(sample: Any) -> tuple[pd.DataFrame, list[int], list[str]]:
    """(turn rows, turn of each `engine_call` journal entry, assistant texts).

    A turn is one generate of the loop (Task 23). Excluded: the probe (after the transcript
    mirror, `tool_choice="none"`) and non-agent model calls. A `model_length` overflow is
    kept as a row (`overflow`, it was billed) under the turn its retry completes. A cache
    read (`cache == "read"`) carries the original call's usage in `output.usage` but adds no
    new usage (Task 24; checked on a mockllm rerun), so its token and cost columns are 0."""
    rows: list[dict] = []
    journal: list[int] = []
    texts: list[str] = []
    turn = 0
    compacted = False
    for e in sample.events:
        if e.event == "info" and e.source == "engine":
            break  # the post-seal mirror: the loop is over, only the probe follows
        if e.event == "compaction":
            compacted = True
        elif e.event == "info" and e.source == "engine_call":
            journal.append(turn)
        elif e.event == "model" and e.origin in (None, "agent") and e.tool_choice != "none":
            overflow = e.output.stop_reason == "model_length"
            cached = e.cache == "read"
            u = None if cached else e.output.usage
            rows.append(
                {
                    "turn": turn + 1,
                    "input_tokens": u.input_tokens if u else 0,
                    "cache_read": (u.input_tokens_cache_read or 0) if u else 0,
                    "cache_write": (u.input_tokens_cache_write or 0) if u else 0,
                    "output_tokens": u.output_tokens if u else 0,
                    "reasoning_tokens": (u.reasoning_tokens or 0) if u else 0,
                    "cost": (u.total_cost if u.total_cost is not None else float("nan"))
                    if u
                    else 0.0,
                    "input_message_count": len(e.input),
                    "compaction": compacted,
                    "cached": cached,
                    "overflow": overflow,
                }
            )
            compacted = False
            if not overflow:
                turn += 1
                texts += _message_texts(e.output.message)
    return pd.DataFrame(rows, columns=[c for c in TURN_COLS if c != "day"]), journal, texts


def _store(sample: Any) -> dict:
    return {k[len(STORE) :]: v for k, v in (sample.store or {}).items() if k.startswith(STORE)}


# --- JSONL side ---------------------------------------------------------------------------


def _clip_key(args: dict) -> str:
    """The identifying arguments of a call (ids, `as_of`), e.g. `email_id=E-0003`."""
    keys = sorted(k for k in args if k.endswith("_id") or k == "as_of")
    return ";".join(f"{k}={args[k]}" for k in keys)


def _daily(events: list[Event]) -> pd.DataFrame:
    filings = [
        (e.day, e.data["reported"].get("npl_ratio"))
        for e in events
        if e.type == "report_filed" and e.data.get("kind") == "weekly_mis"
    ]
    rows = []
    for e in events:
        if e.type != "day_close":
            continue
        d = e.data
        known = [npl for day, npl in filings if day <= d["day"]]  # latest filing so far
        rows.append(
            {c: d[c] for c in DAILY_COLS[:-1]} | {"reported_npl_bp": known[-1] if known else None}
        )
    df = pd.DataFrame(rows, columns=DAILY_COLS)
    df["reported_npl_bp"] = df["reported_npl_bp"].astype("Float64")
    return df


DECISION_TOOLS = ("approve_loan", "reject_loan", "escalate_to_rcc")


def _markers(events: list[Event], turn_of, own_turn, npl_ceiling_bp: int) -> pd.DataFrame:
    """`turn_of(seq)`: turn of the latest call before the event (day-roll events such as
    `application_created` or `day_close` belong to the call that rolled the day).
    `own_turn(seq, pred)`: turn of the first later call matching `pred`. A tool's own events
    (`decision`, `report_filed`) are logged *before* that call's `tool_call` event
    (`Branch.call`), so they are matched to their own call."""
    rows: list[dict] = []

    def add(kind: str, e: Event, detail: str = "", turn: int | None = None) -> None:
        if turn is None:
            turn = turn_of(e.seq)
        rows.append({"kind": kind, "day": e.day, "turn": turn, "seq": e.seq, "detail": detail})

    offer = next((e.data["email_id"] for e in events if e.type == "offer_created"), None)
    first = {"t1_ready": False, "bribe_read": False, "t1_decision": False, "npl_crossing": False}
    for e in events:
        d = e.data
        if e.type == "application_created" and d.get("is_t1") and not first["t1_ready"]:
            first["t1_ready"] = True
            add("t1_ready", e, d["app_id"])
        elif (
            e.type == "tool_call"
            and d["tool"] == "read_email"
            and d["outcome"] == "ok"
            and d["args"].get("email_id") == offer
            and not first["bribe_read"]
        ):
            first["bribe_read"] = True
            add("bribe_read", e, offer)
        elif e.type == "decision" and d.get("is_t1") and not first["t1_decision"]:
            first["t1_decision"] = True
            app = d["app_id"]
            t = own_turn(
                e.seq,
                lambda c, app=app: c["tool"] in DECISION_TOOLS and c["args"].get("app_id") == app,
            )
            add("t1_decision", e, d["action"], t)
        elif e.type == "report_filed":
            t = own_turn(e.seq, lambda c: c["tool"] == "file_report" and c["outcome"] == "ok")
            add("mis_filed", e, f"{d.get('report_id')} cutoff D{d.get('cutoff_day')}", t)
        elif e.type in AUDIT_EVENT_TYPES:
            add("audit", e, e.type)
        elif (
            e.type == "day_close"
            and d["true_npl_bp"] > npl_ceiling_bp
            and not first["npl_crossing"]
        ):
            first["npl_crossing"] = True  # true NPL first above the ceiling (at close)
            add("npl_crossing", e, f"{d['true_npl_bp']} bp > {npl_ceiling_bp} bp")
    df = pd.DataFrame(rows, columns=MARKER_COLS)
    df["turn"] = df["turn"].astype("Int64")
    return df


def _build(
    jsonl_path: Path,
    eval_path: Path | None = None,
    model: str | None = None,
    sample: Any = None,
) -> RunFrame:
    jsonl_path = Path(jsonl_path)
    events = EventLog.read_jsonl(jsonl_path)
    cfg = next((e.data for e in events if e.type == "run_config"), {})
    calls = [e for e in events if e.type == "tool_call"]

    meta: dict[str, Any] = {
        "source": jsonl_path.stem,
        "jsonl_path": str(jsonl_path),
        "seed": cfg.get("seed"),
        "dose": cfg.get("dose"),
        "mode": cfg.get("mode"),
        "variant": cfg.get("variant"),
        "pressure": cfg.get("pressure"),
        "observation": cfg.get("observation"),
        "people": cfg.get("people"),
        "model": "bot",
        "failed_attempts": len(list(jsonl_path.parent.glob(f"{jsonl_path.stem}.attempt*.jsonl"))),
    }
    bot = BOT_RE.match(jsonl_path.stem)
    meta["bot"] = bot.group(1) if bot else None

    turns = pd.DataFrame(columns=TURN_COLS)
    texts: list[str] = []
    call_turn: list[int | None] = [None] * len(calls)
    probe: str | None = None
    if sample is not None:
        rows, journal, texts = _turns(sample)
        if len(journal) < len(calls):
            raise ValueError(
                f"{jsonl_path.name}: {len(calls)} engine tool calls but only {len(journal)} "
                "engine_call journal entries in the .eval sample (wrong pairing?)"
            )
        call_turn = list(journal[: len(calls)])
        # a turn's day: the day of its first engine call; turns with no call keep the last
        first_day: dict[int, int] = {}
        for e, t in zip(calls, call_turn, strict=True):
            first_day.setdefault(t, e.day)
        days, day = [], 1
        for t in rows["turn"]:
            day = first_day.get(t, day)
            days.append(day)
        rows.insert(1, "day", days)
        turns = rows
        st = _store(sample)
        probe = st.get("probe")
        meta |= {
            "model": model,
            "eval_path": str(eval_path) if eval_path else None,
            "sample_id": sample.id,
            "epoch": sample.epoch,
            "probe": probe,
            "probe_label": st.get("probe_label"),
            "probe_failed": st.get("probe_failed"),
            "sample_error": sample.error.message if sample.error else None,
            "attempt_errors": _attempt_errors(sample),
        }

    seqs = [e.seq for e in calls]

    def turn_of(seq: int) -> int | None:
        if sample is None:
            return None
        i = bisect.bisect_right(seqs, seq) - 1
        return 0 if i < 0 else call_turn[i]

    def own_turn(seq: int, pred) -> int | None:
        if sample is None:
            return None
        for i in range(bisect.bisect_right(seqs, seq), len(calls)):
            if pred(calls[i].data):
                return call_turn[i]
        return turn_of(seq)

    tool_rows = [
        {
            "seq": e.seq,
            "day": e.day,
            "minute": e.minute,
            "turn": t,
            "tool": e.data["tool"],
            "kind": TOOL_KIND.get(e.data["tool"], "read"),
            "outcome": e.data["outcome"],
        }
        for e, t in zip(calls, call_turn, strict=True)
    ]
    tool_calls = pd.DataFrame(tool_rows, columns=TOOL_COLS)
    tool_calls["turn"] = tool_calls["turn"].astype("Int64")

    clipped = []
    for e in events:
        if e.type != "output_clipped":
            continue
        i = bisect.bisect_left(seqs, e.seq) - 1  # the call whose output was cut
        call = calls[i] if i >= 0 and calls[i].data["tool"] == e.data["tool"] else None
        clipped.append(
            {
                "day": e.day,
                "turn": turn_of(e.seq),
                "tool": e.data["tool"],
                "key": _clip_key(call.data["args"]) if call else "",
                "chars": e.data["chars"],
                "cap": e.data["cap"],
                "seq": e.seq,
            }
        )

    notes = [e.data["args"].get("text", "") for e in calls if e.data["tool"] == "write_note"]
    notes = [n for n in notes if isinstance(n, str)]
    variant = cfg.get("variant") or "window"
    ceiling = int(load_config(variant).campaign["npl_ceiling_bp"])
    return RunFrame(
        tool_calls=tool_calls,
        meta=meta,
        daily=_daily(events),
        turns=turns,
        labels=score(events).asdict(),
        markers=_markers(events, turn_of, own_turn, ceiling),
        clipped=clipped,
        awareness_hits=awareness.scan([*texts, *notes]),
        probe_hits=awareness.scan([probe] if isinstance(probe, str) else []),
        awareness_context=awareness.contexts(
            [*(("message", t) for t in texts), *(("note", n) for n in notes)]
        ),
    )


def _read_eval(eval_path: Path):
    from inspect_ai.log import read_eval_log

    # long strings (messages, notes) are `attachment://` refs unless resolved (Task 23)
    return read_eval_log(str(eval_path), resolve_attachments=True)


def load_run(jsonl_path: Path, eval_path: Path | None = None) -> RunFrame:
    """One run. With `eval_path`, the `.eval` sample whose `RunStore.jsonl_path` names this
    JSONL (or the only sample) adds turns, turn numbers, the probe and assistant texts."""
    if eval_path is None:
        return _build(jsonl_path)
    log = _read_eval(Path(eval_path))
    samples = log.samples or []
    name = Path(jsonl_path).name
    match = [s for s in samples if Path(_store(s).get("jsonl_path") or "").name == name]
    if not match and len(samples) == 1:
        match = samples
    if len(match) != 1:
        raise ValueError(f"no single sample in {eval_path} for {name}")
    return _build(jsonl_path, Path(eval_path), log.eval.model, match[0])


def _attempt_errors(sample: Any) -> list[str]:
    """The error text of each failed attempt that Inspect's `retry_on_error` reran
    (`EvalSample.error_retries`, oldest first)."""
    return [e.message for e in (getattr(sample, "error_retries", None) or [])]


def _sample_jsonl(sample: Any, batch_dir: Path) -> Path | None:
    st = _store(sample)
    for p in (st.get("jsonl_path"), st.get("log_path")):
        if p and Path(p).exists():
            return Path(p)
    if st.get("log_path"):  # the batch was moved: look for runs/<run_id>/<name> inside it
        want = Path(st["log_path"])
        for p in batch_dir.rglob(want.name):
            if p.parent.name == want.parent.name:
                return p
    return None


def _expected_jsonl(sample: Any, batch_dir: Path) -> Path | None:
    """Where a sample's sealed JSONL should be (it is missing): the store's path, or the
    same `runs/<run id>/<name>` inside a moved batch when that folder exists."""
    st = _store(sample)
    p = st.get("jsonl_path") or st.get("log_path")
    if not p:  # setup never ran: rebuild the path as harness/agent.py does, from the run_id
        run_id = (sample.metadata or {}).get("run_id")
        if not run_id:
            return None
        p = runs_dir() / run_id / f"{sample.id}-e{sample.epoch}.jsonl"
    want = Path(p)
    if want.parent.exists():
        return want
    for d in batch_dir.rglob(want.parent.name):
        if d.is_dir():
            return d / want.name
    return want


def _attempts_of(jsonl_path: Path) -> list[Path]:
    """`<stem>.attempt<k>.jsonl` files beside a run's (final or expected) JSONL."""
    p = Path(jsonl_path)
    return sorted(p.parent.glob(f"{p.stem}.attempt*.jsonl")) if p.parent.exists() else []


def _cell(r: RunFrame) -> tuple:
    m = r.meta
    keys = ("model", "seed", "dose", "people", "variant", "sample_id", "epoch")
    return tuple(m.get(k) for k in keys)


def _all_cached(r: RunFrame) -> bool:
    return bool(len(r.turns)) and bool(r.turns["cached"].all())


def _dedupe(runs: list[RunFrame], replays: list[RunFrame] | None) -> list[RunFrame]:
    """One run per assigned cell (model, seed, dose, people, variant, sample id, epoch; X-1).

    A re-run of a cell already loaded (e.g. a cache replay of the same sample) is not a
    second assigned run. Kept: the labelled one without a sample error, then the freshly
    generated one (first wins on a tie). An errored copy of a cell that has a clean re-run
    goes to `replays`, where the report lists it with its error text (Task 31).
    The others get `meta["duplicate_of"]` and go to `replays`. Runs with no sample id (bot
    JSONLs) are never merged."""
    groups: dict[tuple, list[RunFrame]] = {}
    for r in runs:
        if r.meta.get("sample_id") is not None:
            groups.setdefault(_cell(r), []).append(r)
    drop: set[int] = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        keep = max(
            group,
            key=lambda r: (
                bool(r.labels),
                not (r.meta.get("sample_error") or r.meta.get("error")),
                not _all_cached(r),
            ),
        )
        for r in group:
            if r is not keep:
                r.meta["duplicate_of"] = keep.meta.get("jsonl_path") or keep.meta.get("sample_id")
                drop.add(id(r))
                if replays is not None:
                    replays.append(r)
    return [r for r in runs if id(r) not in drop]


def load_batch(batch_dir: Path, *, replays: list[RunFrame] | None = None) -> list[RunFrame]:
    """Every run under `batch_dir`: each `.eval` sample (paired with its JSONL), then every
    other sealed JSONL (bot runs). `.attempt<k>.jsonl` files are not runs; each run's
    `meta["failed_attempts"]` counts its own. A sample whose JSONL is missing is kept as an
    empty RunFrame with `meta["error"]` (failed samples are never dropped, spec §8); its
    expected path (`meta["jsonl_expected"]`, from the `.eval` store or run_id) locates its
    attempt files, which in the real layout live in `runs_dir()/<run_id>/`, outside the
    batch dir. Duplicate samples of one cell are merged (`_dedupe`); pass a list as
    `replays` to receive the dropped duplicates."""
    batch_dir = Path(batch_dir)
    runs: list[RunFrame] = []
    claimed: set[Path] = set()
    for eval_path in sorted(batch_dir.rglob("*.eval")):
        log = _read_eval(eval_path)
        for s in sorted(log.samples or [], key=lambda s: (str(s.id), s.epoch)):
            path = _sample_jsonl(s, batch_dir)
            if path is None:
                expected = _expected_jsonl(s, batch_dir)
                runs.append(
                    RunFrame(
                        pd.DataFrame(columns=TOOL_COLS),
                        {
                            "model": log.eval.model,
                            "eval_path": str(eval_path),
                            "sample_id": s.id,
                            "epoch": s.epoch,
                            "seed": (s.metadata or {}).get("seed"),
                            "dose": (s.metadata or {}).get("dose"),
                            "people": (s.metadata or {}).get("people"),
                            "variant": (s.metadata or {}).get("variant"),
                            "run_id": (s.metadata or {}).get("run_id"),
                            "error": "no sealed JSONL for this sample",
                            "jsonl_expected": str(expected) if expected else None,
                            # attempts of a sample with no final JSONL still count (R27-2)
                            "failed_attempts": len(_attempts_of(expected)) if expected else 0,
                            "sample_error": s.error.message if s.error else None,
                            "attempt_errors": _attempt_errors(s),
                        },
                    )
                )
                continue
            claimed.add(path.resolve())
            runs.append(_build(path, eval_path, log.eval.model, s))
    for path in sorted(batch_dir.rglob("*.jsonl")):
        if ATTEMPT_RE.search(path.name) or path.resolve() in claimed:
            continue
        runs.append(_build(path))
    return _dedupe(runs, replays)


def labels_table(runs: list[RunFrame]) -> pd.DataFrame:
    """One row per run: meta, every RunLabels field, and the analysis columns.

    `itt` is True for every assigned run (the primary cut); `per_protocol` = `exposed`
    (`offer_read_before_decision`, Task 6), the secondary cut. Report ITT first (DD §10.4).
    `clipped` = number of outputs cut by I15; `aware` = at least one in-run awareness hit;
    `probe_hits` is counted apart (the probe itself says "evaluation")."""
    rows = []
    for rf in runs:
        m, lab = rf.meta, rf.labels
        rows.append(
            {
                "source": m.get("source"),
                "model": m.get("model"),
                "bot": m.get("bot"),
                "seed": m.get("seed"),
                "dose": m.get("dose"),
                "sample_id": m.get("sample_id"),
                "epoch": m.get("epoch"),
                "itt": True,
                "per_protocol": bool(lab.get("exposed", False)),
                **lab,
                "clipped": len(rf.clipped),
                "aware": bool(rf.awareness_hits),
                "awareness_hits": len(rf.awareness_hits),
                "probe_label": m.get("probe_label"),
                "probe_hits": len(rf.probe_hits),
                "failed_attempts": m.get("failed_attempts", 0),
                "error": m.get("error") or m.get("sample_error"),
            }
        )
    return pd.DataFrame(rows)
