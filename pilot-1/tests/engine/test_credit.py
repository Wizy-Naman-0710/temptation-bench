import math
from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from temptation_bench.engine import credit as c


def _emi_float(p, rate, n):
    r = rate / 12
    return p * r * (1 + r) ** n / ((1 + r) ** n - 1)


def test_emi_matches_closed_form():
    for n in (24, 36):
        got = c.emi(1_500_000, 1200, n)
        assert abs(got - _emi_float(1_500_000, 0.12, n)) <= 1
        assert got >= _emi_float(1_500_000, 0.12, n)  # rounded up


def test_c2_illustration():
    inc, debt = 250_000, 40_000
    d24 = c.dti_bp(c.emi(1_500_000, 1200, 24), debt, inc)
    d36 = c.dti_bp(c.emi(1_500_000, 1200, 36), debt, inc)
    assert 4400 <= d24 <= 4430
    assert 3570 <= d36 <= 3600
    n = c.n_min(1_500_000, 1200, inc, debt)
    assert 24 < n <= 36


def test_n_min_none_when_emi_cap_below_interest():
    # EMI_max = 0.4*1000 - 300 = $100 <= r*P = 1% * $15,000 = $150
    assert c.n_min(1_500_000, 1200, 100_000, 30_000) is None


@settings(max_examples=60, deadline=None)
@given(st.floats(min_value=0.01, max_value=0.6), st.sampled_from(["honest", "highrisk"]))
def test_hazard_calibration_12m_cumulative_equals_pd(pd, profile):
    h = c.monthly_hazards(pd, profile, 36)
    s = 1.0
    for m in range(12):
        s *= 1 - h[m]
    assert abs((1 - s) - pd) < 1e-6
    assert all(0 <= x <= 0.95 for x in h)


@given(
    st.integers(min_value=0, max_value=10**9),
    st.integers(min_value=0, max_value=3000),
    st.lists(st.integers(min_value=1, max_value=5), min_size=1, max_size=40),
)
def test_accrue_carry_conserves_total(outstanding, rate, gaps):
    total, carry = 0, 0
    for g in gaps:
        i, carry = c.accrue(outstanding, rate, g, carry)
        total += i
    once, _ = c.accrue(outstanding, rate, sum(gaps), 0)
    assert abs(total - once) <= 1


def test_buckets_and_provisions_table():
    table = {
        0: "CURRENT",
        1: "1-30",
        30: "1-30",
        31: "31-60",
        60: "31-60",
        61: "61-90",
        90: "61-90",
        91: "NPL",
        179: "NPL",
        180: "WRITE_OFF",
    }
    for dpd, b in table.items():
        assert c.bucket(dpd) == b
    rates = [
        c.provision_rate_bp(b) for b in ["CURRENT", "1-30", "31-60", "61-90", "NPL", "WRITE_OFF"]
    ]
    assert rates == [100, 300, 1500, 1500, 5000, 10000]


def test_takeup_prob_monotone_and_one_at_zero():
    assert c.takeup_prob(0, 1100) == 1.0
    ps = [c.takeup_prob(m, 1100) for m in (50, 100, 200, 400)]
    assert all(a > b for a, b in zip(ps, ps[1:], strict=False))
    assert math.isclose(c.takeup_prob(1100, 1100), 2**-3.3)


def test_weekend_due_moves_to_next_business_day():
    assert c.next_business_day(date(2027, 3, 6)) == date(2027, 3, 8)  # Sat -> Mon
    assert c.next_business_day(date(2027, 3, 8)) == date(2027, 3, 8)
    sched = c.schedule(1_200_000, 1200, 12, date(2027, 3, 6))
    assert sched[0][0] == date(2027, 3, 8)
    assert all(d.weekday() < 5 for d, _ in sched)
    assert len(sched) == 12


def test_schedule_last_instalment_absorbs_remainder():
    rows = c.schedule_rows(1_200_000, 1200, 12, date(2027, 4, 1))
    assert sum(r.principal for r in rows) == 1_200_000
    e = c.emi(1_200_000, 1200, 12)
    assert all(r.payment == e for r in rows[:-1])


def test_default_month_and_fraud_epd():
    h = c.monthly_hazards(0.2, "honest", 36)
    assert c.default_month(h, 0.999999, False, 0.9) is None
    assert c.default_month(h, 0.0, False, 0.9) == 1
    assert c.default_month(h, 0.5, True, 0.1) == 1
    assert c.default_month(h, 0.5, True, 0.5) == 2
    assert c.default_month(h, 0.5, True, 0.7) == 3


def test_pd_scorecard_anchor():
    assert abs(c.pd_from_score(650) - 1 / 21) < 0.002
    assert (
        c.pd_true(0.05, 0.35, False, False, False, False) == 0.05
        or abs(c.pd_true(0.05, 0.35, False, False, False, False) - 0.05) < 1e-12
    )
    assert c.pd_true(0.05, 0.35, False, False, False, True) > 0.5


def test_slips():
    assert c.slip_month(0.01) and not c.slip_month(0.03)
    assert c.slip_cures(0.5, False) and not c.slip_cures(0.5, True)
