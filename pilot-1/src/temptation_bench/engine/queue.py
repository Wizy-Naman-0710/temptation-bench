"""Event queue: heapq ordered by (day, priority, seq)."""

from __future__ import annotations

import heapq
from typing import Any


class EventQueue:
    def __init__(self) -> None:
        self._heap: list[tuple[int, int, int, str, dict[str, Any]]] = []
        self._seq = 0

    def push(self, day: int, priority: int, kind: str, payload: dict[str, Any]) -> None:
        """Schedule `kind` for business day `day` {bday}; lower priority fires first."""
        heapq.heappush(self._heap, (day, priority, self._seq, kind, payload))
        self._seq += 1

    def pop_due(self, day: int) -> list[tuple[str, dict[str, Any]]]:
        """Pop every item with item.day <= day, in (day, priority, seq) order."""
        out = []
        while self._heap and self._heap[0][0] <= day:
            _, _, _, kind, payload = heapq.heappop(self._heap)
            out.append((kind, payload))
        return out

    def pending(self) -> list[tuple[int, int, int, str, dict[str, Any]]]:
        return sorted(self._heap)

    def __len__(self) -> int:
        return len(self._heap)
