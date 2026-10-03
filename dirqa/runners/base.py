"""The runner interface: the interactive side of the platform.

A backend reads and writes data. A runner *runs things* - a macro, a form
button, a cleanup routine - and deals with what happens while they run: dialog
boxes that need an answer, and long stretches with no visible activity.

The design has three parts, all declared in config rather than hardcoded:

* ``DialogSpec`` - a dialog the pipeline expects, matched by title and text
  patterns, with the one response it is allowed to give. Anything that does not
  match a spec is unexpected, and the only correct reaction to an unexpected
  dialog is to pause and record it. The pipeline never sends Enter repeatedly.

* ``ActionSpec`` - how long an action normally takes and the ceiling past which
  it is considered stalled. Access can look frozen for minutes while it is
  simply busy; the ceiling is set from the routine's known runtime, not from
  impatience.

* ``Runner`` - the interface. ``ScriptedRunner`` is the implementation used by
  the tests and the SQLite demo; the Access implementation (COM to run macros,
  UI Automation to find dialogs, physical clicks as the last resort) is the
  next phase of the work.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

RESPONSES = ("ok", "yes", "no", "pause")


@dataclass
class DialogSpec:
    """A dialog the pipeline expects, and the only answer it may give."""
    name: str
    title_pattern: str
    text_pattern: str
    response: str = "ok"
    informational: bool = True     # False = the dialog asks a question a person should see

    def __post_init__(self):
        # YAML reads a bare yes/no as a boolean; accept that rather than surprise an editor.
        if isinstance(self.response, bool):
            self.response = "yes" if self.response else "no"
        if self.response not in RESPONSES:
            raise ValueError(f"dialog {self.name}: response must be one of {RESPONSES}")
        self._title = re.compile(self.title_pattern, re.IGNORECASE)
        self._text = re.compile(self.text_pattern, re.IGNORECASE | re.DOTALL)

    def matches(self, title: str, text: str) -> bool:
        return bool(self._title.search(title or "") and self._text.search(text or ""))


@dataclass
class ActionSpec:
    """Timing expectations for one interactive action."""
    name: str
    expected_seconds: float
    ceiling_seconds: float

    def __post_init__(self):
        if self.ceiling_seconds < self.expected_seconds:
            raise ValueError(f"action {self.name}: ceiling must be at least the expected time")


@dataclass
class DialogEvent:
    """A dialog that appeared while an action ran, and what was done about it."""
    title: str
    text: str
    matched: str | None = None     # DialogSpec.name, or None if unexpected
    response: str = "pause"


@dataclass
class ActionResult:
    action: str
    status: str                    # completed | paused | stalled | failed
    dialogs: list[DialogEvent] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class DialogPolicy:
    """Decide what to do about a dialog: answer a known informational one, pause otherwise."""

    def __init__(self, specs: list[DialogSpec]):
        self.specs = list(specs)

    def decide(self, title: str, text: str) -> DialogEvent:
        for spec in self.specs:
            if spec.matches(title, text):
                if spec.informational and spec.response != "pause":
                    return DialogEvent(title, text, matched=spec.name, response=spec.response)
                return DialogEvent(title, text, matched=spec.name, response="pause")
        return DialogEvent(title, text, matched=None, response="pause")


class Runner(ABC):
    """What every runner promises."""

    @abstractmethod
    def run_action(self, name: str) -> ActionResult:
        """Run a named action to completion, a pause, or a stall - never past the ceiling."""
