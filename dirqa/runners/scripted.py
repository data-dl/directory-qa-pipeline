"""The scripted runner: actions as Python callables, dialogs from a script.

Used by the tests and available to the SQLite demo. Each named action is a
function; each action may have a scripted list of dialogs that "appear" while
it runs. The runner applies the same ``DialogPolicy`` the Access runner will:
a known informational dialog is answered and recorded; anything else pauses
the action with the dialog's exact text in the result, so a person can see
what the platform asked. This is how the dialog policy is exercised without
Access being present.
"""

from __future__ import annotations

from collections.abc import Callable

from .base import ActionResult, ActionSpec, DialogEvent, DialogPolicy, DialogSpec, Runner


class ScriptedRunner(Runner):
    def __init__(self, actions: dict[str, Callable[[], object]], dialog_specs: list[DialogSpec],
                 action_specs: dict[str, ActionSpec] | None = None,
                 scripted_dialogs: dict[str, list[tuple[str, str]]] | None = None):
        self.actions = dict(actions)
        self.policy = DialogPolicy(dialog_specs)
        self.action_specs = dict(action_specs or {})
        self.scripted_dialogs = dict(scripted_dialogs or {})
        self.log: list[ActionResult] = []

    def run_action(self, name: str) -> ActionResult:
        result = ActionResult(action=name, status="completed")
        if name not in self.actions:
            result.status = "failed"
            result.notes.append(f"no action named {name!r}")
            self.log.append(result)
            return result

        # Dialogs the action raises are answered - or not - before its work counts as done.
        for title, text in self.scripted_dialogs.get(name, []):
            event: DialogEvent = self.policy.decide(title, text)
            result.dialogs.append(event)
            if event.response == "pause":
                result.status = "paused"
                what = "unexpected dialog" if event.matched is None else f"dialog {event.matched!r} needs a person"
                result.notes.append(f"{what}: [{title}] {text}")
                self.log.append(result)
                return result

        try:
            self.actions[name]()
        except Exception as exc:
            result.status = "failed"
            result.notes.append(f"{type(exc).__name__}: {exc}")
        self.log.append(result)
        return result
