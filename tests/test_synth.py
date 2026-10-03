"""The generator's own contract: every planted defect is where the answer key says it is,
the prior month is clean, and the same seed always gives the same bytes."""

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from synth import vocab
from synth.generate import FLAG_COLUMNS, PRIOR_CYCLE, generate

SCALE = 0.05

# Which database each answer-key table lives in, and its record-id column.
TABLE_DB = {
    "ProfessionalProviderSource": ("sources/PractitionerFeed.sqlite", "ProviderRecordID"),
    "AdditionalServiceSource": ("sources/ServiceVendorFeed.sqlite", "VendorRecordID"),
    "PharmacyPublicationDirectory": ("DirectoryQualityHub.sqlite", "PharmacyRecordID"),
}


@pytest.fixture(scope="session")
def demo(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("demo")
    generate(out, scale=SCALE, quiet=True)
    return out


@pytest.fixture(scope="session")
def key(demo) -> dict:
    return json.loads((demo / "answer_key.json").read_text(encoding="utf-8"))


def fetch(demo: Path, table: str, where: str = "1=1", params=()) -> list[dict]:
    db, _ = TABLE_DB.get(table, ("DirectoryQualityHub.sqlite", None))
    con = sqlite3.connect(demo / db)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(f'SELECT * FROM "{table}" WHERE {where}', params)]
    finally:
        con.close()


def by_ids(demo: Path, table: str, ids: list[int]) -> list[dict]:
    _, id_col = TABLE_DB[table]
    marks = ",".join("?" for _ in ids)
    return fetch(demo, table, f"{id_col} IN ({marks})", ids)


def same_except(a: dict, b: dict, ignore: set[str]) -> bool:
    return {k: v for k, v in a.items() if k not in ignore} == {k: v for k, v in b.items() if k not in ignore}


# ---------------------------------------------------------------------------

def test_expected_tables_exist(demo):
    def tables(db):
        con = sqlite3.connect(demo / db)
        try:
            return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()

    assert tables("sources/PractitionerFeed.sqlite") == {"ProfessionalProviderSource"}
    assert tables("sources/ServiceVendorFeed.sqlite") == {
        "AdditionalServiceSource", "OtherFacilityReference", "ManagedCareFacilitySource"}
    assert tables("DirectoryQualityHub.sqlite") == {
        "ProfessionalDirectory", "ServiceDirectory", "PharmacyPublicationDirectory",
        "OtherFacilityReference", "ManagedCareFacilitySource", "ApprovedDeletionList"}


def test_counts_in_answer_key_match_databases(demo, key):
    for table, n in key["counts"]["current_source"].items():
        assert len(fetch(demo, table)) == n, table
    prior = {"ProfessionalDirectory", "ServiceDirectory", "OtherFacilityReference",
             "ManagedCareFacilitySource"}
    for table in prior:
        assert len(fetch(demo, table)) == key["counts"]["prior_month"][table], table


def test_every_defect_record_exists(demo, key):
    for kind, entries in key["defects"].items():
        for e in entries:
            ids = e.get("record_ids") or [e["record_id"]]
            assert len(by_ids(demo, e["table"], ids)) == len(ids), (kind, e)


def test_exact_duplicates_are_identical_rows(demo, key):
    for e in key["defects"]["exact_duplicate"]:
        _, id_col = TABLE_DB[e["table"]]
        rows = by_ids(demo, e["table"], e["record_ids"])
        assert len(rows) >= 2
        assert len(set(e["stable_keys"])) == 1, "copies share the stable key"
        for r in rows[1:]:
            assert same_except(rows[0], r, {id_col})
        assert e["keep_record_id"] == min(e["record_ids"])


def test_legitimate_multiples_differ_only_in_network(demo, key):
    for e in key["defects"]["legitimate_multiple"]:
        _, id_col = TABLE_DB[e["table"]]
        stable = "PracticeLocationKey" if e["table"].startswith("Professional") else "ServiceLocationKey"
        a, b = by_ids(demo, e["table"], e["record_ids"])
        assert a["Network"] != b["Network"]
        assert same_except(a, b, {id_col, stable, "Network"})


def test_review_duplicates_differ_in_declared_field(demo, key):
    for e in key["defects"]["review_duplicate"]:
        _, id_col = TABLE_DB[e["table"]]
        stable = "PracticeLocationKey" if e["table"].startswith("Professional") else "ServiceLocationKey"
        a, b = by_ids(demo, e["table"], e["record_ids"])
        assert a[e["differs_in"]] != b[e["differs_in"]]
        assert same_except(a, b, {id_col, stable, e["differs_in"]})


def test_malformed_languages_normalize_to_expected(demo, key):
    def independent_normalize(value: str) -> str:
        parts = [p.strip() for p in value.split(",")]
        return ", ".join(p for p in parts if p)

    entries = key["defects"]["malformed_languages"]
    assert entries
    comma_only = 0
    for e in entries:
        (row,) = by_ids(demo, e["table"], [e["record_id"]])
        assert row["SpokenLanguages"] == e["original"]
        assert independent_normalize(e["original"]) == e["expected"]
        assert independent_normalize(e["expected"]) == e["expected"], "normalization is idempotent"
        comma_only += e["comma_only"]
    assert comma_only == sum(1 for e in entries if e["expected"] == "")
    assert comma_only > 0


