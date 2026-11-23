"""End to end on a small generated dataset, graded against the answer key.

Three runs on the same environment: a dry run (production untouched, every
planted exact duplicate removed from the working copy and nothing else), an
apply run that is blocked because the directory is NOT READY, and an apply run
with logged decisions and accepted findings that promotes - after which a
further dry run finds nothing left to do.
"""

import csv
import json
import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml

from dirqa.backends.base import sha256_of_file
from dirqa.config import Config
from dirqa.context import start_run
from dirqa.pipeline import run
from dirqa.restore import find_restore_point, restore
from synth.generate import generate

ROOT = Path(__file__).resolve().parent.parent
SCALE = 0.05


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    base = tmp_path_factory.mktemp("env")
    generate(base / "demo", scale=SCALE, quiet=True)
    raw = yaml.safe_load((ROOT / "config" / "demo.yaml").read_text(encoding="utf-8"))
    raw["queries_file"] = str(ROOT / "config" / "queries.yaml")
    raw["rules_file"] = str(ROOT / "config" / "rules.yaml")
    raw["decisions_dir"] = "config/decisions"
    raw["accepted_findings_file"] = "config/accepted_findings.yaml"
    (base / "config").mkdir()
    config_path = base / "config" / "test.yaml"
    config_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return {"base": base, "config": config_path, "production": base / "demo" / "DirectoryQualityHub.sqlite",
            "key": json.loads((base / "demo" / "answer_key.json").read_text(encoding="utf-8"))}


def stages(manifest):
    return {s.name: s for s in manifest.stages}


def ids_present(db: Path, table: str, column: str) -> set:
    con = sqlite3.connect(db)
    try:
        return {r[0] for r in con.execute(f'SELECT "{column}" FROM "{table}"')}
    finally:
        con.close()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------

def test_dry_run_changes_working_copy_not_production(env):
    before = sha256_of_file(env["production"])
    m = run(env["config"])
    assert m.mode == "dry-run"
    assert sha256_of_file(env["production"]) == before
    assert m.final_status == "dry run (NOT READY)"
    st = stages(m)
    assert {s.status for s in m.stages} <= {"completed", "dry-run", "skipped"}
    assert st["promote"].status == "dry-run"
    assert st["backup"].summary["verified"] is True
    assert Path(m.run_dir, "manifest.json").exists() and Path(m.run_dir, "summary.md").exists()
    env["dry_run"] = m


def test_transfer_loaded_every_source_row(env):
    m = env["dry_run"]
    key = env["key"]
    st = stages(m)
    assert st["transfer"].summary["failed"] == 0 and st["transfer"].summary["completed"] == 4
    items = json.loads(Path(m.run_dir, "evidence", "transfer.json").read_text())
    loaded = {i["target"]: i["rows_after"] for i in items}
    assert loaded["ProfessionalDirectory"] == key["counts"]["current_source"]["ProfessionalProviderSource"]
    assert loaded["ServiceDirectory"] == key["counts"]["current_source"]["AdditionalServiceSource"]


def test_duplicates_graded_against_answer_key(env):
    m = env["dry_run"]
    key = env["key"]
    work = Path(m.run_dir) / "work" / "DirectoryQualityHub.sqlite"
    gone_by_cleanup = ({rid for g in key["defects"]["approved_deletion"] for rid in g["record_ids"]}
                       | {e["record_id"] for e in key["defects"]["retired_source"]})
    for table, hub, column in (("ProfessionalProviderSource", "ProfessionalDirectory", "ProviderRecordID"),
                               ("AdditionalServiceSource", "ServiceDirectory", "VendorRecordID")):
        present = ids_present(work, hub, column)
        exact = [g for g in key["defects"]["exact_duplicate"] if g["table"] == table]
        copies = [rid for g in exact for rid in g["record_ids"] if rid != g["keep_record_id"]]
        keeps = [g["keep_record_id"] for g in exact]
        keep_kinds = ("legitimate_multiple", "review_duplicate", "phone_duplicate_redundant",
                      "phone_duplicate_legitimate")
        untouched = [rid for kind in keep_kinds for g in key["defects"].get(kind, [])
                     if g["table"] == table for rid in g["record_ids"] if rid not in gone_by_cleanup]
        assert exact and all(rid not in present for rid in copies), f"{table}: a planted copy survived"
        assert all(rid in present for rid in keeps), f"{table}: an original was deleted"
        assert all(rid in present for rid in untouched), f"{table}: a non-exact row was deleted"


