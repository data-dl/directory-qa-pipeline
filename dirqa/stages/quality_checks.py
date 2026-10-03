"""Stages 8 and 12 - evaluate the rule registry and classify the checklist.

Every rule runs; every result is recorded; the rows behind every non-passing
rule are exported. A blocking failure does not stop the run here - the point
is to collect all findings in one pass - but it does make the readiness verdict
NOT READY unless the business owner has explicitly accepted it.

The informal checklist is read alongside: each note is matched to the rule it
was translated into (if any) and classified HIGH / CLEAR / REVIEW / REMINDER,
so the reader sees which notes are enforced, which are only reported, and
which have not been turned into checks at all.
"""

from __future__ import annotations

import csv

from ..context import RunContext
from ..evidence.manifest import StageRecord
from ..rules.registry import evaluate_all


def classify_note(note: str, results_by_note: dict) -> tuple[str, str, str]:
    result = results_by_note.get(note.strip())
    if result is None:
        return "REVIEW", "", "not translated into a check; needs a person"
    rule = result.rule
    if rule.severity == "reminder":
        return "REMINDER", rule.id, rule.description
    if rule.severity == "blocking":
        return ("CLEAR" if result.status == "pass" else "HIGH"), rule.id, result.message
    return "REVIEW", rule.id, f"advisory ({result.status}): {result.message}"


def run(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("quality_checks")
    results = evaluate_all(ctx.rules, ctx.repo)
    ctx.rule_results = results

    table = [{
        "rule": r.rule.id, "severity": r.rule.severity, "expect": r.rule.expect or "",
        "status": r.status, "rows": r.row_count, "message": r.message,
        "origin": r.rule.origin, "promoted_on": r.rule.promoted_on or "",
        "accepted": "yes" if r.rule.id in ctx.accepted else "",
    } for r in results]
    rec.files.append(ctx.evidence.csv("rule_results", table))
    for r in results:
        if r.rows and r.status != "pass":
            rec.files.append(ctx.evidence.csv(f"rule_{r.rule.id}", r.rows))

    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    blocking = [r for r in results if r.blocking_failure]
    unaccepted = [r for r in blocking if r.rule.id not in ctx.accepted]
    rec.summary = {"rules": len(results), **{f"status_{k}": v for k, v in sorted(counts.items())},
                   "blocking_failures": len(blocking), "unaccepted_blocking_failures": len(unaccepted)}
    for r in blocking:
        rec.note(f"BLOCKING {r.rule.id}: {r.message}" + (" (accepted)" if r.rule.id in ctx.accepted else ""))

    checklist_path = ctx.config.checklist_file
    if checklist_path and checklist_path.exists():
        by_note = {r.rule.checklist_note.strip(): r for r in results if r.rule.checklist_note}
        with checklist_path.open(encoding="utf-8", newline="") as f:
            notes = list(csv.DictReader(f))
        classified = []
        for n in notes:
            level, rule_id, detail = classify_note(n["Note"], by_note)
            classified.append({"level": level, "rule": rule_id, "note": n["Note"],
                               "added_on": n.get("AddedOn", ""), "added_by": n.get("AddedBy", ""),
                               "detail": detail})
        rec.files.append(ctx.evidence.csv("checklist_classification", classified,
                                          ["level", "rule", "note", "added_on", "added_by", "detail"]))
        levels: dict[str, int] = {}
        for c in classified:
            levels[c["level"]] = levels.get(c["level"], 0) + 1
        rec.summary.update({f"checklist_{k}": v for k, v in sorted(levels.items())})
    return rec
