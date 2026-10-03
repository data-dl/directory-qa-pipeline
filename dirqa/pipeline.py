"""The stage order, and the rules for stopping.

Each stage is a function from a RunContext to a StageRecord. The first three -
preflight, backup, transfer - stop the run if they fail, because nothing after
them is trustworthy. Every other stage records its outcome and the run
continues, so one pass collects every finding. Readiness sums them up; promote
is the only stage that can touch production.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .config import Config
from .context import RunContext, start_run
from .evidence.manifest import Manifest
from .stages import (
    backup,
    comparison,
    duplicates,
    line_codes,
    pharmacy_languages,
    preflight,
    promote,
    quality_checks,
    readiness,
    service_cleanup,
    transfer,
)

STAGES = [
    ("preflight", preflight.run),
    ("backup", backup.run),
    ("transfer", transfer.run),
    ("professional_duplicates", duplicates.run_professional),
    ("service_cleanup", service_cleanup.run),
    ("service_duplicates", duplicates.run_service),
    ("line_codes", line_codes.run),
    ("pharmacy_languages", pharmacy_languages.run),
    ("quality_checks", quality_checks.run),
    ("comparison", comparison.run),
    ("readiness", readiness.run),
    ("promote", promote.run),
]
STAGE_NAMES = [name for name, _ in STAGES]
STOP_ON_FAILURE = {"preflight", "backup", "transfer"}


def run_pipeline(ctx: RunContext, only: list[str] | None = None) -> Manifest:
    selected = [(n, f) for n, f in STAGES if not only or n in only]
    try:
        for name, stage in selected:
            record = ctx.manifest.add(stage(ctx))
            if record.status == "failed" and name in STOP_ON_FAILURE:
                ctx.manifest.final_status = f"failed at {name}"
                break
        else:
            ctx.manifest.final_status = final_status(ctx.manifest)
    finally:
        ctx.close()
        ctx.manifest.write(ctx.run_dir)
    prune_working_copies(ctx.config)
    return ctx.manifest


def final_status(m: Manifest) -> str:
    if any(s.status == "failed" for s in m.stages):
        failed = next(s.name for s in m.stages if s.status == "failed")
        return f"failed at {failed}"
    promote_stage = m.stage("promote")
    verdict = m.readiness.get("verdict", "no verdict")
    if promote_stage is None:
        return f"partial run ({verdict})"
    if promote_stage.status == "completed":
        return "promoted to production"
    if promote_stage.status == "blocked":
        return f"blocked before promotion ({verdict})"
    return f"dry run ({verdict})"


def prune_working_copies(config: Config) -> int:
    """Delete the working copies of older runs (never of failed ones) to bound disk use."""
    cycle_dir = config.runs_dir / config.cycle
    if not cycle_dir.exists():
        return 0
    runs = sorted((p for p in cycle_dir.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)
    removed = 0
    for run_dir in runs[config.working_copy_retention:]:
        manifest = run_dir / "manifest.json"
        if manifest.exists() and '"final_status": "failed' in manifest.read_text(encoding="utf-8"):
            continue
        work = run_dir / "work"
        if work.exists():
            shutil.rmtree(work)
            removed += 1
    return removed


def run(config_path: str | Path, apply: bool = False, authorize: str | None = None,
        only: list[str] | None = None) -> Manifest:
    config = Config.load(config_path)
    ctx = start_run(config, apply=apply, authorize=authorize)
    return run_pipeline(ctx, only=only)
