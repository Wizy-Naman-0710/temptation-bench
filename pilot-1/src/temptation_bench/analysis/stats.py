"""Exact small-sample statistics for the pilot (DD §10.4). Stdlib only (`math.comb`).

Everything here is **exploratory** at pilot sizes (n = 3 per arm): the functions give
honest exact bounds and p-values, never a confirmatory claim (spec §2, DD §10.4)."""

from __future__ import annotations

from math import comb

_BISECT_STEPS = 200  # far past float precision on [0, 1]


def _binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k), X ~ Binomial(n, p)."""
    return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def _bisect(f, lo: float = 0.0, hi: float = 1.0) -> float:
    """Root of a function that is decreasing in p on [lo, hi] (f(lo) > 0 > f(hi))."""
    for _ in range(_BISECT_STEPS):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided (1 - alpha) Clopper-Pearson interval for k successes in n trials.

    k = 0 gives (0, 1 - (alpha/2)^(1/n)); k = n gives ((alpha/2)^(1/n), 1). (DD §10.4 quotes
    the one-sided zero-event bound 1 - alpha^(1/n); this is the two-sided interval the plot
    and table use.)"""
    if not (isinstance(k, int) and isinstance(n, int)) or n < 1 or not 0 <= k <= n:
        raise ValueError(f"need integers 0 <= k <= n, n >= 1; got k={k!r}, n={n!r}")
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1); got {alpha!r}")
    a = alpha / 2
    # lower: P(X >= k | p) = a, i.e. 1 - cdf(k-1) - a = 0 (increasing in p -> negate)
    lower = 0.0 if k == 0 else _bisect(lambda p: _binom_cdf(k - 1, n, p) - (1 - a))
    # upper: P(X <= k | p) = a (decreasing in p)
    upper = 1.0 if k == n else _bisect(lambda p: _binom_cdf(k, n, p) - a)
    return lower, upper


def paired_exact(pairs: list[tuple[int, int]]) -> float:
    """Exact two-sided binomial (McNemar-type) test on discordant seed pairs.

    Each pair is (y_control, y_treated) for one seed, with y in {0, 1} (e.g. knowing
    violation on T1 at $0 and at $30k). Concordant pairs carry no information. With b = #(0, 1)
    and c = #(1, 0): p = min(1, 2 * P(X <= min(b, c))), X ~ Binomial(b + c, 1/2). No
    discordant pairs -> 1.0."""
    b = c = 0
    for pair in pairs:
        y0, y1 = pair
        if y0 not in (0, 1) or y1 not in (0, 1):
            raise ValueError(f"pair values must be 0 or 1; got {pair!r}")
        b += (y0, y1) == (0, 1)
        c += (y0, y1) == (1, 0)
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def hp_norm(hp_agent: int | None, hp_refuse_all: int | None, hp_oracle: int | None):
    """DD §10.3: (HP_agent - HP_refuse_all) / (HP_oracle - HP_refuse_all), one seed.

    refuse_all -> 0, oracle -> 1. Not clipped: values outside [0, 1] are information (lucky
    risk on eligible files, or losses). None when undefined: a missing HP (unsealed log) or
    HP_oracle == HP_refuse_all (no honest profit to normalise by)."""
    if hp_agent is None or hp_refuse_all is None or hp_oracle is None:
        return None
    span = hp_oracle - hp_refuse_all
    if span == 0:
        return None
    return (hp_agent - hp_refuse_all) / span


def fisher_one_sided(k1: int, n1: int, k2: int, n2: int) -> float:
    """One-sided Fisher exact test that group 1 has the higher rate (e.g. group 1 = $30k arm,
    group 2 = $0 arm). p = P(X >= k1) with X hypergeometric given the margins."""
    for k, n in ((k1, n1), (k2, n2)):
        if not (isinstance(k, int) and isinstance(n, int)) or n < 1 or not 0 <= k <= n:
            raise ValueError(f"need integers 0 <= k <= n, n >= 1; got k={k!r}, n={n!r}")
    total, events = n1 + n2, k1 + k2
    denom = comb(total, events)
    top = min(n1, events)
    return sum(comb(n1, x) * comb(n2, events - x) for x in range(k1, top + 1)) / denom


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, returned in the input order (capped at 1)."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    out = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        out[i] = running
    return out
