"""Stage 3 - controlled transfer from the source databases into the working copy.

Each transfer is declared in config with its mode. Before loading, the schemas
are compared. The transfer is skipped when a completion marker from a promoted
run says this exact source was already loaded into this exact production file,
or when the target already holds the source rows verbatim - so running twice is
harmless and never undoes cleaning. After loading, the row count must match the
source exactly or the run stops: a partial transfer is worse than none.
"""

from __future__ import annotations

from ..backends.sqlite import SchemaMismatch
from ..context import RunContext
from ..evidence.manifest import StageRecord


def run(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("transfer")
    items: list[dict] = []

    for spec in ctx.config.transfers:
        source = ctx.sources[spec.source_db]
        item = {"source": f"{spec.source_db}.{spec.source_table}", "target": spec.target,
                "mode": spec.mode, "status": "", "detail": ""}
        try:
            item["rows_before"] = ctx.repo.count(spec.target)
            item["source_rows"] = source.count(spec.source_table)
            source_sig = source.signature(spec.source_table)
            ctx.transfer_signatures[spec.target] = source_sig
            marker = ctx.state.transferred(spec.target, source_sig, ctx.production_hash_at_start)
            if spec.mode != "replace":
                item.update(status="failed", detail=f"transfer mode {spec.mode!r} is not implemented")
            elif marker:
                item.update(status="skipped", rows_after=item["rows_before"],
                            detail=f"already transferred this cycle in run {marker.get('run')} and promoted")
            elif source_sig == ctx.repo.signature(spec.target):
                item.update(status="skipped", detail="target already holds exactly the source rows",
                            rows_after=item["rows_before"])
            else:
                after = ctx.repo.replace_table_from(source, spec.source_table, spec.target)
                item["rows_after"] = after
                if after == item["source_rows"]:
                    item["status"] = "completed"
                else:
                    item.update(status="failed",
                                detail=f"partial transfer: {after} rows loaded of {item['source_rows']}")
        except SchemaMismatch as exc:
            item.update(status="failed", detail=f"schema mismatch: {exc}")
        except Exception as exc:  # any other failure is still a failed transfer, recorded
            item.update(status="failed", detail=f"{type(exc).__name__}: {exc}")
        items.append(item)

    rec.files.append(ctx.evidence.json("transfer", items))
    rec.summary = {
        "transfers": len(items),
        "completed": sum(i["status"] == "completed" for i in items),
        "skipped": sum(i["status"] == "skipped" for i in items),
        "failed": sum(i["status"] == "failed" for i in items),
        "rows_loaded": sum(i.get("rows_after", 0) for i in items if i["status"] == "completed"),
    }
    for item in items:
        if item["status"] == "failed":
            rec.note(f"{item['source']} -> {item['target']}: {item['detail']}")
    if rec.summary["failed"]:
        rec.fail("a transfer did not complete; the working copy cannot be trusted")
    elif rec.summary["completed"] == 0:
        rec.skip("every target already held its source rows")
    return rec
