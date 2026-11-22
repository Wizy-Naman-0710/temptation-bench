"""Task 32 carried items: the loader's audit markers and the audit lines on graph 2."""

import matplotlib.pyplot as plt

from temptation_bench.analysis import plots
from temptation_bench.analysis.load import AUDIT_EVENT_TYPES, load_run
from temptation_bench.bots import run_bot
from temptation_bench.engine.config import load_config


def test_audit_markers_on_tool_timeline(tmp_path):
    sealed = run_bot("cheater", load_config("full"), 1001, 3_000_000, tmp_path)
    rf = load_run(sealed.path)
    assert set(AUDIT_EVENT_TYPES) == {"audit_notice", "audit_fieldwork", "audit_report"}
    audit = rf.markers[rf.markers["kind"] == "audit"]
    assert sorted(audit["detail"]) == sorted(AUDIT_EVENT_TYPES)
    fig = plots.plot_tool_timeline(rf)
    texts = {t.get_text() for t in fig.axes[0].texts}
    assert {"audit notice", "audit fieldwork", "audit findings"} <= texts
    plt.close(fig)
