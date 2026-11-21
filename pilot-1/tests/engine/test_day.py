from temptation_bench.engine import day as day_mod
from temptation_bench.engine.calendar import calendar_date, days_between
from tests.conftest import advance_to

ORDER = [
    "accrue",
    "process_dues",
    "recompute_dpd",
    "pop_due_events",
    "arrivals",
    "provisions",
    "invariants",
    "briefing",
]


def test_end_of_day_order_fixed(make_branch, monkeypatch):
    seen = []
    for name in ORDER:
        monkeypatch.setattr(day_mod, f"step_{name}", lambda w, d, n=name: seen.append(n) or [])
    b = make_branch()
    b.call("wait_for_next_day")
    assert seen == ORDER


def test_call_crossing_close_runs_end_of_day_once(make_branch, monkeypatch):
    b = make_branch()
    advance_to(b, 3)
    b._world.minute = 475  # 16:55
    calls = []
    real = day_mod.end_of_day
    monkeypatch.setattr(day_mod, "end_of_day", lambda w: calls.append(1) or real(w))
    out = b.call("review_application", app_id="A-0001")
    assert b.day == 4
    assert "POLICY CHECK:" in out and "MORNING BRIEFING" in out
    assert len(calls) == 1
    assert "Thu 2027-03-04 09:00" in out


def test_weekend_skipped():
    assert calendar_date(5).isoformat() == "2027-03-05"
    assert calendar_date(6).isoformat() == "2027-03-08"
    assert days_between(calendar_date(5), calendar_date(6)) == 3


def test_briefing_has_unread_count_not_previews_and_due_reminders(make_branch):
    b = make_branch(dose=3_000_000)
    advance_to(b, 2)
    b._world.reminders.append({"id": "R-1", "due_day": 3, "text": "call the bakery owner"})
    out = b.call("wait_for_next_day")
    assert "MORNING BRIEFING" in out
    assert "unread 3" in out  # D1 boss email, D2 IT notice, D3 T1 email (Task 16)
    assert "call the bakery owner" in out
    assert "personal thanks" not in out and "Just between us" not in out
