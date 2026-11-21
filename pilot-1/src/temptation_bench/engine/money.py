"""Money helpers. All engine money is `int` cents: {cents}, $1 = 100."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

Money = int  # {cents}


def cents(dollars: int | str) -> Money:
    """Convert whole dollars (int) or a decimal string like "40000.50" to {cents}.

    Floats are rejected, because they cannot hold money exactly.
    """
    if isinstance(dollars, bool) or isinstance(dollars, float):
        raise TypeError("money must be int dollars or a decimal string, not float")
    if isinstance(dollars, int):
        return dollars * 100
    if isinstance(dollars, str):
        try:
            d = Decimal(dollars.strip())
        except InvalidOperation as e:
            raise ValueError(f"not a money amount: {dollars!r}") from e
        if not d.is_finite():
            raise ValueError(f"not a money amount: {dollars!r}")
        c = d * 100
        if c != c.to_integral_value():
            raise ValueError(f"more than 2 decimal places: {dollars!r}")
        return int(c)
    raise TypeError(f"unsupported money type: {type(dollars).__name__}")


def fmt(m: Money) -> str:
    """{cents} -> "$1,234.56" (negatives "-$5.00")."""
    sign = "-" if m < 0 else ""
    a = abs(m)
    return f"{sign}${a // 100:,}.{a % 100:02d}"


def fmt_whole(m: Money) -> str:
    """{cents} -> "$30,000" (rounded down to whole dollars)."""
    sign = "-" if m < 0 else ""
    return f"{sign}${abs(m) // 100:,}"


def plain(m: Money) -> str:
    """{cents} -> "1234.56" (MIS CSV format: no $, no commas)."""
    sign = "-" if m < 0 else ""
    a = abs(m)
    return f"{sign}{a // 100}.{a % 100:02d}"
