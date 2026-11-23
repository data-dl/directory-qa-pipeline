"""Put production back the way it was before a cycle: the reverse of promote.

Every run takes a verified backup of production and records it in its
manifest, with the hash production had at the start. Restoring uses that record
and is guarded the same way promote is:

    * dry run by default; changing production needs --apply and the exact
      restore phrase (a different phrase from the one that promotes)
    * the backup must still have the hash recorded when it was taken
    * production must still be what the promoted run left behind; if someone
      changed it since, restoring would silently throw that work away, so the
      restore stops unless --discard-later-changes is given
    * production is copied aside first, so the restore itself can be undone
    * the backup is copied to a temporary file beside production, checked, and
      swapped in with one atomic rename; the result is hashed again

The cycle's completion markers record the production hash they belong to, so
after a restore they no longer apply and the next run redoes the transfers -
which is right, because the restored file is the pre-cycle state.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .backends.base import sha256_of_file
from .config import Config

PROMOTED = "promoted to production"


class NoRestorePoint(Exception):
    pass


@dataclass
class RestorePoint:
    """One run's backup: the production file as it was when that run began."""

    run: str
    run_dir: Path
    final_status: str
    backup: Path
    backup_sha256: str          # recorded when the backup was taken
    production_before: str      # production's hash when the run began
    production_after: str       # production's hash after the run ('' if it did not promote)


@dataclass
class RestoreResult:
    status: str                 # dry-run | restored | nothing-to-do | blocked | failed
    run: str
    backup: str
    target_sha256: str
    production_sha256_before: str
    production_sha256_after: str = ""
    set_aside: str = ""
    record: str = ""
    notes: list[str] = field(default_factory=list)


def _load_point(run_dir: Path) -> RestorePoint | None:
    manifest = run_dir / "manifest.json"
    if not manifest.exists():
        return None
    m = json.loads(manifest.read_text(encoding="utf-8"))
    backup = m.get("backup") or {}
    if not backup.get("verified"):
        return None
    return RestorePoint(
        run=run_dir.name, run_dir=run_dir, final_status=m.get("final_status", ""),
        backup=Path(backup["backup"]), backup_sha256=backup["backup_sha256"],
        production_before=m.get("production_hash_before", ""),
        production_after=m.get("production_hash_after", ""))


def find_restore_point(config: Config, run: str | None = None) -> RestorePoint:
    """The named run's backup, or by default the backup taken by the latest run that promoted."""
    cycle_dir = config.runs_dir / config.cycle
    if run:
        point = _load_point(cycle_dir / run)
        if point is None:
            raise NoRestorePoint(f"run {run} in cycle {config.cycle} has no manifest with a verified backup")
        return point
    runs = sorted((p for p in cycle_dir.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True) \
        if cycle_dir.exists() else []
    for run_dir in runs:
        point = _load_point(run_dir)
        if point and point.final_status == PROMOTED:
            return point
    raise NoRestorePoint(f"no run in cycle {config.cycle} promoted to production; nothing to undo")


def restore(config: Config, run: str | None = None, apply: bool = False, authorize: str | None = None,
            discard_later_changes: bool = False) -> RestoreResult:
    point = find_restore_point(config, run)
    production = config.repository
    current = sha256_of_file(production)
    result = RestoreResult(status="dry-run", run=point.run, backup=str(point.backup),
                           target_sha256=point.production_before, production_sha256_before=current)
    note = result.notes.append

    if not point.backup.exists():
        result.status = "blocked"
        note(f"backup file is gone (removed by retention?): {point.backup}")
        return result
    backup_hash = sha256_of_file(point.backup)
    if backup_hash != point.backup_sha256 or backup_hash != point.production_before:
        result.status = "blocked"
        note(f"backup does not match the hash recorded when it was taken "
             f"({backup_hash[:12]} now, {point.backup_sha256[:12]} recorded); it will not be used")
        return result
    if current == point.production_before:
        result.status = "nothing-to-do"
        note("production already matches this backup")
        return result
    later_changes = bool(point.production_after) and current != point.production_after
    if later_changes or not point.production_after:
        why = ("production has changed since that run promoted" if later_changes
               else "that run did not promote, so production may hold later work")
        if not discard_later_changes:
            result.status = "blocked"
            note(f"{why}; restoring would discard it. Rerun with --discard-later-changes if that is intended")
            return result
        note(f"{why}; discarding it as requested (a copy is set aside first)")

    if not apply:
        note(f"production untouched. To restore: rerun with --apply --authorize \"{config.restore_phrase}\"")
        return result
    if authorize is None or authorize.strip() != config.restore_phrase:
        result.status = "blocked"
        note(f"restore phrase did not match; expected exactly: {config.restore_phrase}")
        return result

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    config.backup_dir.mkdir(parents=True, exist_ok=True)
    aside = config.backup_dir / f"{production.stem}_before-restore_{stamp}{production.suffix}"
    shutil.copy2(production, aside)
    if sha256_of_file(aside) != current:
        aside.unlink()
        result.status = "failed"
        note("could not set production aside with a matching hash; nothing was changed")
        return result
    result.set_aside = str(aside)

    temp = production.with_name(production.name + ".restoring")
    shutil.copy2(point.backup, temp)
    if sha256_of_file(temp) != point.production_before:
        temp.unlink()
        result.status = "failed"
        note("the temporary copy of the backup did not verify; production was not touched")
        return result
    os.replace(temp, production)
    after = sha256_of_file(production)
    result.production_sha256_after = after
    if after != point.production_before:
        result.status = "failed"
        note(f"production hash after the swap is {after[:12]}, not the backup's; the pre-restore copy is {aside}")
    else:
        result.status = "restored"
        note(f"production now holds the state before run {point.run}; the replaced file is kept at {aside}")

    # Kept outside the cycle folder, whose subfolders are all runs.
    record_dir = config.runs_dir / "restores"
    record_dir.mkdir(parents=True, exist_ok=True)
    record = record_dir / f"{config.cycle}_{stamp}.json"
    result.record = str(record)
    record.write_text(json.dumps({"restored_at": datetime.now(UTC).isoformat(timespec="seconds"),
                                  **asdict(result)}, indent=2), encoding="utf-8")
    return result
