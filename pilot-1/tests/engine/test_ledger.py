import pytest
from hypothesis import given
from hypothesis import strategies as st

from temptation_bench.bots import run_bot
from temptation_bench.engine.config import load_config
from temptation_bench.engine.invariants import InvariantError, check_ledger
from temptation_bench.engine.ledger import ACCOUNTS, CASH, LOANS, Ledger
from tests.conftest import advance_to

accounts = st.sampled_from(sorted(ACCOUNTS))
amount = st.integers(min_value=-(10**9), max_value=10**9)


@st.composite
def balanced(draw):
    lines = draw(st.lists(st.tuples(accounts, amount), min_size=1, max_size=6))
    fix = draw(accounts)
    return [*lines, (fix, -sum(a for _, a in lines))]


@given(st.lists(balanced(), max_size=20))
def test_random_balanced_postings_keep_I1_I2(postings):
    led = Ledger()
    for i, lines in enumerate(postings):
        led.post(lines, event_seq=i, memo="x")
        check_ledger(led)
    assert sum(led.balance(a) for a in ACCOUNTS) == 0


def test_unbalanced_post_rejected():
    with pytest.raises(ValueError):
        Ledger().post([(CASH, 100), (LOANS, -99)], event_seq=0, memo="x")
    with pytest.raises(ValueError):
        Ledger().post([], event_seq=0, memo="x")


def test_float_amount_rejected():
    with pytest.raises(ValueError):
        Ledger().post([(CASH, 1.5), (LOANS, -1.5)], event_seq=0, memo="x")


def test_check_ledger_detects_tampering():
    led = Ledger()
    led.post([(CASH, 5), (LOANS, -5)], event_seq=0, memo="x")
    led._balances[CASH] += 1
    with pytest.raises(InvariantError):
        check_ledger(led)


@given(st.lists(balanced(), max_size=15))
def test_ledger_replay_equals_live_balances(postings):
    led = Ledger()
    for i, lines in enumerate(postings):
        led.post(lines, event_seq=i, memo="x")
    replay = {a: 0 for a in ACCOUNTS}
    for e in led.entries:
        for acct, amt in e.lines:
            replay[acct] += amt
    assert replay == {a: led.balance(a) for a in ACCOUNTS}
    assert led.prefix_hash(len(led.entries)) == led.prefix_hash(len(led.entries))
    if led.entries:
        assert led.prefix_hash(0) != led.prefix_hash(len(led.entries))


def test_personal_benefits_never_in_ledger_I13(tmp_path):
    cfg = load_config("gfree")
    from temptation_bench.engine.branch import Branch

    b = Branch.new(cfg, 1001, 3_000_000, log_path=tmp_path / "x.jsonl")
    from temptation_bench.bots.cheater import CheaterBot

    CheaterBot().run(b)
    w = b._world
    assert w.personal_benefits == 3_000_000
    assert all(abs(amt) != 3_000_000 for e in w.ledger.entries for _, amt in e.lines)
    assert run_bot("cheater", cfg, 1001, 3_000_000, tmp_path).path.exists()


def test_approve_postcondition_cash_down_by_principal(make_branch):
    b = make_branch()
    advance_to(b, 3)
    led = b._world.ledger
    cash0, loans0 = led.balance(CASH), led.balance(LOANS)
    b.call("approve_loan", app_id="A-0001", amount=40000, tenor_m=36)
    assert led.balance(CASH) == cash0 - 4_000_000
    assert led.balance(LOANS) == loans0 + 4_000_000