def test_prior_month_pharmacy_languages_are_clean(demo):
    # The hub holds the *current* staging table (malformed by design); the clean
    # prior-month version lives in the archive.
    archive = demo / "archive" / PRIOR_CYCLE / "PharmacyPublicationDirectory.csv"
    with archive.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            v = row["SpokenLanguages"]
            assert ", ".join(p.strip() for p in v.split(",") if p.strip()) == v


def test_vision_missing_from_one_borough_this_month(demo, key):
    fact = key["facts"]["vision_missing_borough"]
    now = fetch(demo, "AdditionalServiceSource", "ServiceType=? AND Borough=?",
                (fact["service_type"], fact["borough"]))
    before = fetch(demo, "ServiceDirectory", "ServiceType=? AND Borough=?",
                   (fact["service_type"], fact["borough"]))
    assert len(now) == 0
    assert len(before) == fact["prior_month_rows"] > 0


def test_retired_source_rows_carry_exact_source_value(demo, key):
    fact = key["facts"]["retired_source"]
    now = fetch(demo, "AdditionalServiceSource", "Source=?", (fact["source"],))
    before = fetch(demo, "ServiceDirectory", "Source=?", (fact["source"],))
    assert len(now) == fact["rows"] == len(key["defects"]["retired_source"])
    assert before == []


def test_source_expansion_is_rows_not_locations(demo, key):
    fact = key["facts"]["source_expansion"]
    now = fetch(demo, "AdditionalServiceSource", "Source=?", (fact["source"],))
    before = fetch(demo, "ServiceDirectory", "Source=?", (fact["source"],))
    assert len(now) == fact["current_month_rows"]
    assert len(before) == fact["prior_month_rows"]
    assert len({r["AddressKey"] for r in now}) == fact["locations"]
    assert len(now) == fact["locations"] * len(vocab.EXPANDING_SOURCE_CURRENT_SERVICES)


def test_named_exclusion_is_back_in_the_feed(demo, key):
    person = key["facts"]["named_exclusion"]
    now = fetch(demo, "ProfessionalProviderSource", "NPI=?", (person["NPI"],))
    before = fetch(demo, "ProfessionalDirectory", "NPI=?", (person["NPI"],))
    assert len(now) == 2 and before == []
    assert {r["LastName"] for r in now} == {person["LastName"]}


def test_named_org_carries_forbidden_lines(demo, key):
    org = key["facts"]["named_org"]
    rows = fetch(demo, "AdditionalServiceSource", "DisplayName=?", (org["DisplayName"],))
    assert len(rows) == org["rows"]
    assert all(r["LineA_Flag"] == "1" for r in rows)
    bad = [r for r in rows if any(r[c] == "1" for c in org["must_be_zero"])]
    assert len(bad) == len(key["defects"]["named_org_nonzero_flag"])


def test_approved_deletions_match_hub_list(demo, key):
    listed = {r["ProviderNumber"] for r in fetch(demo, "ApprovedDeletionList")}
    tagged = {e["provider_number"] for e in key["defects"]["approved_deletion"]}
    assert listed == tagged
    for pn in listed:
        assert fetch(demo, "AdditionalServiceSource", "ProviderNumber=?", (pn,))


def test_prior_month_is_clean(demo):
    prof = fetch(demo, "ProfessionalDirectory")
    assert all(r["County"] and r["Specialty"] and r["Phone"] for r in prof)
    assert len({r["PracticeLocationKey"] for r in prof}) == len(prof)
    for r in prof:
        flags = [r[c] for c in FLAG_COLUMNS]
        assert r["LineCode"] == ("" if all(f == "" for f in flags) else "".join(flags))
        assert (r["Specialty"], r["County"]) not in vocab.SPECIALTY_COUNTY_EXCLUSIONS
        if r["Specialty"] == vocab.SCHOOL_BASED_SPECIALTY:
            assert r["LimitationText"] == vocab.SCHOOL_LIMITATION_TEXT
    svc = fetch(demo, "ServiceDirectory")
    assert all(r["County"] and r["Borough"] for r in svc)
    assert len({r["ServiceLocationKey"] for r in svc}) == len(svc)
    assert all(r["LineA_Flag"] == "1" for r in svc if r["ServiceType"] == vocab.VISION_SERVICE_TYPE)


def test_current_month_line_code_is_blank_until_populated(demo):
    assert all(r["LineCode"] == "" for r in fetch(demo, "ProfessionalProviderSource"))
    assert all(r["LineCode"] == "" for r in fetch(demo, "AdditionalServiceSource"))


def test_same_seed_same_bytes(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate(a, scale=0.02, quiet=True)
    generate(b, scale=0.02, quiet=True)
    for path in sorted(a.rglob("*.csv")):
        assert path.read_bytes() == (b / path.relative_to(a)).read_bytes(), path
    ka = json.loads((a / "answer_key.json").read_text())
    kb = json.loads((b / "answer_key.json").read_text())
    assert ka == kb


def test_samples_and_checklist_are_written(demo):
    assert (demo / "samples" / "ProfessionalProviderSource.csv").exists()
    assert (demo / "samples" / "ApprovedDeletionList.csv").exists()
    with (demo / "advisory_checklist.csv").open(encoding="utf-8", newline="") as f:
        notes = list(csv.DictReader(f))
    assert len(notes) == len(vocab.ADVISORY_CHECKLIST)
    assert notes[0].keys() == {"Note", "AddedOn", "AddedBy"}