def test_redundant_phone_pairs_are_surfaced_not_deleted(env):
    m = env["dry_run"]
    key = env["key"]
    groups = read_csv(Path(m.run_dir) / "evidence" / "duplicates_service_phone_groups.csv")
    flagged = {int(x) for g in groups if g["kind"] == "likely_redundant" for x in g["record_ids"].split()}
    gone = {rid for g in key["defects"]["approved_deletion"] for rid in g["record_ids"]}
    planted = [g for g in key["defects"]["phone_duplicate_redundant"] if not set(g["record_ids"]) & gone]
    assert planted and all(set(g["record_ids"]) & flagged for g in planted)
    assert all(g["delete"] == "" for g in groups if g["kind"] != "exact")


def test_cleanup_pharmacy_and_line_codes(env):
    m = env["dry_run"]
    key = env["key"]
    st = stages(m)
    assert st["service_cleanup"].summary["retired_source:LegacyVendorFeed"] == key["facts"]["retired_source"]["rows"]
    assert st["service_cleanup"].summary["approved_deletions"] == sum(
        len(g["record_ids"]) for g in key["defects"]["approved_deletion"])
    assert st["pharmacy_languages"].summary["changed"] == len(key["defects"]["malformed_languages"])
    assert st["pharmacy_languages"].summary["remaining_malformed"] == 0
    assert st["pharmacy_languages"].summary["became_blank"] == sum(
        e["comma_only"] for e in key["defects"]["malformed_languages"])
    planted_partial = sum(1 for e in key["defects"]["partial_flags"] if e["table"] == "ProfessionalProviderSource")
    assert st["line_codes"].summary["ProfessionalDirectory_partial"] == planted_partial
    assert st["line_codes"].summary["populated"] > 0


def test_quality_checks_find_the_planted_failures(env):
    m = env["dry_run"]
    results = {r["rule"]: r for r in read_csv(Path(m.run_dir) / "evidence" / "rule_results.csv")}
    assert results["vision_island_presence"]["status"] == "fail"
    assert results["named_exclusion_present"]["status"] == "fail" and results["named_exclusion_present"]["rows"] == "2"
    assert results["malformed_languages"]["status"] == "pass", "fixed earlier in the same run"
    assert results["retired_source_present"]["status"] == "pass"
    assert results["named_org_nonzero_lines"]["status"] == "warn"
    assert results["flu_clinic_listings_next_cycle"]["status"] == "reminder"
    checklist = read_csv(Path(m.run_dir) / "evidence" / "checklist_classification.csv")
    assert {c["level"] for c in checklist} >= {"HIGH", "REVIEW", "REMINDER"}


def test_comparison_explains_growth_as_row_expansion(env):
    m = env["dry_run"]
    notes = stages(m)["comparison"].notes
    assert any("CommunityCareFeed" in n and "row expansion" in n for n in notes)


def test_apply_is_blocked_while_not_ready(env):
    before = sha256_of_file(env["production"])
    phrase = Config.load(env["config"]).authorization_phrase
    m = run(env["config"], apply=True, authorize=phrase)
    assert stages(m)["promote"].status == "blocked"
    assert m.final_status.startswith("blocked before promotion")
    assert sha256_of_file(env["production"]) == before
    m2 = run(env["config"], apply=True, authorize="wrong phrase", only=["preflight", "backup", "readiness", "promote"])
    assert stages(m2)["promote"].status == "blocked"
    assert "authorization" in stages(m2)["promote"].notes[0]


def test_apply_promotes_with_decisions_and_acceptances(env):
    base = env["base"]
    m0 = env["dry_run"]
    decisions_dir = base / "config" / "decisions"
    decisions_dir.mkdir(exist_ok=True)
    for name in ("professional", "service_address", "service_phone"):
        groups = read_csv(Path(m0.run_dir) / "evidence" / f"duplicates_{name}_groups.csv")
        with (decisions_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["group_hash", "decision", "keep_stable_key",
                                              "decided_by", "decided_on", "note"])
            w.writeheader()
            for g in groups:
                if g["kind"] in ("review", "likely_redundant"):
                    w.writerow({"group_hash": g["group_hash"], "decision": "exception", "keep_stable_key": "",
                                "decided_by": "tester", "decided_on": "2026-09-13", "note": "test"})
    failing = [r["rule"] for r in read_csv(Path(m0.run_dir) / "evidence" / "rule_results.csv")
               if r["status"] in ("fail", "error") and r["severity"] == "blocking"]
    (base / "config" / "accepted_findings.yaml").write_text(yaml.safe_dump([
        {"rule": r, "accepted_by": "tester", "accepted_on": "2026-09-13", "reason": "test acceptance"}
        for r in failing]), encoding="utf-8")

    phrase = Config.load(env["config"]).authorization_phrase
    m = run(env["config"], apply=True, authorize=phrase)
    st = stages(m)
    assert m.readiness["verdict"] == "READY", m.readiness["checks"]
    assert st["professional_duplicates"].summary["decided_from_log"] > 0
    assert len(m.accepted_findings) == len(failing)
    assert st["promote"].status == "completed"
    assert m.final_status == "promoted to production"
    work_hash = sha256_of_file(Path(m.run_dir) / "work" / "DirectoryQualityHub.sqlite")
    assert sha256_of_file(env["production"]) == work_hash == m.production_hash_after
    assert Path(m.backup["backup"]).exists()


