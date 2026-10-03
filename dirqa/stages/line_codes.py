"""Stage 10 - populate the combined line code from the four coverage-line flags.

Three cases, and only one of them is the pipeline's to decide:

    all four flags present   the code is the four values concatenated
    all four flags blank     the code stays blank - that is legitimate
    some flags blank         there is no defined answer; the row is exported
                             for a business rule, and nothing is written.
                             Blanks are never turned into zeros here.

The post-update review is a grouped count of codes; it is a listing to read,
not a check expected to come back empty.
"""

from __future__ import annotations

from ..backends.sqlite import q
from ..context import RunContext
from ..evidence.manifest import StageRecord


def run(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("line_codes")
    cfg = ctx.config.line_code
    flags = cfg["flags"]
    column = cfg["column"]
    totals = {"populated": 0, "left_blank_all_flags_blank": 0, "needs_rule_partial_flags": 0}

    for entry in cfg["tables"]:
        table, record_id = entry["table"], entry["record_id"]
        cols = ", ".join(q(c) for c in [record_id, *flags])
        rows = ctx.repo.query(
            f"SELECT {cols} FROM {q(table)} WHERE {q(column)} = '' OR {q(column)} IS NULL")
        complete, partial, blank = [], [], 0
        for r in rows:
            values = ["" if r[f] is None else str(r[f]).strip() for f in flags]
            if all(v == "" for v in values):
                blank += 1
            elif any(v == "" for v in values):
                partial.append(r)
            else:
                complete.append(("".join(values), r[record_id]))
        updated = 0
        if complete:
            updated = ctx.repo.execute_many(
                f"UPDATE {q(table)} SET {q(column)} = ? WHERE {q(record_id)} = ?", complete)
        if partial:
            rec.files.append(ctx.evidence.csv(f"line_codes_{table}_needs_rule", partial))
        review = ctx.repo.query(
            f"SELECT {q(column)} AS line_code, COUNT(*) AS rows FROM {q(table)} "
            f"GROUP BY {q(column)} ORDER BY rows DESC")
        rec.files.append(ctx.evidence.csv(f"line_codes_{table}_review", review))
        rec.summary[f"{table}_populated"] = updated
        rec.summary[f"{table}_partial"] = len(partial)
        totals["populated"] += updated
        totals["left_blank_all_flags_blank"] += blank
        totals["needs_rule_partial_flags"] += len(partial)
        if updated != len(complete):
            rec.fail(f"{table}: {len(complete)} codes computed, {updated} rows updated")

    rec.summary.update(totals)
    if totals["needs_rule_partial_flags"]:
        rec.note(f"{totals['needs_rule_partial_flags']} rows have some but not all flags; "
                 "no code was written for them - they need a business rule")
    if totals["populated"] == 0 and rec.status == "completed":
        rec.skip("no rows needed a line code")
    return rec
