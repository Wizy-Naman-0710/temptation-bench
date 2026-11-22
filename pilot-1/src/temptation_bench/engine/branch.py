"""The Branch facade: the only door into the world for bots, Inspect tools and tests."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from . import book, runoff, runtag, scenario
from . import day as day_mod
from .calendar import clock_str
from .config import WorldConfig, check_factors, check_target, runs_dir
from .invariants import check_all, check_append_only, check_output
from .model import DecisionContext, Refusal, SealedLog
from .money import fmt, fmt_whole
from .people import PeopleBackend, TemplatePeople
from .prompt import render_system_prompt
from .tools import HANDLERS, TOOLS
from .world import World


def _json_safe(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _json_safe(x) for k, x in v.items()}
    return str(v)


def _build_world(cfg: WorldConfig, seed: int, dose: int, log_path: Path, people) -> World:
    if not 0 <= dose <= 3_000_000:
        raise ValueError("dose must be between 0 and 3_000_000 cents")
    check_factors(cfg.factors)  # again here: a model_copy'd config skips the validator
    check_target(cfg.campaign)  # no run starts without a calibrated target
    missing = sorted(set(TOOLS) - set(cfg.minutes))
    if missing:  # checked up front so a call can never fail after changing state
        raise ValueError(f"configs [minutes] has no entry for: {', '.join(missing)}")
    plan = scenario.plan_scenario(seed, cfg)  # before any event: a ScenarioError leaves no log
    w = World(config=cfg, seed=seed, dose=dose, log_path=log_path)
    w.event("run_config", runtag.run_config(cfg, seed, dose, people))  # always the first event
    w.handlers.update(HANDLERS)  # replies scheduled by tools (RCC, Compliance, boss)
    book.open_book(w)
    scenario.install(w, plan, people)
    check_append_only(w)  # I8 marks from the start, so pre-first-check changes are seen
    return w


class Branch:
    # I15 (DD §7, §13A): outputs meet the cap by design. False (paid runs): an over-long
    # output is clipped and a hidden `output_clipped` event records it. True (tests, set in
    # conftest): it raises InvariantError("I15") so an overflow fails loudly in CI.
    strict_output: bool = False

    def __init__(self, world: World, people: PeopleBackend | None = None) -> None:
        self._world = world
        self._people = people
        self._sealed: SealedLog | None = None

    @classmethod
    def new(
        cls,
        config: WorldConfig,
        seed: int,
        dose: int,
        people: PeopleBackend | None = None,
        log_path: Path | str | None = None,
    ) -> Branch:
        path = Path(log_path) if log_path else runs_dir() / f"engine-s{seed}-d{dose}.jsonl"
        people = people if people is not None else TemplatePeople()
        return cls(_build_world(config, seed, dose, path, people), people)

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
        """DD §6.10: rendered from config with the calibrated campaign target."""
        return render_system_prompt(self.config, self.config.campaign["target"])

    def opening_briefing(self) -> str:
        """The D1 09:00 morning briefing (DD §6.8), shown with the first message. Read-only:
        it logs nothing, so it never changes the run's JSONL."""
        return self._finish_text("\n".join(day_mod.opening_briefing(self._world)))

    # --- the one door ------------------------------------------------------------------
    def call(self, tool: str, ctx: DecisionContext = DecisionContext.PERFECT, **kwargs: Any) -> str:
        w = self._world
        closed = self.config.texts["period_closed"]
        if w.over:
            return closed
        args = _json_safe(kwargs)
        spec = TOOLS.get(tool) if isinstance(tool, str) else None
        if spec is None:
            self._log_call(str(tool)[:60], args, "refused", 0, "unknown tool")
            raise Refusal(f"Unknown tool {str(tool)[:60]!r}. Use one of the listed tools.")
        try:
            inspect.signature(spec.fn).bind(w, ctx, **kwargs)
        except TypeError as e:
            self._log_call(tool, args, "refused", 0, f"bad arguments: {e}")
            raise Refusal(f"Bad arguments for {tool}: {e}") from None
        minutes = int(self.config.minutes[tool])  # looked up before the tool changes state
        try:
            body = spec.fn(w, ctx, **kwargs)
        except Refusal as e:
            self._log_call(tool, args, "refused", 0, str(e))
            raise
        if tool == "wait_for_next_day":
            self._log_call(tool, args, "ok", 0)
            briefing = self._roll_day()
            if briefing is None:
                return closed
            return self._finish(tool, f"{body}\n\n{briefing}")
        self._log_call(tool, args, "ok", minutes)
        w.minute += minutes
        if w.minute >= self.config.day_minutes:
            if w.day >= self.config.last_day:
                # This call seals the run: build (and, if cut, log) its output first, so
                # an `output_clipped` event lands in the sealed log.
                out = self._clip(tool, f"{body}\n\nThe branch has closed for the day.", closed)
                self._roll_day()
                if spec.decision:
                    check_all(w)
                return out
            briefing = self._roll_day()
            body = f"{body}\n\nThe branch has closed for the day.\n\n{briefing}"
        out = self._finish(tool, body)
        if spec.decision:  # DD §7: invariants after every decision, not only at day end
            check_all(w)
        return out

    def harness_event(self, type: str, data: dict[str, Any]) -> None:
        """A hidden event the agent loop logs about its own policy (DD §9: `harness_day_cap`,
        `harness_auto_advance`). It changes no world state and nothing the agent sees;
        bots never call it. Ignored once the run is sealed."""
        if not type.startswith("harness_"):
            raise ValueError(f"harness events are named harness_*, got {type!r}")
        if not self._world.over:
            self._world.event(type, _json_safe(data), actor="harness")

    def _finish_text(self, body: str) -> str:
        out = f"{body}\n\n{self.status_line()}"
        check_output(out, int(self.config.caps["output_chars"]))
        return out

    def _finish(self, tool: str, body: str) -> str:
        return self._clip(tool, body, self.status_line())

    def _clip(self, tool: str, body: str, tail: str) -> str:
        """I15: every output (incl. briefings) stays within [caps].output_chars. Strict:
        an overflow raises. Otherwise the tail (status line) is kept, the body is cut with
        a short notice, and a hidden `output_clipped` event records the cut."""
        cap = int(self.config.caps["output_chars"])
        out = f"{body}\n\n{tail}"
        if len(out) <= cap:
            return out
        if self.strict_output:
            check_output(out, cap)  # raises InvariantError("I15")
        self._world.event("output_clipped", {"tool": tool, "chars": len(out), "cap": cap})
        note = self.config.texts["output_cut"]
        room = cap - len(tail) - 2
        out = f"{body[: room - len(note) - 1]}\n{note}\n\n{tail}"
        check_output(out, cap)
        return out

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
        """Run-off, then seal (idempotent). Later calls return PERIOD CLOSED and change
        nothing. A run cut short by a limit (truncated) still gets its run-off."""
        if self._sealed is not None:
            return self._sealed
        w = self._world
        w.over = True
        w.event("runoff", runoff.runoff(w).asdict())
        w.event("sealed", {"truncated": truncated})
        sha = w.log.write_jsonl(w.log_path)
        self._sealed = SealedLog(w.log_path, sha, truncated)
        return self._sealed
