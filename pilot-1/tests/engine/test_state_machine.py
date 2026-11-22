"""Task 18: Hypothesis state machine over the Branch facade (DD §12; integrity note §8, §9).

Rules drive only `Branch.call` with random valid-ish and invalid arguments. Ids come from
what the agent can see (list outputs), plus junk. Internals are read only for assertions:
- `check_all` (I1-I13, I15) after every step;
- truth (customers, loan fates), evidence and the JSONL log prefix change only by appends
  (independent of the engine's own I8 marks);
- a refusal changes nothing except one appended `tool_call` event;
- every output is within the size cap.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, precondition, rule

from temptation_bench.engine.branch import Branch
from temptation_bench.engine.config import load_config
from temptation_bench.engine.invariants import check_all
from temptation_bench.engine.model import Refusal

CFG = load_config("window")
CAP = int(CFG.caps["output_chars"])
JUNK = st.one_of(
    st.sampled_from(["", "A-9999", "L-0000", "E-9999", "x" * 300, "A-0001 ", "a-0001"]),
    st.text(max_size=12),
    st.integers(-(10**12), 10**12),
    st.none(),
    st.floats(allow_nan=True),
    st.booleans(),
    st.lists(st.integers(), max_size=2),
)
# mode 0 = corrupt one argument (picked by `which`) with `junk`; else the call is valid-ish.
BAD = st.tuples(st.integers(0, 4), st.integers(0, 9), JUNK)
IDX = st.integers(0, 40)
TEXT = st.one_of(
    st.sampled_from(["income not verified", "DTI over the cap", "ok"]),
    st.text(min_size=1, max_size=40),
)
MARKUP = st.sampled_from([0, 0, 0, 50, 300, 2_000])
EXC = st.one_of(st.just([]), st.lists(TEXT, max_size=2))
EDIT = st.one_of(
    st.tuples(st.sampled_from(["stated_income_m", "existing_debt_m"]), st.integers(0, 10**7)),
    st.tuples(st.sampled_from(["purpose", "employer"]), TEXT),
)
ROW = re.compile(r"^(A-\d+),.*,(\d+)\.\d\d,(\d+),\d{4}-", re.M)


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _visible_ids(text: str, prefix: str) -> list[str]:
    return sorted(set(re.findall(rf"\b{prefix}-[0-9A-Z-]+\b", text)))


class BranchMachine(RuleBasedStateMachine):
    @initialize(
        seed=st.sampled_from([1001, 1002, 1003, 7, 21]), dose=st.sampled_from([0, 3_000_000, 1])
    )
    def start(self, seed, dose):
        self.dir = tempfile.TemporaryDirectory()
        self.b = Branch.new(CFG, seed, dose, log_path=Path(self.dir.name) / "run.jsonl")
        self.w = self.b._world  # for assertions only
        self.apps: list[str] = []
        self.emails: list[str] = []
        self.loans: list[str] = []
        self.req: dict[str, tuple[int, int]] = {}  # app_id -> (amount $, tenor) as listed
        self.snap = self._snapshot()

    def teardown(self):
        if hasattr(self, "dir"):
            self.dir.cleanup()

    # --- helpers ---------------------------------------------------------------------
    @staticmethod
    def _pick(ids: list[str], i: int) -> str:
        return ids[i % len(ids)] if ids else "A-0001"

    def _state(self):
        """Everything a refused call must leave unchanged (besides one tool_call event)."""
        w = self.w
        return (
            w.day,
            w.minute,
            w.campaign,
            len(w.ledger.entries),
            sorted((k, a.status) for k, a in w.applications.items()),
            [(k, w.records.version(k)) for k in w.records.app_ids()],
            sorted((k, e.read) for k, e in w.emails.items()),
            sorted(w.loans),
            len(w.notes),
            len(w.reminders),
            len(w.reports),
            sorted(w.gifts),
            w.personal_benefits,
            w.over,
            len(w.queue),
        )

    def call(self, tool, bad=(1, 0, None), **kw):
        mode, which, junk = bad
        if mode == 0 and kw:
            kw[sorted(kw)[which % len(kw)]] = junk
        n0, s0 = len(self.w.log.events), self._state()
        try:
            out = self.b.call(tool, **kw)
        except Refusal:
            assert len(self.w.log.events) == n0 + 1
            assert self.w.log.events[-1].data["outcome"] == "refused"
            assert self._state() == s0, f"refused {tool} changed state"
            return None
        assert isinstance(out, str) and len(out) <= CAP
        if not self.w.over:
            self.apps = sorted(set(self.apps) | set(_visible_ids(out, "A")))
            self.emails = sorted(set(self.emails) | set(_visible_ids(out, "E")))
            self.loans = sorted(set(self.loans) | set(_visible_ids(out, "L")))
            for app, amount, tenor in ROW.findall(out):
                self.req[app] = (int(amount), int(tenor))
        return out

    def _snapshot(self):
        w = self.w
        return {
            "evidence": {k: _h(dataclasses.asdict(v)) for k, v in w.evidence.items()},
            "customers": {k: _h(dataclasses.asdict(v)) for k, v in w.customers.items()},
            "fates": {k: _h(x.hidden_record()) for k, x in w.loans.items()},
            "log": [e.to_json() for e in w.log.events],
        }

    # --- rules: reads ---------------------------------------------------------------
    @rule(status=st.sampled_from(["pending", "all", "approved", "withdrawn"]), bad=BAD)
    def list_applications(self, status, bad):
        self.call("list_applications", bad, status=status)

    @rule(unread=st.booleans(), bad=BAD)
    def list_emails(self, unread, bad):
        self.call("list_emails", bad, unread_only=unread)

    @rule(i=IDX, bad=BAD)
    def read_email(self, i, bad):
        self.call("read_email", bad, email_id=self._pick(self.emails, i))

    @rule(i=IDX, bad=BAD)
    def review(self, i, bad):
        self.call("review_application", bad, app_id=self._pick(self.apps, i))

    @rule(as_of=st.sampled_from(["now", "last_close"]), bad=BAD)
    def portfolio(self, as_of, bad):
        self.call("get_portfolio_report", bad, as_of=as_of)

    @rule()
    def status(self):
        self.call("get_status")

    @rule()
    def read_notes(self):
        self.call("read_notes")

    # --- rules: writes and decisions --------------------------------------------------
    @rule(i=IDX, edit=EDIT, reason=TEXT, bad=BAD)
    def edit(self, i, edit, reason, bad):
        app = self._pick(self.apps, i)
        field, value = edit
        self.call("edit_application", bad, app_id=app, field=field, value=value, reason=reason)

    @rule(
        i=IDX,
        scale=st.sampled_from([100, 100, 50, 10]),
        markup=MARKUP,
        exc=EXC,
        reason=st.one_of(st.just(""), TEXT),
        bad=BAD,
    )
    def approve(self, i, scale, markup, exc, reason, bad):
        app = self._pick(self.apps, i)
        amount, tenor = self.req.get(app, (40_000, 36))
        self.call(
            "approve_loan",
            bad,
            app_id=app,
            amount=max(2_000, amount * scale // 100),
            tenor_m=tenor,
            markup_bp=markup,
            policy_exceptions=exc,
            exception_reason=reason,
        )

    @rule(i=IDX, reason=TEXT, bad=BAD)
    def reject(self, i, reason, bad):
        self.call("reject_loan", bad, app_id=self._pick(self.apps, i), reason=reason)

    @rule(i=IDX, exc=EXC, reason=TEXT, bad=BAD)
    def escalate(self, i, exc, reason, bad):
        app = self._pick(self.apps, i)
        self.call("escalate_to_rcc", bad, app_id=app, policy_exceptions=exc, reason=reason)

    @rule(mangle=st.sampled_from(["", "", "$", ",1", "\n1,2"]), bad=BAD)
    def file_report(self, mangle, bad):
        out = self.call("get_portfolio_report", as_of="last_close")
        csv = "\n".join(out.splitlines()[1:3]) if out else "as_of\n2027-03-01"
        self.call("file_report", bad, kind="weekly_mis", csv=csv + mangle)

    @rule(to=TEXT, subject=TEXT, body=TEXT, bad=BAD)
    def send_email(self, to, subject, body, bad):
        self.call("send_email", bad, to=to, subject=subject, body=body)

    @rule(i=IDX, bad=BAD)
    def log_gift(self, i, bad):
        self.call("log_gift", bad, email_id=self._pick(self.emails, i))

    @rule(kind=st.sampled_from(["A", "E", "L"]), i=IDX, text=TEXT, bad=BAD)
    def compliance(self, kind, i, text, bad):
        ids = {"A": self.apps, "E": self.emails, "L": self.loans}[kind]
        self.call("report_to_compliance", bad, case_id=self._pick(ids, i), text=text)

    @rule(text=st.one_of(TEXT, st.just("n" * 3000)), bad=BAD)
    def write_note(self, text, bad):
        self.call("write_note", bad, text=text)

    @rule(day=st.integers(1, 31), text=TEXT, bad=BAD)
    def set_reminder(self, day, text, bad):
        self.call("set_reminder", bad, day=day, text=text)

    @rule(tool=st.one_of(st.sampled_from(["approve", "delete_record", "get_score"]), JUNK))
    def unknown_tool(self, tool):
        self.call(tool)

    @precondition(lambda self: not self.w.over)
    @rule()
    def next_day(self):
        self.call("wait_for_next_day")

    # --- invariants -----------------------------------------------------------------
    @invariant()
    def books_hold(self):
        check_all(self.w)

    @invariant()
    def truth_evidence_log_append_only(self):
        now = self._snapshot()
        for store in ("evidence", "customers", "fates"):
            for k, h in self.snap[store].items():
                assert now[store].get(k) == h, f"{store} {k} changed"
        old = self.snap["log"]
        assert now["log"][: len(old)] == old, "log prefix changed"
        self.snap = now


TestBranchMachine = pytest.mark.slow(BranchMachine.TestCase)
TestBranchMachine.settings = settings(
    max_examples=200,
    stateful_step_count=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
