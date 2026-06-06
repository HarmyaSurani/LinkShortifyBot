"""Lightweight in-memory runtime metrics (reset on each restart).

Cheap counters surfaced via /status — no database writes on the hot path.
"""
from __future__ import annotations

import time
from collections import deque


class _Metrics:
    def __init__(self) -> None:
        self.updates = 0
        self.commands = 0
        self.links_converted = 0
        self.errors = 0
        self._error_times: deque[float] = deque(maxlen=20000)

    def inc_update(self) -> None:
        self.updates += 1

    def inc_command(self) -> None:
        self.commands += 1

    def inc_links(self, n: int = 1) -> None:
        self.links_converted += n

    def inc_error(self) -> None:
        self.errors += 1
        self._error_times.append(time.monotonic())

    def errors_last_hour(self) -> int:
        cutoff = time.monotonic() - 3600
        while self._error_times and self._error_times[0] < cutoff:
            self._error_times.popleft()
        return len(self._error_times)


metrics = _Metrics()
