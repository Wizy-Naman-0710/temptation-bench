import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "src/temptation_bench"


def _imports(pkg):
    for f in (SRC / pkg).rglob("*.py"):
        for n in ast.walk(ast.parse(f.read_text())):
            if isinstance(n, ast.Import):
                yield from (a.name for a in n.names)
            if isinstance(n, ast.ImportFrom) and n.module:
                yield n.module


def test_engine_imports_no_framework():
    bad = {
        m
        for m in _imports("engine")
        if m.split(".")[0] in {"inspect_ai", "numpy"}
        or m.startswith(("temptation_bench.harness", "temptation_bench.analysis"))
    }
    assert bad == set()


def test_analysis_does_not_import_harness():
    assert not [m for m in _imports("analysis") if m.startswith("temptation_bench.harness")]
