"""Telling a slow process from a frozen one.

A routine that shows no window activity for four minutes may be working hard
or may be stuck. The difference is visible in side signals - the database
file's size or modification time, the process's CPU time, whether a second
connection still answers - and in how long the routine is *known* to take.

The watchdog is handed a list of signal functions and an ``ActionSpec``. Each
``check()`` reads every signal and compares with the last reading:

    running   something changed since the last check
    quiet     nothing changed, but the routine is still inside its ceiling
    stalled   nothing changed and the ceiling has passed

It never decides "frozen" before the ceiling, no matter how quiet things look,
and it never sends input to the process. The clock is injectable so the logic
can be tested without waiting.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from .base import ActionSpec

Signal = Callable[[], object]


class Watchdog:
    def __init__(self, action: ActionSpec, signals: list[Signal], clock: Callable[[], float] = time.monotonic):
        self.action = action
        self.signals = list(signals)
        self.clock = clock
        self.started = clock()
        self.last_change = self.started
        self.last_values = self._read()
        self.history: list[tuple[float, str]] = []

    def _read(self) -> list[object]:
        values = []
        for signal in self.signals:
            try:
                values.append(signal())
            except Exception as exc:  # a failing signal is information, not a crash
                values.append(f"error: {exc}")
        return values

    @property
    def elapsed(self) -> float:
        return self.clock() - self.started

    def check(self) -> str:
        now = self.clock()
        values = self._read()
        if values != self.last_values:
            self.last_values = values
            self.last_change = now
            state = "running"
        elif now - self.started <= self.action.ceiling_seconds:
            state = "quiet"
        else:
            state = "stalled"
        self.history.append((round(now - self.started, 3), state))
        return state

    def quiet_for(self) -> float:
        """Seconds since any signal last changed."""
        return self.clock() - self.last_change

    def describe(self) -> str:
        return (f"{self.action.name}: {self.elapsed:.0f}s elapsed of {self.action.ceiling_seconds:.0f}s ceiling "
                f"(expected ~{self.action.expected_seconds:.0f}s); quiet for {self.quiet_for():.0f}s")
