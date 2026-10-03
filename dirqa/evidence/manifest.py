"""What every run leaves behind.

One folder per run holds a machine-readable manifest, a human-readable summary,
and a CSV for every finding. The manifest is the audit trail: what was
attempted, what completed, what was skipped and why, every count before and
after, the backup that restores the prior state, and the final verdict.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

STATUSES = ("completed", "skipped", "dry-run", "blocked", "failed")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class StageRecord:
    name: str
    status: str = "completed"
    started: str = field(default_factory=now)
    finished: str = ""
    summary: dict = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def note(self, text: str) -> None:
        self.notes.append(text)

    def fail(self, text: str) -> StageRecord:
        self.status = "failed"
        self.notes.append(text)
        return self

    def block(self, text: str) -> StageRecord:
        self.status = "blocked"
        self.notes.append(text)
        return self

    def skip(self, text: str) -> StageRecord:
        self.status = "skipped"
        self.notes.append(text)
        return self

    def finish(self) -> StageRecord:
        self.finished = now()
        return self


class Evidence:
    """Writes CSV / JSON evidence files into the run folder and remembers their names."""

    def __init__(self, run_dir: Path):
        self.dir = run_dir / "evidence"
        self.dir.mkdir(parents=True, exist_ok=True)

    def csv(self, name: str, rows: Iterable[dict], columns: list[str] | None = None) -> str:
        rows = list(rows)
        if columns is None:
            columns = list(rows[0].keys()) if rows else []
        path = self.dir / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        return str(path.relative_to(self.dir.parent))

    def json(self, name: str, data) -> str:
        path = self.dir / f"{name}.json"
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return str(path.relative_to(self.dir.parent))


@dataclass
class Manifest:
    cycle: str
    mode: str                     # "dry-run" or "apply"
    config: str
    production: str
    run_dir: str
    started: str = field(default_factory=now)
    finished: str = ""
    production_hash_before: str = ""
    production_hash_after: str = ""
    backup: dict | None = None
    stages: list[StageRecord] = field(default_factory=list)
    accepted_findings: list[dict] = field(default_factory=list)
    readiness: dict = field(default_factory=dict)
    final_status: str = "incomplete"
    stop_before_borough: bool = True

    def add(self, record: StageRecord) -> StageRecord:
        self.stages.append(record.finish())
        return record

    def stage(self, name: str) -> StageRecord | None:
        return next((s for s in self.stages if s.name == name), None)

    def to_dict(self) -> dict:
        return asdict(self)

    def write(self, run_dir: Path) -> None:
        self.finished = now()
        (run_dir / "manifest.json").write_text(json.dumps(self.to_dict(), indent=2, default=str),
                                               encoding="utf-8")
        (run_dir / "summary.md").write_text(render_summary(self), encoding="utf-8")


def render_summary(m: Manifest) -> str:
    lines = [f"# Run summary - cycle {m.cycle} ({m.mode})", ""]
    before, after = m.production_hash_before[:12], m.production_hash_after[:12] or "-"
    lines += [f"- Started: {m.started}", f"- Finished: {m.finished}", f"- Production: `{m.production}`",
              f"- Production hash before / after: `{before}` / `{after}`",
              f"- Final status: **{m.final_status}**", ""]
    if m.backup:
        lines += ["## Backup", "", f"- `{m.backup['backup']}`",
                  f"- verified: {m.backup['verified']}  (sha256 `{m.backup['backup_sha256'][:12]}`)", ""]
    lines += ["## Stages", "", "| stage | status | summary |", "|---|---|---|"]
    for s in m.stages:
        summary = "; ".join(f"{k}={v}" for k, v in s.summary.items()
                            if not isinstance(v, (list, dict)))
        lines.append(f"| {s.name} | {s.status} | {summary} |")
    lines.append("")
    notes = [(s.name, n) for s in m.stages for n in s.notes]
    if notes:
        lines += ["## Notes", ""] + [f"- **{name}**: {n}" for name, n in notes] + [""]
    if m.readiness:
        lines += ["## Readiness", "", f"**{m.readiness.get('verdict', '?')}**", ""]
        for item in m.readiness.get("checks", []):
            mark = "x" if item["ok"] else " "
            lines.append(f"- [{mark}] {item['check']}: {item['detail']}")
        lines.append("")
    if m.accepted_findings:
        lines += ["## Accepted findings", ""] + [
            f"- {a['rule']}: accepted by {a.get('accepted_by', '?')} on {a.get('accepted_on', '?')}"
            f" - {a.get('reason', '')}"
            for a in m.accepted_findings] + [""]
    files = [f for s in m.stages for f in s.files]
    if files:
        lines += ["## Evidence files", ""] + [f"- `{f}`" for f in files] + [""]
    if m.stop_before_borough:
        lines += ["---", "Borough generation was **not** run. It is a separate, manual phase.", ""]
    return "\n".join(lines)
