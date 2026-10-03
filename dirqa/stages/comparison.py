"""Stage 9 - compare this month with the prior-month archive.

Totals and breakdowns by source, borough, facility type and service type, with
absolute and percentage differences. Growth is explained before it is alarming:
for each source the stage also compares rows per distinct location, so a feed
that started sending one row per service line shows up as "more rows per
location", not as thousands of new sites. Everything here is advisory.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from ..backends.sqlite import q
from ..context import RunContext
from ..evidence.manifest import StageRecord

GROWTH_FLAG_PERCENT = 25.0


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def breakdown(prior: list[dict], current: list[dict], dimension: str) -> list[dict]:
    before = Counter(r.get(dimension, "") for r in prior)
    after = Counter(r.get(dimension, "") for r in current)
    out = []
    for value in sorted(set(before) | set(after), key=str):
        p, c = before.get(value, 0), after.get(value, 0)
        out.append({"dimension": dimension, "value": value, "prior": p, "current": c,
                    "difference": c - p,
                    "percent": round((c - p) / p * 100, 1) if p else ("" if c == 0 else "new")})
    return out


def rows_per_location(rows: list[dict], key: str, source_col: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for source, group in _group_by(rows, source_col).items():
        locations = len({r.get(key) for r in group})
        out[source] = {"rows": len(group), "locations": locations,
                       "rows_per_location": round(len(group) / locations, 2) if locations else 0}
    return out


def _group_by(rows: list[dict], col: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r.get(col, ""), []).append(r)
    return out


def run(ctx: RunContext) -> StageRecord:
    rec = ctx.begin("comparison")
    cfg = ctx.config
    archive = cfg.archive_dir / cfg.prior_cycle
    plan = {
        "professional": {"dimensions": ["Source", "Borough", "Network", "ProviderType"],
                         "location_key": "AddressKey"},
        "service": {"dimensions": ["Source", "Borough", "FacilityType", "ServiceType", "Network"],
                    "location_key": "AddressKey"},
    }
    flagged: list[str] = []

    for role, settings in plan.items():
        table = cfg.tables[role]
        prior_path = archive / f"{table}.csv"
        if not prior_path.exists():
            rec.note(f"no prior-month archive for {table} at {prior_path}")
            continue
        prior = read_csv(prior_path)
        current = ctx.repo.query(f"SELECT * FROM {q(table)}")
        current = [{k: ("" if v is None else str(v)) for k, v in r.items()} for r in current]

        rows = [{"dimension": "TOTAL", "value": "", "prior": len(prior), "current": len(current),
                 "difference": len(current) - len(prior),
                 "percent": round((len(current) - len(prior)) / len(prior) * 100, 1) if prior else ""}]
        for dim in settings["dimensions"]:
            rows.extend(breakdown(prior, current, dim))
        rec.files.append(ctx.evidence.csv(f"comparison_{table}", rows,
                                          ["dimension", "value", "prior", "current", "difference", "percent"]))

        before = rows_per_location(prior, settings["location_key"], "Source")
        after = rows_per_location(current, settings["location_key"], "Source")
        density = []
        for source in sorted(set(before) | set(after)):
            b, a = before.get(source, {}), after.get(source, {})
            density.append({"source": source, "prior_rows": b.get("rows", 0), "current_rows": a.get("rows", 0),
                            "prior_locations": b.get("locations", 0), "current_locations": a.get("locations", 0),
                            "prior_rows_per_location": b.get("rows_per_location", 0),
                            "current_rows_per_location": a.get("rows_per_location", 0)})
        rec.files.append(ctx.evidence.csv(f"comparison_{table}_by_location", density))

        for d in density:
            p, c = d["prior_rows"], d["current_rows"]
            if p and (c - p) / p * 100 > GROWTH_FLAG_PERCENT:
                growth = round((c - p) / p * 100, 1)
                if d["current_rows_per_location"] > d["prior_rows_per_location"] * 1.5:
                    why = (f"rows per location rose {d['prior_rows_per_location']} -> "
                           f"{d['current_rows_per_location']}: row expansion across service lines, "
                           f"not new locations ({d['prior_locations']} -> {d['current_locations']})")
                else:
                    why = f"locations {d['prior_locations']} -> {d['current_locations']}: investigate by category"
                flagged.append(f"{table}/{d['source']}: +{growth}% ({p} -> {c}); {why}")
            elif p == 0 and c:
                flagged.append(f"{table}/{d['source']}: new source this month ({c} rows)")
        rec.summary[f"{table}_prior"] = len(prior)
        rec.summary[f"{table}_current"] = len(current)

    for note in flagged:
        rec.note(note)
    rec.summary["flagged_sources"] = len(flagged)
    return rec
