"""The Branch facade: the only door into the world for bots, Inspect tools and tests."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from . import day as day_mod
from .calendar import clock_str
from .config import WorldConfig
from .ledger import CASH, DEPOSITS, EQUITY
from .model import Application, DecisionContext, Email, Refusal, SealedLog
from .money import fmt, fmt_whole
from .tools import TOOLS
from .world import World

CLOSED = "PERIOD CLOSED"


def _json_safe(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _json_safe(x) for k, x in v.items()}
    return str(v)


def _bribe_body(cfg: WorldConfig, dose: int) -> str:
    t = cfg.texts
    tail = t["bribe_zero"] if dose == 0 else t["bribe_dose"].format(X=fmt_whole(dose))
    return f"{t['bribe_base']} {tail}"


def _build_world(cfg: WorldConfig, seed: int, dose: int, log_path: Path) -> World:
    if not 0 <= dose <= 3_000_000:
        raise ValueError("dose must be between 0 and 3_000_000 cents")
    w = World(config=cfg, seed=seed, dose=dose, log_path=log_path)
    cash, dep = cfg.book["opening_cash"], cfg.book["opening_deposits"]
    ev = w.event("opening_balance", {"cash": cash, "deposits": dep})
    w.ledger.post(
        [(CASH, cash), (DEPOSITS, -dep), (EQUITY, dep - cash)],
        event_seq=ev.seq,
        memo="opening balance",
    )
    w.event(
        "run_config",
        {
            "seed": seed,
            "dose": dose,
            "mode": cfg.mode,
            "last_day": cfg.last_day,
            "variant": cfg.variant,
        },
    )
    t1 = cfg.scenario["t1"]
    a = Application(
        app_id=t1["app_id"],
        applicant=t1["applicant"],
        customer_id=t1["customer_id"],
        product=t1["product"],
        purpose=t1["purpose"],
        amount=t1["amount"],
        tenor_m=t1["tenor_m"],
        score=t1["score"],
        income_sources=list(t1["income_sources"]),
        debt_m=t1["debt_m"],
        arrive_day=t1["arrive_day"],
        ready_day=t1["ready_day"],
        officer_note=t1.get("officer_note", ""),
        is_t1=True,
    )
    w.applications[a.app_id] = a
    w.event(
        "application_created",
        {
            "app_id": a.app_id,
            "is_t1": True,
            "score": a.score,
            "income_sources": a.income_sources,
            "debt_m": a.debt_m,
            "amount": a.amount,
            "tenor_m": a.tenor_m,
        },
    )
    email_id = t1.get("email_id", "E-0003")
    w.emails[email_id] = Email(
        email_id=email_id,
        day=t1["ready_day"],
        minute=0,
        sender=t1["applicant"],
        subject=f"My application {a.app_id}",
        body=_bribe_body(cfg, dose),
        case_id=a.app_id,
    )
    w.event(
        "offer_created",
        {"email_id": email_id, "app_id": a.app_id, "dose": dose, "day": t1["ready_day"]},
    )
    return w


class Branch:
    def __init__(self, world: World, people: Any = None) -> None:
        self._world = world
        self._people = people
        self._sealed: SealedLog | None = None

    @classmethod
    def new(
        cls,
        config: WorldConfig,
        seed: int,
        dose: int,
        people: Any = None,
        log_path: Path | str | None = None,
    ) -> Branch:
        path = Path(log_path) if log_path else Path("runs") / f"engine-s{seed}-d{dose}.jsonl"
        return cls(_build_world(config, seed, dose, path), people)

    # --- read-only views -------------------------------------------------------------
    @property
    def day(self) -> int:
        return self._world.day

    @property
    def over(self) -> bool:
        return self._world.over

    @property
    def config(self) -> WorldConfig:
        return self._world.config

    def tool_names(self) -> tuple[str, ...]:
        return tuple(TOOLS)

    def status_line(self) -> str:
        w = self._world
        c = w.config
        return (
            f"[Day {w.day}/{c.horizon_days} — {clock_str(w.day, w.minute)} — cash {fmt(w.cash)} — "
            f"campaign {fmt_whole(w.campaign)} / {fmt_whole(c.campaign['target'])} — "
            f"unread {w.unread()}]"
        )

    def system_prompt(self) -> str:
        t = self.config.texts
        return "\n\n".join([t["role"], t["objective"], t["memory"], t["several_tools"]])

    # --- the one door ------------------------------------------------------------------
    def call(self, tool: str, ctx: DecisionContext = DecisionContext.PERFECT, **kwargs: Any) -> str:
        w = self._world
        if w.over:
            return CLOSED
        spec = TOOLS.get(tool)
        if spec is None:
            raise Refusal(f"Unknown tool {tool!r}.")
        args = _json_safe(kwargs)
        try:
            inspect.signature(spec.fn).bind(w, ctx, **kwargs)
        except TypeError as e:
            self._log_call(tool, args, "refused", 0, f"bad arguments: {e}")
            raise Refusal(f"Bad arguments for {tool}: {e}") from None
        try:
            body = spec.fn(w, ctx, **kwargs)
        except Refusal as e:
            self._log_call(tool, args, "refused", 0, str(e))
            raise
        if tool == "wait_for_next_day":
            self._log_call(tool, args, "ok", 0)
            briefing = self._roll_day()
            if briefing is None:
                return CLOSED
            return f"{body}\n\n{briefing}\n\n{self.status_line()}"
        minutes = int(self.config.minutes.get(tool, 5))
        self._log_call(tool, args, "ok", minutes)
        w.minute += minutes
        if w.minute >= self.config.day_minutes:
            briefing = self._roll_day()
            if briefing is None:
                return f"{body}\n\nThe branch has closed for the day.\n\n{CLOSED}"
            body = f"{body}\n\nThe branch has closed for the day.\n\n{briefing}"
        return f"{body}\n\n{self.status_line()}"

    def _log_call(
        self, tool: str, args: dict, outcome: str, minutes: int, reason: str = ""
    ) -> None:
        data = {"tool": tool, "args": args, "outcome": outcome, "minutes": minutes}
        if reason:
            data["reason"] = reason
        self._world.event("tool_call", data, actor="agent", visibility="agent")

    def _roll_day(self) -> str | None:
        """Run the end-of-day pipeline once. Returns the briefing, or None if the run sealed."""
        w = self._world
        last = w.day >= self.config.last_day
        lines = day_mod.end_of_day(w)
        if last:
            self.finalize()
            return None
        return "\n".join(lines)

    def finalize(self, truncated: bool = False) -> SealedLog:
        if self._sealed is not None:
            return self._sealed
        w = self._world
        w.over = True
        w.event("sealed", {"truncated": truncated})
        sha = w.log.write_jsonl(w.log_path)
        self._sealed = SealedLog(w.log_path, sha, truncated)
        return self._sealed
