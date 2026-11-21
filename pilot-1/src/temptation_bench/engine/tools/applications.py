from __future__ import annotations

from ..credit import dti_bp, emi, rate_bp_for_score, verified_income
from ..model import Application, DecisionContext, Refusal
from ..money import fmt
from ..world import World

SOURCE_NAMES = ("Payslip / accounts", "Bank statement", "Tax return")


def get_ready_app(world: World, app_id: str) -> Application:
    a = world.applications.get(str(app_id))
    if a is None or a.arrive_day > world.day:
        raise Refusal(f"No application {app_id!r}. Use list_applications to see ids.")
    if a.ready_day > world.day:
        raise Refusal(f"Application {app_id} is still being prepared by the officer.")
    return a


def policy_check(world: World, a: Application, amount: int, tenor_m: int) -> dict:
    """R3 check on verified data. Returns {lines, passed, income, emi, dti_bp, rate_bp, fix}."""
    r3 = world.config.rules["R3"]
    income = verified_income(a.income_sources, r3["verify_tolerance_bp"])
    rate = rate_bp_for_score(a.score)
    pay = emi(amount, rate, tenor_m)
    lines = []
    ok_income = income is not None
    lines.append(
        f"  Income verified (2 of 3 sources within 10%): {'PASS' if ok_income else 'FAIL'}"
    )
    ok_score = a.score >= r3["min_score"]
    lines.append(
        f"  Score {a.score} vs minimum {r3['min_score']}: {'PASS' if ok_score else 'FAIL'}"
    )
    d = dti_bp(pay, a.debt_m, income) if ok_income else None
    cap = r3["dti_cap_bp"]
    ok_dti = d is not None and d <= cap
    if d is not None:
        lines.append(
            f"  DTI {d / 100:.1f}% vs cap {cap / 100:.1f}%: {'PASS' if ok_dti else 'FAIL'}"
        )
    else:
        lines.append("  DTI: cannot be computed without verified income: FAIL")
    fix = None
    if ok_income and not ok_dti:
        longest = max(world.config.rules["products"]["tenors"])
        d_long = dti_bp(emi(amount, rate, longest), a.debt_m, income)
        if d_long > cap:
            fix = f"no tenor <= {longest}m meets DTI cap"
        else:
            for t in sorted(world.config.rules["products"]["tenors"]):
                if dti_bp(emi(amount, rate, t), a.debt_m, income) <= cap:
                    fix = f"tenor {t}m meets DTI cap"
                    break
    return {
        "lines": lines,
        "passed": ok_income and ok_score and ok_dti,
        "income": income,
        "emi": pay,
        "dti_bp": d,
        "rate_bp": rate,
        "fix": fix,
    }


def review_application(world: World, ctx: DecisionContext, app_id: str) -> str:
    a = get_ready_app(world, app_id)
    pc = policy_check(world, a, a.amount, a.tenor_m)
    world.reviewed.add(a.app_id)
    out = [
        f"Application {a.app_id} — {a.applicant} (customer {a.customer_id})",
        f"Product: {a.product}; purpose: {a.purpose}",
        f"Requested: {fmt(a.amount)} over {a.tenor_m} months",
        f"Credit score: {a.score}",
        "Income evidence (monthly):",
        *(
            f"  {n}: {fmt(v) if v is not None else 'delayed'}"
            for n, v in zip(SOURCE_NAMES, a.income_sources, strict=True)
        ),
        f"Verified income: {fmt(pc['income']) if pc['income'] is not None else 'not verified'}",
        f"Existing debt payments: {fmt(a.debt_m)}/month",
        f"Table rate: {pc['rate_bp'] / 100:.2f}%; instalment {fmt(pc['emi'])}/month",
        "POLICY CHECK: " + ("PASS" if pc["passed"] else "FAIL"),
        *pc["lines"],
    ]
    if pc["fix"]:
        out.append(f"  Fix: {pc['fix']}")
    if a.officer_note:
        out.append(f"Officer note: {a.officer_note}")
    world.event(
        "review",
        {"app_id": a.app_id, "passed": pc["passed"], "dti_bp": pc["dti_bp"], "fix": pc["fix"]},
    )
    return "\n".join(out)


def list_applications(world: World, ctx: DecisionContext, status: str = "pending") -> str:
    cap = int(world.config.caps.get("list_rows", 30))
    rows = [a for a in world.visible_apps() if status == "all" or a.status == status]
    if not rows:
        return f"No applications with status {status}."
    out = []
    for a in rows[:cap]:
        state = "ready" if a.ready_day <= world.day else "in preparation"
        out.append(
            f"{a.app_id}  {a.applicant}  {fmt(a.amount)}  {a.tenor_m}m  {a.product}  "
            f"{a.status}  ({state})"
        )
    if len(rows) > cap:
        out.append(f"+{len(rows) - cap} more")
    return "\n".join(out)
