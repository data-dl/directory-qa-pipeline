"""Stage 2 - verified backup of production.

Taken in every mode, because a dry run should rehearse the real thing. The copy
is compared with a hash taken immediately before copying, with no handle open.
If the two do not match, nothing downstream is allowed to change production.
Old backups beyond the retention count are removed so runs do not fill the disk.
"""

from __future__ import annotations

from dataclasses import asdict

from ..backends.sqlite import SqliteBackend
from ..context import RunContext
from ..evidence.manifest import StageRecord


def run(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("backup")
    cfg = ctx.config

    production = SqliteBackend(ctx.production)
    result = production.backup(cfg.backup_dir, label=f"{cfg.cycle}_{ctx.run_stamp}")
    production.close()
    ctx.manifest.backup = asdict(result)

    if result.source_sha256 != ctx.production_hash_at_start:
        return rec.fail("production changed between the start of the run and the backup")
    if not result.verified:
        return rec.fail(f"backup did not verify: source {result.source_sha256[:12]} "
                        f"vs copy {result.backup_sha256[:12]}")
    ctx.backup_verified = True

    pattern = f"{ctx.production.stem}_*{ctx.production.suffix}"
    backups = sorted(cfg.backup_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    pruned = 0
    for old in backups[cfg.backup_retention:]:
        old.unlink()
        pruned += 1

    rec.summary = {
        "backup": result.backup, "size": result.backup_size, "verified": True,
        "retained": min(len(backups), cfg.backup_retention), "pruned": pruned,
    }
    rec.note(f"restores the state before cycle {cfg.cycle}: {result.backup}")
    return rec
