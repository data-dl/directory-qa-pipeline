import pytest

from dirqa.runners.base import ActionSpec, DialogPolicy, DialogSpec
from dirqa.runners.scripted import ScriptedRunner
from dirqa.runners.watchdog import Watchdog

CLEANUP_CONFIRM = DialogSpec("cleanup_confirm", r"Microsoft Access", r"will delete \d+ records", response="ok")
REVIEW_REMINDER = DialogSpec("review_reminder", r"Reminder", r"review the CORE", response="ok")
DELETE_QUESTION = DialogSpec("delete_question", r"Microsoft Access", r"delete ALL rows", response="no",
                             informational=False)


def test_known_informational_dialog_is_answered():
    policy = DialogPolicy([CLEANUP_CONFIRM, REVIEW_REMINDER])
    event = policy.decide("Microsoft Access", "This will delete 14 records. Continue?")
    assert event.matched == "cleanup_confirm" and event.response == "ok"


def test_unknown_dialog_pauses_and_keeps_the_text():
    policy = DialogPolicy([CLEANUP_CONFIRM])
    event = policy.decide("Microsoft Access", "Could not find object 'qryOld'.")
    assert event.matched is None and event.response == "pause"
    assert event.text == "Could not find object 'qryOld'."


def test_known_but_non_informational_dialog_still_pauses():
    policy = DialogPolicy([DELETE_QUESTION])
    event = policy.decide("Microsoft Access", "This will delete ALL rows. Continue?")
    assert event.matched == "delete_question" and event.response == "pause"


def test_dialog_spec_validates_response():
    with pytest.raises(ValueError):
        DialogSpec("x", "a", "b", response="enter")


def test_scripted_runner_runs_action_and_records_dialogs():
    done = []
    runner = ScriptedRunner(
        actions={"RunServiceDirectoryCleanup": lambda: done.append(1)},
        dialog_specs=[CLEANUP_CONFIRM, REVIEW_REMINDER],
        scripted_dialogs={"RunServiceDirectoryCleanup": [
            ("Microsoft Access", "This will delete 14 records. Continue?"),
            ("Reminder", "Please review the CORE services after cleanup."),
        ]},
    )
    result = runner.run_action("RunServiceDirectoryCleanup")
    assert result.status == "completed" and done == [1]
    assert [d.matched for d in result.dialogs] == ["cleanup_confirm", "review_reminder"]


def test_scripted_runner_pauses_before_acting_on_unexpected_dialog():
    done = []
    runner = ScriptedRunner(
        actions={"PopulateLineCodes": lambda: done.append(1)},
        dialog_specs=[CLEANUP_CONFIRM],
        scripted_dialogs={"PopulateLineCodes": [("Microsoft Access", "Run-time error 3021")]},
    )
    result = runner.run_action("PopulateLineCodes")
    assert result.status == "paused" and done == []
    assert "unexpected dialog" in result.notes[0] and "3021" in result.notes[0]


def test_scripted_runner_reports_failures_and_unknown_actions():
    def boom():
        raise RuntimeError("macro failed")
    runner = ScriptedRunner(actions={"Boom": boom}, dialog_specs=[])
    assert runner.run_action("Boom").status == "failed"
    assert runner.run_action("Nope").status == "failed"


def test_watchdog_tells_slow_from_stalled():
    clock = {"t": 0.0}
    signal = {"v": 0}
    spec = ActionSpec("PopulateProfessionalLineCodes", expected_seconds=240, ceiling_seconds=900)
    dog = Watchdog(spec, [lambda: signal["v"]], clock=lambda: clock["t"])

    clock["t"] = 60
    assert dog.check() == "quiet", "no change yet, well inside the ceiling"
    clock["t"] = 300
    signal["v"] = 1
    assert dog.check() == "running", "a signal changed - it is working"
    clock["t"] = 700
    assert dog.check() == "quiet", "quiet again, but still inside the ceiling - not frozen"
    clock["t"] = 901
    assert dog.check() == "stalled", "quiet past the ceiling"
    assert dog.quiet_for() == pytest.approx(601)
    assert [s for _, s in dog.history] == ["quiet", "running", "quiet", "stalled"]


def test_watchdog_signal_errors_are_readings_not_crashes():
    def bad():
        raise OSError("file locked")
    spec = ActionSpec("x", expected_seconds=1, ceiling_seconds=10)
    dog = Watchdog(spec, [bad], clock=lambda: 0.0)
    assert dog.check() == "quiet"
    assert dog.last_values[0].startswith("error:")


def test_action_spec_validates_ceiling():
    with pytest.raises(ValueError):
        ActionSpec("x", expected_seconds=10, ceiling_seconds=5)


def test_shipped_config_declares_dialogs_and_actions():
    from pathlib import Path

    from dirqa.config import Config
    cfg = Config.load(Path(__file__).resolve().parent.parent / "config" / "demo.yaml")
    assert {d.name for d in cfg.dialogs} >= {"cleanup_confirm", "delete_all_question"}
    assert not next(d for d in cfg.dialogs if d.name == "delete_all_question").informational
    assert cfg.actions["PopulateProfessionalLineCodes"].ceiling_seconds >= 600
    policy = DialogPolicy(cfg.dialogs)
    assert policy.decide("Microsoft Access", "This will delete 27 records. Continue?").response == "ok"
    assert policy.decide("Microsoft Access", "This will delete ALL rows. Continue?").response == "pause"
