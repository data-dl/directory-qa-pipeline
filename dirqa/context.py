"""The run context: everything a stage needs, handed to it as one object.

A run never edits the production database directly. It copies production into
the run folder, does every stage against that working copy, and only the final
``promote`` stage - in apply mode, with the authorization phrase, a verified
backup, and a READY verdict - copies the working copy back over production.
So a dry run shows the full effect of the cycle, and production changes at most
once, at the end, atomically.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .backends.base import sha256_of_file
from .backends.sqlite import SqliteBackend
from .config import Config
from .evidence.manifest import Evidence, Manifest, StageRecord
from .queries import QueryLibrary
from .rules.registry import Rule, RuleResult, load_rules
from .state import CycleState


@dataclass
class RunContext:
    config: Config
    queries: QueryLibrary
    rules: list[Rule]
    run_dir: Path
    run_stamp: str
    evidence: Evidence
    manifest: Manifest
    production: Path
    repo: SqliteBackend                 # the working copy
    sources: dict[str, SqliteBackend]
    apply: bool
    authorized: bool
    production_hash_at_start: str
    accepted: dict[str, dict] = field(default_factory=dict)
    backup_verified: bool = False
    rule_results: list[RuleResult] = field(default_factory=list)
    duplicate_summaries: dict[str, dict] = field(default_factory=dict)
    state: CycleState | None = None
    transfer_signatures: dict[str, str] = field(default_factory=dict)

    def begin(self, name: str) -> StageRecord:
        return StageRecord(name=name)

    def close(self) -> None:
        self.repo.close()
        for backend in self.sources.values():
            backend.close()


def load_accepted_findings(path: Path | None) -> dict[str, dict]:
    """Findings the business owner has explicitly accepted, keyed by rule id."""
    if path is None or not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return {entry["rule"]: dict(entry) for entry in raw}


def start_run(config: Config, apply: bool = False, authorize: str | None = None) -> RunContext:
    production = config.repository
    if not production.exists():
        raise FileNotFoundError(f"repository database not found: {production}")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = config.runs_dir / config.cycle / stamp
    (run_dir / "work").mkdir(parents=True, exist_ok=True)

    # Hash production first, then copy it: the hash is the baseline that promote
    # re-checks before it is allowed to overwrite the file.
    production_hash = sha256_of_file(production)
    work = run_dir / "work" / production.name
    shutil.copy2(production, work)

    queries = QueryLibrary.load(config.queries_file)
    rules = load_rules(config.rules_file)
    repo = SqliteBackend(work, queries)
    sources = {name: SqliteBackend(path, queries)
               for name, path in config.databases.items() if name != "repository"}

    manifest = Manifest(
        cycle=config.cycle, mode="apply" if apply else "dry-run", config=str(config.path),
        production=str(production), run_dir=str(run_dir),
        production_hash_before=production_hash, stop_before_borough=config.stop_before_borough,
    )
    return RunContext(
        config=config, queries=queries, rules=rules, run_dir=run_dir, run_stamp=stamp,
        evidence=Evidence(run_dir), manifest=manifest, production=production, repo=repo,
        sources=sources, apply=apply,
        authorized=(authorize is not None and authorize.strip() == config.authorization_phrase),
        production_hash_at_start=production_hash,
        accepted=load_accepted_findings(config.accepted_findings_file),
        state=CycleState.load(config.runs_dir, config.cycle),
    )
