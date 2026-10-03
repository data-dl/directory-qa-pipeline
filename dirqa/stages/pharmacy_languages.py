"""Stage 11 - normalize malformed comma-delimited language lists.

The rule is deliberately simple and deliberately not clever: split at commas,
trim each piece, drop the empty pieces, keep every non-empty piece in its
original order, and rejoin with a comma and one space. Nothing is cut by a
fixed number of characters, no repeated replacements that could eat part of a
language name, no assumption that every bad value has the same spacing.

Evidence is the old and new value for every changed row, and the QA query is
rerun afterwards: the expected result is zero malformed values.
"""

from __future__ import annotations

from ..backends.sqlite import q
from ..context import RunContext
from ..evidence.manifest import StageRecord


def normalize(value: str | None) -> str:
    if value is None:
        return ""
    return ", ".join(part.strip() for part in str(value).split(",") if part.strip())


def run(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("pharmacy_languages")
    cfg = ctx.config.pharmacy
    table, record_id, column, query = cfg["table"], cfg["record_id"], cfg["column"], cfg["query"]

    malformed = ctx.repo.run_saved_query(query)
    if not malformed:
        return rec.skip("the malformed-language query is already clear")

    changes = []
    for r in malformed:
        new = normalize(r[column])
        changes.append({"record_id": r[record_id], "old": r[column], "new": new,
                        "became_blank": new == ""})
    rec.files.append(ctx.evidence.csv("pharmacy_language_changes", changes,
                                      ["record_id", "old", "new", "became_blank"]))
    updated = ctx.repo.execute_many(
        f"UPDATE {q(table)} SET {q(column)} = ? WHERE {q(record_id)} = ?",
        [(c["new"], c["record_id"]) for c in changes])
    remaining = len(ctx.repo.run_saved_query(query))

    rec.summary = {
        "malformed_found": len(malformed), "changed": updated,
        "became_blank": sum(c["became_blank"] for c in changes), "remaining_malformed": remaining,
    }
    if updated != len(changes):
        rec.fail(f"{len(changes)} changes planned, {updated} rows updated")
    elif remaining:
        rec.note(f"{remaining} values still match the malformed-language query after normalization")
    return rec
