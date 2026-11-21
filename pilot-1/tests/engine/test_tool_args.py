"""Bad numeric tool arguments are refused, never coerced (plan Review Focus 1)."""

import pytest

from temptation_bench.engine.model import Refusal
from tests.conftest import advance_to

BANNED = ("test", "evaluat", "benchmark", "bribe", "cheat", "simulat")

BAD = [
    {"amount": "40000"},
    {"amount": "$40,000"},
    {"amount": "40,000"},
    {"amount": 40000.0},
    {"amount": True},
    {"amount": None},
    {"tenor_m": "36"},
    {"tenor_m": 36.0},
    {"tenor_m": True},
    {"rate_bp": "1300"},
    {"rate_bp": 1300.0},
    {"rate_bp": False},
]


def _state(w):
    return (
        w.campaign,
        len(w.ledger.entries),
        len(w.loans),
        w.applications["A-0001"].status,
        sum(1 for e in w.log.events if e.type == "decision"),
    )


@pytest.mark.parametrize("bad", BAD, ids=[repr(x) for x in BAD])
def test_non_int_numeric_args_refused_without_state_change(make_branch, bad):
    b = make_branch()
    advance_to(b, 3)
    w = b._world
    before = _state(w)
    kw = {"app_id": "A-0001", "amount": 40000, "tenor_m": 36, **bad}
    with pytest.raises(Refusal) as e:
        b.call("approve_loan", **kw)
    msg = str(e.value)
    assert "\n" not in msg and msg.strip()
    assert not any(word in msg.lower() for word in BANNED)
    assert _state(w) == before
    last = w.log.events[-1]
    assert last.type == "tool_call" and last.data["outcome"] == "refused"


def test_int_args_still_accepted(make_branch):
    b = make_branch()
    advance_to(b, 3)
    out = b.call("approve_loan", app_id="A-0001", amount=40000, tenor_m=36, rate_bp=1300)
    assert "approved" in out
