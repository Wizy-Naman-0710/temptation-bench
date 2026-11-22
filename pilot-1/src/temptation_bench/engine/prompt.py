"""The system prompt (DD §6.10), rendered from config.

Seven parts: role, objective (+ the calibrated campaign target), team and workflow, how
time works, memory, the compact rulebook of the active pilot rules, and the weekly MIS
format. Wording lives in `configs/world.toml` ([texts], [prompt]); every number is filled
in here from `rules.toml`, [campaign], [minutes], [world] or the calibrated target, so the
prompt cannot drift from the rules the engine enforces (Prosus `sync_config --check`;
tests/engine/test_prompt.py). No current date: the date is in every status line.
"""

from __future__ import annotations

from .calendar import DAY_START_MIN
from .money import Money, fmt_whole
from .tools.reports import MIS_HEADER


def pct(bp: int) -> str:
    """{bp} -> "40%" / "42.5%"."""
    whole, rest = divmod(bp, 100)
    return f"{whole}%" if rest == 0 else f"{whole}.{rest:02d}".rstrip("0") + "%"


def _clock(minute: int) -> str:
    t = DAY_START_MIN + minute
    return f"{t // 60:02d}:{t % 60:02d}"


def _premiums(table: list[list[int]]) -> str:
    """R4 [[min score, premium bp], ...] (descending) -> "750 and above +0 pp; ..."."""
    parts = []
    upper = None
    for lo, prem in table:
        pp = f"+{prem // 100} pp" if prem % 100 == 0 else f"+{prem / 100:g} pp"
        if upper is None:
            parts.append(f"{lo} and above {pp}")
        elif lo > 0:
            parts.append(f"{lo}-{upper - 1} {pp}")
        else:
            parts.append(f"below {upper} {pp}")
        upper = lo
    return "; ".join(parts)


def _tenors(tenors: list[int]) -> str:
    t = [str(x) for x in tenors]
    return t[0] if len(t) == 1 else f"{', '.join(t[:-1])} or {t[-1]}"


def _minutes(cfg) -> str:
    """One line per minute cost, tools in the [minutes] order; the 0-minute
    wait_for_next_day is described in its own line."""
    by: dict[int, list[str]] = {}
    for tool, m in cfg.minutes.items():
        if m > 0:
            by.setdefault(int(m), []).append(tool)
    line = cfg.prompt["minutes_line"]
    return "\n".join(line.format(minutes=m, tools=", ".join(by[m])) for m in sorted(by))


def render_system_prompt(cfg, target: Money) -> str:
    t, p, r = cfg.texts, cfg.prompt, cfg.rules
    buckets = r["R5"]["buckets"]
    names = ["write-off" if b == "WRITE_OFF" else b for b in buckets]
    close = _clock(cfg.day_minutes)
    v = {
        "target": fmt_whole(target),
        "npl_ceiling": pct(cfg.campaign["npl_ceiling_bp"]),
        "rcc_reply_bd": r["RCC"]["reply_bd"],
        "open": _clock(0),
        "close": close,
        "minutes": _minutes(cfg),
        "several_tools": t["several_tools"],
        "memory": t["memory"],
        "manager_limit": fmt_whole(r["R2"]["manager_limit"]),
        "dti_cap": pct(r["R3"]["dti_cap_bp"]),
        "min_score": r["R3"]["min_score"],
        "verify_tol": pct(r["R3"]["verify_tolerance_bp"]),
        "base_rate": pct(r["R4"]["base_bp"]),
        "premiums": _premiums(r["R4"]["premium_bp"]),
        "buckets": ", ".join(b for b in buckets if b not in ("NPL", "WRITE_OFF")),
        "npl_dpd": r["R5"]["npl_over_dpd"],
        "write_off_dpd": r["R5"]["write_off_dpd"],
        "provisions": ", ".join(
            f"{n} {pct(bp)}" for n, bp in zip(names, r["R6"]["provision_bp"], strict=True)
        ),
        "gift_limit": fmt_whole(r["R12"]["gift_limit"]),
        "gift_months": r["R12"]["period_months"],
        "gift_log_bd": r["R12"]["log_within_bd"],
        "mis_tolerance": pct(r["R14"]["tolerance_bp"]),
        "audit_notice_bd": r["R15"]["notice_bd"],
        "min_amount": fmt_whole(r["products"]["min_amount"]),
        "max_amount": fmt_whole(r["products"]["max_amount"]),
        "tenors": _tenors(r["products"]["tenors"]),
        "header": MIS_HEADER,
        "example": p["mis_example"],
    }
    policy = [p["policy_title"], *(p[k].format(**v) for k in p["rules"])]
    policy.append(p["products"].format(**v))
    parts = [
        t["role"],  # 1 role (fixed start date only)
        f"{t['objective']}\n{p['target_line'].format(**v)}",  # 2 objective + target
        p["team"].format(**v),  # 3 team and workflow
        p["time"].format(**v),  # 4 how time works
        p["memory"].format(**v),  # 5 memory
        "\n".join(policy),  # 6 compact rulebook (active rules only)
        p["mis"].format(**v),  # 7 weekly MIS format
    ]
    return "\n\n".join(parts)
