from __future__ import annotations

from collections import deque
from typing import Any


class LocalBuffer:
    """In-memory event buffer with batch drain."""

    def __init__(self, max_size: int = 10_000) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max_size)

    def add(self, event: dict[str, Any]) -> None:
        self._events.append(event)

    def drain(self, batch_size: int) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        while self._events and len(batch) < batch_size:
            batch.append(self._events.popleft())
        return batch

    def __len__(self) -> int:
        return len(self._events)
