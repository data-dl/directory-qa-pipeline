"""Configuration: every path, table name, query name and setting the pipeline needs.

Nothing about a particular database is hardcoded in the stages. They ask the
Config object, which was loaded from a YAML file. Swapping the file swaps the
environment: the demo SQLite databases, a test fixture, or a set of Access files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .runners.base import ActionSpec, DialogSpec


@dataclass
class TransferSpec:
    source_db: str       # key into Config.databases
    source_table: str
    target: str          # table in the repository
    mode: str = "replace"


@dataclass
class DuplicateSpec:
    """How to review one official duplicate query."""
    name: str
    query: str                         # saved-query name
    table: str
    record_id: str                     # the autonumber column (changes on every reload)
    stable_key: str | None             # the column that survives reloads; None = no safe deletes
    group_by: list[str]                # the official query's grouping fields
    compare: list[str]                 # fields that decide whether rows are the same listing
    legitimate_if_differs_in: list[str] = field(default_factory=list)
    text_fields: list[str] = field(default_factory=list)
    location_keys: list[str] = field(default_factory=list)


@dataclass
class Config:
    path: Path
    cycle: str
    prior_cycle: str
    databases: dict[str, Path]
    archive_dir: Path
    backup_dir: Path
    runs_dir: Path
    decisions_dir: Path
    queries_file: Path
    rules_file: Path
    checklist_file: Path | None
    accepted_findings_file: Path | None
    tables: dict[str, str]
    transfers: list[TransferSpec]
    duplicates: dict[str, DuplicateSpec]
    retired_sources: list[str]
    pharmacy: dict
    line_code: dict
    service_cleanup: dict
    dialogs: list[DialogSpec] = field(default_factory=list)
    actions: dict[str, ActionSpec] = field(default_factory=dict)
    backup_retention: int = 5
    working_copy_retention: int = 2
    stop_before_borough: bool = True

    @property
    def repository(self) -> Path:
        return self.databases["repository"]

    @property
    def authorization_phrase(self) -> str:
        """The exact text a person must supply to let a run change production."""
        return f"APPLY {self.cycle} TO {self.repository.name}"

    @classmethod
    def load(cls, path: str | Path) -> Config:
        path = Path(path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        base = path.parent.parent if path.parent.name == "config" else path.parent

        def p(value: str | None) -> Path | None:
            return None if value is None else (base / value)

        return cls(
            path=path,
            cycle=str(raw["cycle"]),
            prior_cycle=str(raw["prior_cycle"]),
            databases={k: p(v) for k, v in raw["databases"].items()},
            archive_dir=p(raw["archive_dir"]),
            backup_dir=p(raw["backup_dir"]),
            runs_dir=p(raw["runs_dir"]),
            decisions_dir=p(raw.get("decisions_dir", "config/decisions")),
            queries_file=p(raw.get("queries_file", "config/queries.yaml")),
            rules_file=p(raw.get("rules_file", "config/rules.yaml")),
            checklist_file=p(raw.get("checklist_file")),
            accepted_findings_file=p(raw.get("accepted_findings_file")),
            tables=dict(raw["tables"]),
            transfers=[TransferSpec(**t) for t in raw.get("transfers", [])],
            duplicates={name: DuplicateSpec(name=name, **spec)
                        for name, spec in raw.get("duplicates", {}).items()},
            retired_sources=list(raw.get("retired_sources", [])),
            pharmacy=dict(raw.get("pharmacy", {})),
            line_code=dict(raw.get("line_code", {})),
            service_cleanup=dict(raw.get("service_cleanup", {})),
            dialogs=[DialogSpec(**d) for d in raw.get("dialogs", [])],
            actions={name: ActionSpec(name=name, **spec) for name, spec in raw.get("actions", {}).items()},
            backup_retention=int(raw.get("backup_retention", 5)),
            working_copy_retention=int(raw.get("working_copy_retention", 2)),
            stop_before_borough=bool(raw.get("stop_before_borough", True)),
        )
