"""Stages 4 and 7 - duplicate review against the official duplicate queries.

The official query defines the candidate population; this stage never invents
its own grouping over the whole table. Each official group is first split by
the fields whose difference means "a different listing" (network, source,
service type, an identifier): rows alone in their partition are distinct
listings that happen to share the grouping fields. Every partition with more
than one row is then classified:

    exact             every compared field identical and the same stable key -
                      the same row loaded twice. Deleted automatically, keeping
                      the lowest record id, but only when the table has a stable
                      key. Name and address matching alone never deletes anything.
    likely_redundant  same location keys, only the text differs (a typo, an
                      abbreviation). A person confirms; the pipeline does not.
    review            differs in something else (an effective date, a phone).
                      Exported for a person.

Decisions people make on review groups are kept in a decision log keyed by a
hash of the group's content, so a group that comes back unchanged next month
gets the same decision applied without being re-reviewed, and a group that
changed is surfaced again.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from ..backends.sqlite import q
from ..config import DuplicateSpec
from ..context import RunContext
from ..evidence.manifest import StageRecord


@dataclass
class Group:
    group_id: str
    kind: str
    reason: str
    rows: list[dict]
    record_ids: list
    stable_keys: list
    group_hash: str = ""
    keep: object = None
    delete: list = field(default_factory=list)
    decision: str = ""


def classify(rows: list[dict], spec: DuplicateSpec) -> tuple[str, str]:
    """Return (kind, reason) for one candidate partition."""
    def same(col: str) -> bool:
        return len({r.get(col) for r in rows}) == 1

    differing = [c for c in spec.compare if not same(c)]
    if not differing and (spec.stable_key is None or same(spec.stable_key)):
        if spec.stable_key is None:
            return "exact_no_stable_key", "identical rows, but the table has no stable identifier - manual only"
        return "exact", "every compared field identical; same stable key"
    legit = [c for c in differing if c in spec.legitimate_if_differs_in]
    if legit:
        return "legitimate", "differs in " + ", ".join(legit)
    text = [c for c in spec.text_fields if not same(c)]
    if spec.location_keys and all(same(k) for k in spec.location_keys) and text:
        return "likely_redundant", ("same " + "/".join(spec.location_keys) + "; only text differs: "
                                    + ", ".join(text))
    return "review", "differs in " + ", ".join(differing)


def group_hash(rows: list[dict], spec: DuplicateSpec) -> str:
    """Content hash of a group over the grouping and compared fields, order-independent.

    Record ids are excluded because they change on every reload. Columns the
    review does not look at (a line code populated later in the run, say) are
    excluded too, so a decision keeps applying until something that matters
    about the group actually changes.
    """
    fields = sorted(set(spec.group_by + spec.compare))
    content = sorted(json.dumps({f: r.get(f) for f in fields}, sort_keys=True, default=str) for r in rows)
    return hashlib.sha256("\n".join(content).encode("utf-8")).hexdigest()[:16]


def partition(members: list[dict], spec: DuplicateSpec) -> list[list[dict]]:
    """Split an official group by the fields whose difference means a different listing."""
    keyed: dict[tuple, list[dict]] = {}
    for r in members:
        keyed.setdefault(tuple(r.get(c) for c in spec.legitimate_if_differs_in), []).append(r)
    return list(keyed.values())


def load_decisions(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {row["group_hash"]: row for row in csv.DictReader(f) if row.get("group_hash")}


def make_group(group_id: str, kind: str, reason: str, rows: list[dict], spec: DuplicateSpec) -> Group:
    return Group(
        group_id=group_id, kind=kind, reason=reason, rows=rows,
        record_ids=sorted(r[spec.record_id] for r in rows),
        stable_keys=sorted({r.get(spec.stable_key) for r in rows}) if spec.stable_key else [],
        group_hash=group_hash(rows, spec),
    )


def decide(g: Group, spec: DuplicateSpec, decisions: dict[str, dict]) -> None:
    """Exact groups delete automatically; review groups only with a logged decision."""
    if g.kind == "exact":
        g.keep = g.record_ids[0]
        g.delete = g.record_ids[1:]
    elif g.kind in ("review", "likely_redundant") and g.group_hash in decisions:
        d = decisions[g.group_hash]
        g.decision = d.get("decision", "")
        if g.decision == "delete":
            keep_key = d.get("keep_stable_key") or ""
            keepers = [r for r in g.rows if str(r.get(spec.stable_key)) == keep_key] if keep_key else []
            g.keep = keepers[0][spec.record_id] if keepers else g.record_ids[0]
            g.delete = [rid for rid in g.record_ids if rid != g.keep]
        # "exception" and "keep" leave the rows alone; the decision is recorded.


def review(ctx: RunContext, spec: DuplicateSpec, rec: StageRecord) -> dict:
    rows = ctx.repo.run_saved_query(spec.query)
    decisions = load_decisions(ctx.config.decisions_dir / f"{spec.name}.csv")

    buckets: dict[tuple, list[dict]] = {}
    for r in rows:
        buckets.setdefault(tuple(r.get(c) for c in spec.group_by), []).append(r)

    groups: list[Group] = []
    for i, (_, members) in enumerate(sorted(buckets.items(), key=lambda kv: str(kv[0])), 1):
        parts = partition(members, spec)
        candidates = [p for p in parts if len(p) > 1]
        if not candidates:
            differing = [c for c in spec.legitimate_if_differs_in if len({r.get(c) for r in members}) > 1]
            groups.append(make_group(f"{spec.name}-{i:05d}", "legitimate",
                                     "distinct listings; differ in " + ", ".join(differing), members, spec))
            continue
        for j, part in enumerate(candidates):
            kind, reason = classify(part, spec)
            if len(parts) > 1:
                reason += f"; {len(members) - len(part)} other rows in this official group are distinct listings"
            suffix = f"-{chr(97 + j)}" if len(candidates) > 1 else ""
            g = make_group(f"{spec.name}-{i:05d}{suffix}", kind, reason, part, spec)
            decide(g, spec, decisions)
            groups.append(g)

    # Evidence: every candidate row with its group and class, and one line per group.
    row_columns = (["group_id", "kind", "group_hash"] + list(rows[0].keys())) if rows else None
    rec.files.append(ctx.evidence.csv(f"duplicates_{spec.name}_rows", [
        {"group_id": g.group_id, "kind": g.kind, "group_hash": g.group_hash, **r}
        for g in groups for r in g.rows], row_columns))
    rec.files.append(ctx.evidence.csv(f"duplicates_{spec.name}_groups", [{
        "group_id": g.group_id, "kind": g.kind, "reason": g.reason, "group_hash": g.group_hash,
        "rows": len(g.rows), "record_ids": " ".join(map(str, g.record_ids)),
        "stable_keys": " ".join(map(str, g.stable_keys)),
        "keep": g.keep if g.keep is not None else "", "delete": " ".join(map(str, g.delete)),
        "decision": g.decision,
        "sample": " | ".join(str(g.rows[0].get(c, "")) for c in spec.group_by[:4]),
    } for g in groups], ["group_id", "kind", "reason", "group_hash", "rows", "record_ids", "stable_keys",
                         "keep", "delete", "decision", "sample"]))

    to_delete = [rid for g in groups for rid in g.delete]
    deleted = 0
    for start in range(0, len(to_delete), 500):
        chunk = to_delete[start:start + 500]
        marks = ",".join("?" for _ in chunk)
        deleted += ctx.repo.execute(
            f"DELETE FROM {q(spec.table)} WHERE {q(spec.record_id)} IN ({marks})", chunk)
    remaining_rows = ctx.repo.run_saved_query(spec.query)

    kinds: dict[str, int] = {}
    for g in groups:
        kinds[g.kind] = kinds.get(g.kind, 0) + 1
    unresolved = [g for g in groups if g.kind in ("review", "likely_redundant", "exact_no_stable_key")
                  and g.decision not in ("delete", "exception", "keep")]
    summary = {
        "candidate_rows": len(rows), "groups": len(groups),
        **{f"groups_{k}": v for k, v in sorted(kinds.items())},
        "decided_from_log": sum(1 for g in groups if g.decision),
        "deleted": deleted, "remaining_rows": len(remaining_rows), "unresolved_groups": len(unresolved),
    }
    if deleted != len(to_delete):
        rec.fail(f"{spec.name}: planned {len(to_delete)} deletions, database reports {deleted}")
    return summary


def run_professional(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("professional_duplicates")
    spec = ctx.config.duplicates["professional"]
    summary = review(ctx, spec, rec)
    ctx.duplicate_summaries[spec.name] = summary
    rec.summary = summary
    if summary["candidate_rows"] == 0:
        rec.skip("official duplicate query returned no rows")
    return rec


def run_service(ctx: RunContext) -> StageRecord:
    """Address duplicates first, then phone duplicates on what remains."""
    rec = ctx.begin("service_duplicates")
    total = {"deleted": 0, "unresolved_groups": 0}
    for name in ("service_address", "service_phone"):
        spec = ctx.config.duplicates[name]
        summary = review(ctx, spec, rec)
        ctx.duplicate_summaries[name] = summary
        rec.summary.update({f"{name}_{k}": v for k, v in summary.items()
                            if k in ("candidate_rows", "groups", "deleted", "remaining_rows", "unresolved_groups")})
        total["deleted"] += summary["deleted"]
        total["unresolved_groups"] += summary["unresolved_groups"]
    rec.summary.update(total)
    rec.note("phone duplicates were reviewed after address deletions, so their count already "
             "excludes rows the address step removed")
    return rec
