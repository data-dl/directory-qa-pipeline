"""Stage 5 - service-directory cleanup from approved lists.

Two removals, both by exact identifier and both exported before deletion:
organizations on the approved deletion list (matched on provider number), and
every row from a retired source feed (matched on the exact source value - never
on a facility type or a name pattern when a reliable Source field exists).
Counts are reconciled before and after; a second run finds nothing and skips.
"""

from __future__ import annotations

from ..backends.sqlite import q
from ..context import RunContext
from ..evidence.manifest import StageRecord


def run(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("service_cleanup")
    cfg = ctx.config
    table = cfg.tables["service"]
    deletion_list = cfg.tables["deletion_list"]
    pn = cfg.service_cleanup.get("provider_number_column", "ProviderNumber")
    source_col = cfg.service_cleanup.get("source_column", "Source")

    before = ctx.repo.count(table)
    deleted = {}

    listed = ctx.repo.query(
        f"SELECT s.* FROM {q(table)} s JOIN {q(deletion_list)} d ON d.{q(pn)} = s.{q(pn)}")
    if listed:
        rec.files.append(ctx.evidence.csv("cleanup_approved_deletions", listed))
        deleted["approved_deletions"] = ctx.repo.execute(
            f"DELETE FROM {q(table)} WHERE {q(pn)} IN (SELECT {q(pn)} FROM {q(deletion_list)})")
    else:
        deleted["approved_deletions"] = 0

    for source in cfg.retired_sources:
        rows = ctx.repo.query(f"SELECT * FROM {q(table)} WHERE {q(source_col)} = ?", (source,))
        if rows:
            rec.files.append(ctx.evidence.csv(f"cleanup_retired_source_{source}", rows))
        n = ctx.repo.execute(f"DELETE FROM {q(table)} WHERE {q(source_col)} = ?", (source,)) if rows else 0
        left = ctx.repo.query(f"SELECT COUNT(*) AS n FROM {q(table)} WHERE {q(source_col)} = ?", (source,))[0]["n"]
        deleted[f"retired_source:{source}"] = n
        if left:
            rec.fail(f"{left} rows from retired source {source!r} remain after deletion")

    after = ctx.repo.count(table)
    total = sum(deleted.values())
    rec.summary = {"rows_before": before, "rows_after": after, "deleted_total": total, **deleted}
    if before - total != after:
        rec.fail(f"reconciliation failed: {before} - {total} != {after}")
    elif total == 0:
        rec.skip("nothing on the deletion list and no retired-source rows present")
    return rec
