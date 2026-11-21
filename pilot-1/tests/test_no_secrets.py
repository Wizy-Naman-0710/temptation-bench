import pathlib
import re

KEY = re.compile(r"xpl_[A-Za-z0-9]{16,}")  # any gateway-style key


def test_no_api_key_in_tracked_files():
    root = pathlib.Path(__file__).resolve().parents[1]
    hits = [
        p
        for p in root.rglob("*")
        if p.is_file()
        and not {".venv", ".git"} & set(p.parts)
        and p.name != ".env"
        and KEY.search(p.read_text(errors="ignore"))
    ]
    assert hits == []
