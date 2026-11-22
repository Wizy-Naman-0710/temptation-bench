import ast
import importlib.util
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "src/temptation_bench"


def _imports(pkg, src=SRC):
    """Absolute module names imported under `src/pkg`. Relative imports are resolved
    against the file's package (F-3), and `from <pkg> import name` yields `<pkg>.name`."""
    for f in (src / pkg).rglob("*.py"):
        parts = (src.name, *f.relative_to(src).with_suffix("").parts)
        package = ".".join(parts[:-1])  # a module and an __init__ both live in their dir
        for n in ast.walk(ast.parse(f.read_text())):
            if isinstance(n, ast.Import):
                yield from (a.name for a in n.names)
            if isinstance(n, ast.ImportFrom):
                if n.level:
                    base = importlib.util.resolve_name("." * n.level + (n.module or ""), package)
                else:
                    base = n.module or ""
                yield base
                if n.module is None:
                    yield from (f"{base}.{a.name}" for a in n.names)


def _engine_violations(src=SRC):
    return {
        m
        for m in _imports("engine", src)
        if m.split(".")[0] in {"inspect_ai", "numpy"}
        or m.startswith(("temptation_bench.harness", "temptation_bench.analysis"))
    }


def test_engine_imports_no_framework():
    assert _engine_violations() == set()


def test_analysis_does_not_import_harness():
    assert not [m for m in _imports("analysis") if m.startswith("temptation_bench.harness")]


def test_relative_harness_import_in_engine_is_caught(tmp_path):
    """F-3: `from ..harness.tools import x` has module="harness.tools", level=2."""
    src = tmp_path / "temptation_bench"
    (src / "engine").mkdir(parents=True)
    (src / "engine" / "__init__.py").write_text("")
    (src / "engine" / "bad.py").write_text("from ..harness.tools import x\n")
    (src / "engine" / "bad2.py").write_text("from .. import analysis\n")
    assert _engine_violations(src) == {
        "temptation_bench.harness.tools",
        "temptation_bench.analysis",
    }
