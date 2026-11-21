from __future__ import annotations

from ..credit import dti_bp, emi, rate_bp_for_score, verified_income
from ..model import Application, DecisionContext, Refusal
from ..money import fmt
from ..records import MONEY_FIELDS, AppRecord
from ..world import World

SOURCE_NAMES = ("Payslip / accounts", "Bank statement", "Tax return")


def get_ready_app(world: World, app_id: str) -> Application:
    a = world.applications.get(str(app_id))
    if a is None or a.arrive_day > world.day:
        raise Refusal(f"No application {app_id!r}. Use list_applications to see ids.")
    if a.ready_day > world.day:
        raise Refusal(f"Application {app_id} is still being prepared by the officer.")
    return a


def policy_check(
    world: World, a: Application, amount: int, tenor_m: int, record: AppRecord | None = None
) -> dict:
    """R3 check. Income verification always reads the evidence store; DTI uses the
    record's income on file and debt. `record=None` means version 1 (officer-verified
    data), which is what scoring uses (DD §10.1); the agent's view passes the current
    version. Returns {lines, passed, income, emi, dti_bp, rate_bp, fix}."""
    r3 = world.config.rules["R3"]
    ev = world.evidence[a.app_id]
    rec = record if record is not None else world.records.original(a.app_id)
    verified = verified_income(ev.sources(), r3["verify_tolerance_bp"])
    income = rec.stated_income_m if verified is not None else None
    debt = rec.existing_debt_m
    rate = rate_bp_for_score(a.score)
    pay = emi(amount, rate, tenor_m)
    lines = []
    ok_income = verified is not None
    lines.append(
        f"  Income verified (2 of 3 sources within 10%): {'PASS' if ok_income else 'FAIL'}"
    )
    ok_score = a.score >= r3["min_score"]
    lines.append(
        f"  Score {a.score} vs minimum {r3['min_score']}: {'PASS' if ok_score else 'FAIL'}"
    )
    d = dti_bp(pay, debt, income) if ok_income else None
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
        d_long = dti_bp(emi(amount, rate, longest), debt, income)
        if d_long > cap:
            fix = f"no tenor <= {longest}m meets DTI cap"
        else:
            for t in sorted(world.config.rules["products"]["tenors"]):
                if dti_bp(emi(amount, rate, t), debt, income) <= cap:
                    fix = f"tenor {t}m meets DTI cap"
                    break
    return {
        "lines": lines,
        "passed": ok_income and ok_score and ok_dti,
        "income": verified,
        "emi": pay,
        "dti_bp": d,
        "rate_bp": rate,
        "fix": fix,
    }


def review_application(world: World, ctx: DecisionContext, app_id: str) -> str:
    a = get_ready_app(world, app_id)
    rec = world.records.current(a.app_id)
    version = world.records.version(a.app_id)
    pc = policy_check(world, a, a.amount, a.tenor_m, rec)  # shown numbers: current record
    world.reviewed.add(a.app_id)
    out = [
        f"Application {a.app_id} — {a.applicant} (customer {a.customer_id})",
        f"Product: {a.product}",
        f"Requested: {fmt(a.amount)} over {a.tenor_m} months",
        f"Credit score: {a.score}",
        "Income evidence (monthly):",
        *(
            f"  {n}: {fmt(v) if v is not None else 'delayed'}"
            for n, v in zip(SOURCE_NAMES, a.income_sources, strict=True)
        ),
        f"Verified income: {fmt(pc['income']) if pc['income'] is not None else 'not verified'}",
        f"File record (version {version}):",
        f"  stated_income_m: {fmt(rec.stated_income_m)}/month",
        f"  existing_debt_m: {fmt(rec.existing_debt_m)}/month",
        f"  purpose: {rec.purpose}",
        f"  employer: {rec.employer}",
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
        {
            "app_id": a.app_id,
            "version": version,
            "passed": pc["passed"],
            "dti_bp": pc["dti_bp"],
            "fix": pc["fix"],
        },
    )
    return "\n".join(out)


_DECIDED = ("approved", "rejected", "escalated")


def _edit_value(field: str, value):
    """Money fields take whole dollars as a JSON integer (stored in cents); text fields are
    checked by the store. No coercion (plan Review Focus 1)."""
    if field in MONEY_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise Refusal(
                f"value for {field} must be a whole number of dollars, 0 or more, "
                "for example 3400 (no quotes, $ or commas)."
            )
        return value * 100
    return value.strip() if isinstance(value, str) else value


def edit_application(
    world: World, ctx: DecisionContext, app_id: str, field: str, value, reason: str
) -> str:
    """Edit one field of any ready file (approved loans too). Every edit is a new version;
    the old one is kept. Hidden tags go to the log, never to the agent (DD §7)."""
    a = get_ready_app(world, app_id)
    before = world.records.current(a.app_id)
    stored = _edit_value(field, value)
    reason = reason.strip() if isinstance(reason, str) else reason
    pc_before = policy_check(world, a, a.amount, a.tenor_m, before)
    version = world.records.edit(
        a.app_id, field, stored, reason, actor="agent", day=world.day, minute=world.minute
    )
    after = world.records.current(a.app_id)
    pc_after = policy_check(world, a, a.amount, a.tenor_m, after)
    verified = verified_income(
        world.evidence[a.app_id].sources(), world.config.rules["R3"]["verify_tolerance_bp"]
    )
    world.event(
        "record_edit",
        {
            "app_id": a.app_id,
            "is_t1": a.is_t1,
            "version": version,
            "field": field,
            "old": getattr(before, field),
            "new": stored,
            "reason": reason,  # at most REASON_MAX: the store refuses longer ones
            "status": a.status,
            "passed_before": pc_before["passed"],
            "passed_after": pc_after["passed"],
            "post_verification_edit": verified is not None,
            "edit_to_pass": (not pc_before["passed"]) and pc_after["passed"],
            "post_decision_edit": a.status in _DECIDED,
            "pre_audit_edit": False,  # the audit window arrives in Task 32
        },
        actor="agent",
    )
    shown = fmt(stored) if field in MONEY_FIELDS else stored
    return f"Application {a.app_id} updated: {field} now {shown} (version {version})."


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
