from temptation_bench.analysis.load import TOOL_KIND, load_run
from temptation_bench.analysis.plots import plot_tool_calls_per_day, save
from temptation_bench.bots import run_bot
from temptation_bench.engine.config import load_config


def test_graph1_renders_from_bot_run(tmp_path):
    sealed = run_bot("honest", load_config("window"), 1, 0, tmp_path)
    rf = load_run(sealed.path)
    assert set(rf.tool_calls.columns) >= {"seq", "day", "minute", "tool", "kind", "outcome"}
    assert set(rf.tool_calls["kind"]) <= set(TOOL_KIND.values())
    assert rf.meta["seed"] == 1 and rf.meta["dose"] == 0
    fig = plot_tool_calls_per_day(rf)
    assert len(fig.axes) >= 1
    heights = sum(p.get_height() for p in fig.axes[0].patches)
    assert heights == len(rf.tool_calls)
    paths = save(fig, tmp_path / "out", "graph1")
    assert len([p for p in paths if p.suffix in (".png", ".svg")]) == 2
    assert all(p.exists() for p in paths)
