import sqlite3

import pytest

from dirqa.backends.sqlite import SqliteBackend
from dirqa.queries import QueryLibrary
from dirqa.rules.registry import Rule, evaluate, load_rules


@pytest.fixture
def backend(tmp_path):
    db = tmp_path / "r.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE T (id INTEGER, county TEXT)")
    con.executemany("INSERT INTO T VALUES (?, ?)", [(1, "Kings"), (2, ""), (3, "Queens")])
    con.commit()
    con.close()
    return SqliteBackend(db, QueryLibrary({
        "blank_county": "SELECT * FROM T WHERE county = ''",
        "any_row": "SELECT * FROM T",
        "none": "SELECT * FROM T WHERE 1 = 0",
        "grouped": "SELECT county, COUNT(*) AS n FROM T GROUP BY county",
        "broken": "SELECT * FROM NoSuchTable",
    }))


def test_zero_rows_blocking_fails_when_rows_exist(backend):
    r = evaluate(Rule("a", "d", "blocking", "zero_rows", "blank_county"), backend)
    assert r.status == "fail" and r.row_count == 1 and r.blocking_failure


def test_zero_rows_advisory_warns(backend):
    r = evaluate(Rule("a", "d", "advisory", "zero_rows", "blank_county"), backend)
    assert r.status == "warn" and not r.blocking_failure


def test_zero_rows_passes_when_empty(backend):
    assert evaluate(Rule("a", "d", "blocking", "zero_rows", "none"), backend).status == "pass"


def test_presence(backend):
    assert evaluate(Rule("a", "d", "blocking", "at_least_one_row", "any_row"), backend).status == "pass"
    assert evaluate(Rule("a", "d", "blocking", "at_least_one_row", "none"), backend).status == "fail"


def test_grouped_report_never_fails(backend):
    r = evaluate(Rule("a", "d", "advisory", "grouped_report", "grouped"), backend)
    assert r.status == "report" and r.row_count == 3


def test_reminder_has_no_query(backend):
    r = evaluate(Rule("a", "October reminder", "reminder"), backend)
    assert r.status == "reminder"


def test_broken_query_is_a_finding_not_a_crash(backend):
    r = evaluate(Rule("a", "d", "blocking", "zero_rows", "broken"), backend)
    assert r.status == "error" and r.blocking_failure


def test_rule_validation():
    with pytest.raises(ValueError):
        Rule("a", "d", "critical", "zero_rows", "x")
    with pytest.raises(ValueError):
        Rule("a", "d", "blocking", "some_rows", "x")
    with pytest.raises(ValueError):
        Rule("a", "d", "blocking", "zero_rows", None)


def test_registry_rejects_duplicate_ids(tmp_path):
    p = tmp_path / "rules.yaml"
    p.write_text("- {id: a, description: d, severity: reminder}\n- {id: a, description: d, severity: reminder}\n")
    with pytest.raises(ValueError):
        load_rules(p)


def test_shipped_registry_loads_and_every_query_exists():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    rules = load_rules(root / "config" / "rules.yaml")
    library = QueryLibrary.load(root / "config" / "queries.yaml")
    assert len(rules) >= 20
    for rule in rules:
        if rule.query:
            assert rule.query in library, rule.id
    assert any(r.severity == "blocking" and r.origin == "checklist" and r.promoted_on for r in rules)
    assert any(r.severity == "advisory" and r.origin == "checklist" and not r.promoted_on for r in rules)
