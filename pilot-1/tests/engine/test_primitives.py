import pytest

from temptation_bench.engine.eventlog import Event, EventLog
from temptation_bench.engine.money import cents, fmt, fmt_whole
from temptation_bench.engine.queue import EventQueue
from temptation_bench.engine.rng import rng


def test_cents_and_fmt():
    assert cents("40000") == 4_000_000
    assert cents("40000.50") == 4_000_050
    assert cents(40000) == 4_000_000
    assert fmt(123456) == "$1,234.56"
    assert fmt(-500) == "-$5.00"
    assert fmt_whole(3_000_000) == "$30,000"
    with pytest.raises(TypeError):
        cents(1.5)


def test_rng_is_keyed_and_stable():
    a = rng(1, "applicant", 2, 0).random()
    rng(1, "other").random()
    b = rng(1, "applicant", 2, 0).random()
    assert a == b
    assert rng(1, "applicant", 2, 1).random() != a
    assert rng(2, "applicant", 2, 0).random() != a


def test_queue_orders_by_day_priority_seq():
    q = EventQueue()
    q.push(3, 1, "c", {})
    q.push(2, 5, "b2", {})
    q.push(2, 1, "a", {})
    q.push(2, 5, "b3", {})
    assert [k for k, _ in q.pop_due(2)] == ["a", "b2", "b3"]
    assert q.pop_due(2) == []
    assert [k for k, _ in q.pop_due(5)] == ["c"]


def test_eventlog_roundtrip_and_hash_stable(tmp_path):
    log = EventLog()
    e1 = log.append("x", "engine", {"a": 1, "b": [1, 2]}, day=1, minute=0)
    log.append("y", "agent", {"z": "q"}, day=1, minute=5, visibility="agent", cause=e1.seq)
    h1 = log.write_jsonl(tmp_path / "a.jsonl")
    h2 = log.write_jsonl(tmp_path / "b.jsonl")
    assert h1 == h2
    back = EventLog.read_jsonl(tmp_path / "a.jsonl")
    assert back == log.events
    assert isinstance(back[1], Event) and back[1].cause == 0
