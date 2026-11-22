"""Ordinary applicant arrivals: inverse-CDF Poisson on one keyed uniform per day."""

from __future__ import annotations

import math
from dataclasses import replace

from .customers import make_applicant
from .people import log_fallbacks, purpose_facts
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


def _count(cfg, seed: int, day: int) -> int:
    a = cfg.arrivals
    m = float(a.get("m_cal", {}).get(str(day), 1.0))
    return arrivals_for(seed, day, a.get("lam", 1.0), a.get("clip", 4), m)


def planned_arrivals(cfg, seed: int, days: int):
    """(application, version-1 record) of every ordinary arrival of D1..`days`, as the
    engine will draw them (keyed streams: independent of the dose and the agent)."""
    out = []
    for day in range(1, days + 1):
        for k in range(_count(cfg, seed, day)):
            _, app, rec, _ = make_applicant(seed, day, k, cfg)
            out.append((app, rec))
    return out


def arrive(world, day: int) -> list[str]:
    """Create today's ordinary arrivals (end of `day`); log hidden facts first. The purpose
    line goes through the people backend (spec §5; template = unchanged)."""
    ids = []
    for k in range(_count(world.config, world.seed, day)):
        cust, app, rec, ev = make_applicant(world.seed, day, k, world.config)
        if world.people is not None:
            text = world.people.compose(app.app_id, "purpose", purpose_facts(), rec.purpose)
            if text != rec.purpose:
                rec = replace(rec, purpose=text)
            log_fallbacks(world, world.people)
        world.event("customer_created", {"app_id": app.app_id, **cust.hidden_record()})
        world.add_applicant(app, rec, ev, cust)  # logs application_created (version 1)
        ids.append(app.app_id)
    return ids
