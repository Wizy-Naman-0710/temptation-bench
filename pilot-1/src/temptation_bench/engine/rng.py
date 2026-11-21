"""Keyed RNG streams (DD §7). The only source of randomness in the engine."""

from __future__ import annotations

import random


def rng(seed: int, stream: str, *key: object) -> random.Random:
    """A fresh `random.Random` keyed by (seed, stream, key...).

    The string seed is hashed by `random` with SHA-512, so it is stable across processes
    and independent of `PYTHONHASHSEED` and of call order.
    """
    parts = [str(seed), stream, *(str(k) for k in key)]
    return random.Random("|".join(parts))