def test_second_run_finds_nothing_left_to_do(env):
    m = run(env["config"])
    st = stages(m)
    assert st["transfer"].status == "skipped"
    assert st["service_cleanup"].status == "skipped"
    assert st["pharmacy_languages"].status == "skipped"
    assert st["line_codes"].status == "skipped"
    assert st["professional_duplicates"].summary["deleted"] == 0
    assert st["service_duplicates"].summary["deleted"] == 0
    assert m.readiness["verdict"] == "READY"


def test_runs_started_in_the_same_second_get_their_own_folders(env):
    config = Config.load(env["config"])
    a, b = start_run(config), start_run(config)
    try:
        assert a.run_dir != b.run_dir and a.run_dir.exists() and b.run_dir.exists()
    finally:
        a.close()
        b.close()
        for ctx in (a, b):
            shutil.rmtree(ctx.run_dir)


# --- undoing the promotion ---------------------------------------------------

def promoted_point(env):
    return find_restore_point(Config.load(env["config"]))


def test_restore_finds_the_promoted_run_and_dry_run_changes_nothing(env):
    config = Config.load(env["config"])
    point = promoted_point(env)
    assert point.final_status == "promoted to production"
    before = sha256_of_file(env["production"])
    assert before == point.production_after != point.production_before
    result = restore(config)
    assert result.status == "dry-run" and result.target_sha256 == point.production_before
    assert config.restore_phrase in result.notes[-1]
    assert sha256_of_file(env["production"]) == before


def test_restore_needs_its_own_phrase(env):
    config = Config.load(env["config"])
    before = sha256_of_file(env["production"])
    for phrase in (None, "wrong", config.authorization_phrase):
        result = restore(config, apply=True, authorize=phrase)
        assert result.status == "blocked" and "restore phrase" in result.notes[-1]
    assert sha256_of_file(env["production"]) == before


def test_restore_refuses_a_backup_whose_hash_changed(env):
    config = Config.load(env["config"])
    backup = promoted_point(env).backup
    good = backup.read_bytes()
    try:
        backup.write_bytes(good + b"\0")
        result = restore(config, apply=True, authorize=config.restore_phrase)
        assert result.status == "blocked" and "does not match" in result.notes[0]
    finally:
        backup.write_bytes(good)


def test_restore_refuses_to_discard_later_changes(env):
    config = Config.load(env["config"])
    production = env["production"]
    promoted = production.read_bytes()
    try:
        production.write_bytes(promoted + b"later work")
        result = restore(config, apply=True, authorize=config.restore_phrase)
        assert result.status == "blocked" and "changed since" in result.notes[0]
        assert production.read_bytes() == promoted + b"later work"
    finally:
        production.write_bytes(promoted)


def test_restore_puts_back_the_pre_cycle_state_and_keeps_what_it_replaced(env):
    config = Config.load(env["config"])
    point = promoted_point(env)
    result = restore(config, apply=True, authorize=config.restore_phrase)
    assert result.status == "restored", result.notes
    assert sha256_of_file(env["production"]) == point.production_before == result.production_sha256_after
    assert sha256_of_file(Path(result.set_aside)) == point.production_after
    assert not env["production"].with_name(env["production"].name + ".restoring").exists()
    record = json.loads(Path(result.record).read_text(encoding="utf-8"))
    assert record["status"] == "restored" and record["run"] == point.run
    assert restore(config, apply=True, authorize=config.restore_phrase).status == "nothing-to-do"


def test_after_a_restore_the_cycle_runs_again(env):
    m = run(env["config"])
    st = stages(m)
    assert st["transfer"].status == "completed", "completion markers must not outlive the restored file"
    assert st["professional_duplicates"].summary["deleted"] > 0
