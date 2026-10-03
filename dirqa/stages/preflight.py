"""Stage 1 - preflight: look before touching anything.

Confirms every database and every expected object exists, notes lock files,
records sizes, modification times, hashes and row counts, and writes a preflight
report. Stops the run if anything expected is missing.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..backends.base import sha256_of_file
from ..context import RunContext
from ..evidence.manifest import StageRecord


def run(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("preflight")
    cfg = ctx.config
    problems: list[str] = []

    missing = [f"{name} -> {path}" for name, path in cfg.databases.items() if not path.exists()]
    if missing:
        return rec.fail("database missing: " + "; ".join(missing))

    for name, path in cfg.databases.items():
        for lock in (path.with_suffix(".laccdb"), path.with_name(path.name + "-journal"),
                     path.with_name(path.name + "-wal")):
            if lock.exists():
                rec.note(f"lock file present beside {name}: {lock.name} - another session may have it open")

    inventory: dict[str, dict] = {}
    backends = {"repository": ctx.repo, **ctx.sources}
    for name, backend in backends.items():
        path = cfg.databases[name]
        stat = path.stat()
        inventory[name] = {
            "path": str(path),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(timespec="seconds"),
            "sha256": ctx.production_hash_at_start if name == "repository" else sha256_of_file(path),
            "tables": {table: backend.count(table) for table in backend.tables()},
        }

    repo_tables = inventory["repository"]["tables"]
    for role, table in cfg.tables.items():
        if table not in repo_tables:
            problems.append(f"repository table missing: {table} ({role})")
    for t in cfg.transfers:
        if t.source_table not in inventory.get(t.source_db, {}).get("tables", {}):
            problems.append(f"source table missing: {t.source_db}.{t.source_table}")
        if t.target not in repo_tables:
            problems.append(f"transfer target missing: {t.target}")
    wanted_queries = {r.query for r in ctx.rules if r.query}
    wanted_queries |= {d.query for d in cfg.duplicates.values()}
    if cfg.pharmacy.get("query"):
        wanted_queries.add(cfg.pharmacy["query"])
    for name in sorted(wanted_queries):
        if name not in ctx.queries:
            problems.append(f"saved query missing: {name}")

    rec.files.append(ctx.evidence.json("preflight", {"inventory": inventory, "problems": problems}))
    rec.summary = {
        "databases": len(inventory),
        "repository_tables": len(repo_tables),
        "repository_rows": sum(repo_tables.values()),
        "saved_queries": len(ctx.queries.names()),
        "rules": len(ctx.rules),
        "problems": len(problems),
    }
    if problems:
        rec.fail("expected objects missing: " + "; ".join(problems))
    return rec
