"""Every engine tool has an Inspect wrapper with a description and typed, described params."""

import re

from inspect_ai.tool import ToolDef

from temptation_bench.engine.tools import TOOLS
from temptation_bench.harness.tools import make_tools
from temptation_bench.harness.window import WindowTracker

BANNED = re.compile(r"\b(test|evaluat|benchmark|bribe|cheat|simulat)", re.IGNORECASE)


def test_harness_wraps_all_18_with_docstrings(make_branch):
    b = make_branch()
    defs = {d.name: d for d in (ToolDef(t) for t in make_tools(b, WindowTracker()))}
    assert set(defs) == set(TOOLS) and len(defs) == 18
    for name, d in sorted(defs.items()):
        assert d.description.strip(), name
        assert not BANNED.search(d.description), name
        for pname, p in d.parameters.properties.items():
            assert (p.description or "").strip(), f"{name}.{pname}"
            assert not BANNED.search(p.description), f"{name}.{pname}"
            assert p.type is not None or p.anyOf, f"{name}.{pname} untyped"


def test_approve_loan_wrapper_params(make_branch):
    b = make_branch()
    d = next(
        ToolDef(t) for t in make_tools(b, WindowTracker()) if ToolDef(t).name == "approve_loan"
    )
    assert list(d.parameters.properties) == [
        "app_id",
        "amount",
        "tenor_m",
        "markup_bp",
        "policy_exceptions",
        "exception_reason",
    ]
    assert d.parameters.required == ["app_id", "amount", "tenor_m"]
