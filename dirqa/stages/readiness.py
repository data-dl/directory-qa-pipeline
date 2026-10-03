"""Stage 13 - the final readiness review, and the explicit stop before borough generation.

Every condition the directory must meet before publication is listed with a
yes/no and a detail. Blocking rule failures count against readiness unless the
business owner has explicitly accepted them, and those acceptances are written
into the manifest by name. Advisory findings are listed, not counted.

Borough generation is never run from here. It is a separate, manual phase.
"""

from __future__ import annotations

from ..backends.sqlite import q
from ..context import RunContext
from ..evidence.manifest import StageRecord


def run(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("readiness")
    cfg = ctx.config
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    counts = {table: ctx.repo.count(table) for table in cfg.tables.values()}
    check("final table counts recorded", True, "; ".join(f"{t}={n:,}" for t, n in counts.items()))

    for name in ("preflight", "backup", "transfer"):
        stage = ctx.manifest.stage(name)
        check(f"{name} completed", stage is not None and stage.status in ("completed", "skipped"),
              stage.status if stage else "not run")

    for name, summary in ctx.duplicate_summaries.items():
        unresolved = summary.get("unresolved_groups", 0)
        check(f"duplicate review {name}: no unresolved groups", unresolved == 0,
              f"{summary.get('remaining_rows', 0)} rows still returned by the official query; "
              f"{unresolved} groups need a decision")

    blocking = [r for r in ctx.rule_results if r.blocking_failure]
    unaccepted = [r for r in blocking if r.rule.id not in ctx.accepted]
    accepted = [r for r in blocking if r.rule.id in ctx.accepted]
    check("blocking checks clear or accepted", not unaccepted,
          ", ".join(f"{r.rule.id} ({r.message})" for r in unaccepted) or "clear")
    for r in accepted:
        entry = ctx.accepted[r.rule.id]
        ctx.manifest.accepted_findings.append({"rule": r.rule.id, "message": r.message, **entry})

    pharmacy = ctx.manifest.stage("pharmacy_languages")
    remaining = pharmacy.summary.get("remaining_malformed", 0) if pharmacy else None
    check("pharmacy language QA clear",
          pharmacy is not None and pharmacy.status != "failed" and not remaining,
          "not run" if pharmacy is None else f"{remaining or 0} malformed values remain")

    codes = ctx.manifest.stage("line_codes")
    codes_detail = ("not run" if codes is None else
                    f"{codes.summary.get('populated', 0)} populated; "
                    f"{codes.summary.get('needs_rule_partial_flags', 0)} need a rule")
    check("line codes populated", codes is not None and codes.status in ("completed", "skipped"), codes_detail)

    service = cfg.tables["service"]
    source_col = cfg.service_cleanup.get("source_column", "Source")
    for source in cfg.retired_sources:
        n = ctx.repo.query(f"SELECT COUNT(*) AS n FROM {q(service)} WHERE {q(source_col)} = ?", (source,))[0]["n"]
        check(f"retired source {source} absent", n == 0, f"{n} rows")

    advisory = [f"{r.rule.id}: {r.message}" for r in ctx.rule_results if r.status in ("warn", "error")
                and not r.blocking_failure]
    reminders = [r.rule.description for r in ctx.rule_results if r.status == "reminder"]

    verdict = "READY" if all(c["ok"] for c in checks) else "NOT READY"
    ctx.manifest.readiness = {"verdict": verdict, "checks": checks, "unresolved_advisory": advisory,
                              "reminders": reminders, "accepted": [a["rule"] for a in ctx.manifest.accepted_findings],
                              "final_counts": counts}
    rec.files.append(ctx.evidence.json("readiness", ctx.manifest.readiness))
    rec.summary = {"verdict": verdict, "checks": len(checks), "failing": sum(not c["ok"] for c in checks),
                   "advisory_open": len(advisory), "accepted": len(accepted)}
    rec.note("stopped before borough generation - that phase is manual by design"
             if cfg.stop_before_borough else "stop_before_borough is off in config")
    return rec
