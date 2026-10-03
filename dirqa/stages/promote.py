"""Final stage - promote the working copy to production, or explain why not.

Production is overwritten only when every one of these holds:

    * the run was started with --apply
    * the exact authorization phrase was supplied
    * the backup stage verified its copy in this run
    * the readiness verdict is READY
    * production's hash is what it was when the run began

After a verified copy the cycle's completion markers are written, so the next
run knows the transfer is done and does not re-import raw rows over cleaned ones.
In a dry run the stage records what it would have done and how to do it.
"""

from __future__ import annotations

import shutil

from ..backends.base import sha256_of_file
from ..context import RunContext
from ..evidence.manifest import StageRecord


def run(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("promote")
    phrase = ctx.config.authorization_phrase
    verdict = ctx.manifest.readiness.get("verdict", "unknown")

    if not ctx.apply:
        rec.status = "dry-run"
        rec.note(f"production untouched. To promote: rerun with --apply --authorize \"{phrase}\"")
        rec.summary = {"would_promote": verdict == "READY", "readiness": verdict}
        return rec
    if not ctx.authorized:
        return rec.block(f"authorization phrase did not match; expected exactly: {phrase}")
    if not ctx.backup_verified:
        return rec.block("no verified backup in this run")
    if verdict != "READY":
        return rec.block(f"readiness verdict is {verdict}; production untouched")

    current_hash = sha256_of_file(ctx.production)
    if current_hash != ctx.production_hash_at_start:
        return rec.block("production changed while the run was in progress; someone else wrote to it")

    ctx.repo.close()
    work_hash = sha256_of_file(ctx.repo.path)
    shutil.copy2(ctx.repo.path, ctx.production)
    after = sha256_of_file(ctx.production)
    ctx.manifest.production_hash_after = after
    if after != work_hash:
        return rec.fail(f"production hash after copy ({after[:12]}) does not match the working copy "
                        f"({work_hash[:12]}); restore from {ctx.manifest.backup['backup']}")
    ctx.state.save(after, {
        target: {"source_signature": sig, "run": ctx.run_stamp, "promoted_at": rec.started}
        for target, sig in ctx.transfer_signatures.items()})
    rec.summary = {"promoted": True, "production_sha256": after,
                   "restore_from": ctx.manifest.backup["backup"] if ctx.manifest.backup else ""}
    rec.note("production now holds the working copy; the pre-cycle state is in the backup above")
    return rec
