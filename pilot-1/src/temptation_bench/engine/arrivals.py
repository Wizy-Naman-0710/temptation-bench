"""Ordinary applicant arrivals: inverse-CDF Poisson on one keyed uniform per day."""

from __future__ import annotations

import math

from .customers import make_applicant
from .rng import rng


def arrivals_for(seed: int, day: int, lam: float = 1.0, clip: int = 4, m_cal: float = 1.0) -> int:
    """Number of ordinary arrivals on business day `day` (mean lam·m_cal, clipped)."""
    u = rng(seed, "arrivals", day).random()
    mu = lam * m_cal
    k, p = 0, math.exp(-mu)
    cdf = p
    while u > cdf and k < clip:
        k += 1
        p *= mu / k
        cdf += p
    return min(k, clip)


def arrive(world, day: int) -> list[str]:
    """Create today's ordinary arrivals (end of `day`); log hidden facts first."""
    cfg = world.config.arrivals
    m = float(cfg.get("m_cal", {}).get(str(day), 1.0))
    n = arrivals_for(world.seed, day, cfg.get("lam", 1.0), cfg.get("clip", 4), m)
    ids = []
    for k in range(n):
        cust, app, ev = make_applicant(world.seed, day, k, world.config)
        world.event("customer_created", {"app_id": app.app_id, **cust.hidden_record()})
        world.event(
            "application_created",
            {
                "app_id": app.app_id,
                "is_t1": False,
                "score": app.score,
                "amount": app.amount,
                "tenor_m": app.tenor_m,
                "debt_m": app.debt_m,
                "income_sources": app.income_sources,
            },
        )
        world.add_applicant(app, ev, cust)
        ids.append(app.app_id)
    return ids
