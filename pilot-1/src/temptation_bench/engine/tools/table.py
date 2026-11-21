"""CSV output helpers shared by the list and report tools (DD §8, §13A size caps)."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from ..model import Refusal


def csv_lines(rows: Sequence[Sequence[object]]) -> list[str]:
    """Rows -> CSV lines (quoted only where a field needs it)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerows(rows)
    return buf.getvalue().splitlines()


def capped_csv(header: str, rows: Sequence[Sequence[object]], cap: int) -> str:
    """Header + at most `cap` rows, then `+N more` (plan Global Constraints)."""
    out = [header, *csv_lines(rows[:cap])]
    if len(rows) > cap:
        out.append(f"+{len(rows) - cap} more")
    return "\n".join(out)


def check_bool(name: str, v) -> bool:
    if not isinstance(v, bool):
        raise Refusal(f"{name} must be true or false.")
    return v


def check_text(name: str, v, max_len: int) -> str:
    """A non-empty string of at most `max_len` characters after stripping, or a Refusal."""
    if not isinstance(v, str) or not v.strip():
        raise Refusal(f"{name} must be non-empty text.")
    v = v.strip()
    if len(v) > max_len:
        raise Refusal(f"{name} must be at most {max_len:,} characters.")
    return v
