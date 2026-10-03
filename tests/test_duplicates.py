from dirqa.config import DuplicateSpec
from dirqa.stages.duplicates import Group, classify, decide, group_hash, partition

SPEC = DuplicateSpec(
    name="t", query="q", table="T", record_id="rid", stable_key="key",
    group_by=["name", "addr"], compare=["npi", "network", "date", "loc", "key"],
    legitimate_if_differs_in=["npi", "network"], text_fields=["name", "addr"], location_keys=["loc"],
)


def row(rid, key=1, npi="1", network="A", date="2020", loc=7, name="Clinic", addr="1 Main St"):
    return dict(rid=rid, key=key, npi=npi, network=network, date=date, loc=loc, name=name, addr=addr)


def test_exact_needs_identical_fields_and_same_stable_key():
    assert classify([row(1), row(2)], SPEC)[0] == "exact"
    assert classify([row(1, key=1), row(2, key=2)], SPEC)[0] == "review"


def test_no_stable_key_never_deletes():
    spec = DuplicateSpec(**{**SPEC.__dict__, "stable_key": None})
    kind, _ = classify([row(1), row(2)], spec)
    assert kind == "exact_no_stable_key"


def test_network_or_identifier_difference_is_legitimate():
    assert classify([row(1, key=1), row(2, key=2, network="B")], SPEC)[0] == "legitimate"
    assert classify([row(1, key=1), row(2, key=2, npi="9")], SPEC)[0] == "legitimate"


def test_text_only_difference_at_same_location_is_likely_redundant():
    kind, reason = classify([row(1, key=1), row(2, key=2, name="Clinic Inc")], SPEC)
    assert kind == "likely_redundant" and "name" in reason


def test_other_difference_is_review():
    kind, reason = classify([row(1, key=1), row(2, key=2, date="2024")], SPEC)
    assert kind == "review" and "date" in reason


def test_partition_separates_distinct_listings():
    members = [row(1), row(2), row(3, key=3, network="B")]
    parts = sorted(partition(members, SPEC), key=len)
    assert [len(p) for p in parts] == [1, 2]


def test_group_hash_ignores_record_id_and_order():
    a = group_hash([row(1), row(2)], SPEC)
    b = group_hash([row(99), row(42)], SPEC)
    c = group_hash([row(2), row(1)], SPEC)
    assert a == b == c
    assert group_hash([row(1), row(2, network="B")], SPEC) != a


def test_decide_applies_logged_decisions():
    rows = [row(5, key=1), row(9, key=2, date="2024")]
    g = Group("g", "review", "r", rows, [5, 9], [1, 2], group_hash(rows, SPEC))
    decide(g, SPEC, {})
    assert g.delete == [] and g.decision == ""
    decide(g, SPEC, {g.group_hash: {"decision": "delete", "keep_stable_key": "2"}})
    assert g.keep == 9 and g.delete == [5]
    g2 = Group("g", "review", "r", rows, [5, 9], [1, 2], group_hash(rows, SPEC))
    decide(g2, SPEC, {g2.group_hash: {"decision": "exception"}})
    assert g2.delete == [] and g2.decision == "exception"


def test_exact_group_keeps_lowest_record_id():
    rows = [row(30), row(12), row(25)]
    g = Group("g", "exact", "r", rows, sorted(r["rid"] for r in rows), [1], "h")
    decide(g, SPEC, {})
    assert g.keep == 12 and g.delete == [25, 30]
