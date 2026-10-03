"""Synthetic directory generator.

Builds a fictional provider-directory universe, derives a prior-month (clean)
state and a current-month (defective) state from it, plants defects whose
locations are known, and writes:

    <out>/sources/PractitionerFeed.sqlite               current-month professional source
    <out>/sources/ServiceVendorFeed.sqlite current-month service sources
    <out>/DirectoryQualityHub.sqlite                    the repository as the cycle begins
    <out>/archive/<prior>/*.csv                         prior-month tables, for comparison
    <out>/csv/<cycle>/*.csv                             current-month tables, for Excel
    <out>/samples/*.csv                                 first rows of each table (committed)
    <out>/advisory_checklist.csv                        the informal notes spreadsheet
    <out>/answer_key.json                               every planted defect, by record

The same seed always produces the same data. Nothing here is real: names,
organizations, identifiers and phone numbers are invented; only the borough /
county / ZIP geography is public knowledge.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from pathlib import Path

from . import vocab
from .npi import make_npi

CYCLE = "2026-09"
PRIOR_CYCLE = "2026-08"
DEFAULT_SEED = 20260913

Row = dict

# ---------------------------------------------------------------------------
# Table schemas (column order as written)
# ---------------------------------------------------------------------------

FLAG_COLUMNS = ["LineA_Flag", "LineB_Flag", "LineC_Flag", "LineD_Flag"]

PROFESSIONAL_COLUMNS = [
    "ProviderRecordID", "ProviderNumber", "NPI", "FirstName", "LastName", "OfficeName",
    "Specialty", "ProviderType", "Address1", "Address2", "City", "State", "ZIP", "County",
    "Borough", "Phone", "Network", "Source", "EffectiveDate", "ProviderKey", "AddressKey",
    "PracticeLocationKey", *FLAG_COLUMNS, "PrintFlag", "LineCode", "LimitationText",
]

SERVICE_COLUMNS = [
    "VendorRecordID", "ProviderNumber", "NPI", "DisplayName", "FacilityType", "ServiceType",
    "Address1", "Address2", "City", "State", "ZIP", "County", "Borough", "Phone", "Network",
    "Source", "EffectiveStart", "EffectiveEnd", "VendorKey", "AddressKey",
    "ServiceLocationKey", *FLAG_COLUMNS, "PrintFlag", "LineCode",
]

PHARMACY_COLUMNS = [
    "PharmacyRecordID", "ProviderNumber", "NPI", "DisplayName", "Address1", "Address2",
    "City", "State", "ZIP", "County", "Borough", "Phone", "SpokenLanguages", "Hours",
    "Network", *FLAG_COLUMNS, "PrintFlag",
]

FACILITY_REF_COLUMNS = [
    "FacilityRefID", "FacilityName", "FacilityType", "NPI", "ProviderNumber", "Address1",
    "Address2", "City", "State", "ZIP", "County", "Borough", "Phone", "Network",
]

MANAGED_CARE_COLUMNS = [
    "FacilityID", "FacilityName", "FacilityType", "NPI", "ProviderNumber", "Address1",
    "Address2", "City", "State", "ZIP", "County", "Borough", "Phone", "Network",
    "ContractType", "EffectiveStart",
]

DELETION_LIST_COLUMNS = ["DeletionID", "ProviderNumber", "DisplayName", "Reason",
                         "ApprovedBy", "ApprovedOn"]

CHECKLIST_COLUMNS = ["Note", "AddedOn", "AddedBy"]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def weighted_choice(rng: random.Random, pairs):
    values = [v for v, _ in pairs]
    weights = [w for _, w in pairs]
    return rng.choices(values, weights=weights, k=1)[0]


def unique_value(rng: random.Random, seen: set, make: Callable[[random.Random], str]) -> str:
    while True:
        value = make(rng)
        if value not in seen:
            seen.add(value)
            return value


def rand_date(rng: random.Random, start: date, end: date) -> str:
    return (start + timedelta(days=rng.randint(0, (end - start).days))).isoformat()


def make_phone(rng: random.Random, borough: str, used: set[str] | None = None) -> str:
    """A phone number in the 555 exchange, which is never assigned to a subscriber.

    With ``used`` given, the number is unique: a shared phone in the data is then
    always deliberate (a duplicate, or two sites behind one switchboard)."""
    area = rng.choice(vocab.BOROUGHS[borough]["area_codes"])
    while True:
        phone = f"{area}-555-{rng.randint(0, 9999):04d}"
        if used is None:
            return phone
        if phone not in used:
            used.add(phone)
            return phone


def make_address(rng: random.Random, address_key: int, borough: str | None = None,
                 used_phones: set[str] | None = None) -> Row:
    borough = borough or weighted_choice(rng, vocab.BOROUGH_WEIGHTS)
    info = vocab.BOROUGHS[borough]
    zip_code = rng.choice(info["zips"])
    return {
        "AddressKey": address_key,
        "Address1": f"{rng.randint(1, 3999)} {rng.choice(vocab.STREETS[borough])}",
        "Address2": rng.choice(vocab.ADDRESS2_OPTIONS),
        "City": vocab.city_for(borough, zip_code),
        "State": "NY",
        "ZIP": zip_code,
        "County": info["county"],
        "Borough": borough,
        "Phone": make_phone(rng, borough, used_phones),
    }


def make_flags(rng: random.Random, all_blank_share: float = 0.02, force_a: bool = False) -> Row:
    """Four coverage-line flags as text '0' / '1'. A small share of rows carry no flags at all."""
    if not force_a and rng.random() < all_blank_share:
        return {c: "" for c in FLAG_COLUMNS}
    return {
        "LineA_Flag": "1" if force_a or rng.random() < 0.85 else "0",
        "LineB_Flag": "1" if rng.random() < 0.55 else "0",
        "LineC_Flag": "1" if rng.random() < 0.35 else "0",
        "LineD_Flag": "1" if rng.random() < 0.15 else "0",
    }


def line_code(row: Row) -> str:
    """The combined line code: the four flags concatenated, or blank when all four are blank.

    A row with *some* flags blank has no defined line code. That is a business
    decision, not something the generator (or the pipeline) may invent.
    """
    values = [row[c] for c in FLAG_COLUMNS]
    if all(v == "" for v in values):
        return ""
    if any(v == "" for v in values):
        raise ValueError(f"partial flags have no defined line code: {values}")
    return "".join(values)


def clone(row: Row) -> Row:
    copy = dict(row)
    copy["_tags"] = [dict(t) for t in row.get("_tags", [])]
    return copy


def tag(row: Row, kind: str, **extra) -> None:
    row.setdefault("_tags", []).append({"kind": kind, **extra})


def pick_rows(rng: random.Random, rows: list[Row], count: int, used: set, key: str,
              predicate: Callable[[Row], bool] | None = None) -> list[Row]:
    """Choose ``count`` rows not yet used by another injection, and mark them used."""
    candidates = [r for r in rows if r[key] not in used and (predicate is None or predicate(r))]
    chosen = rng.sample(candidates, min(count, len(candidates)))
    used.update(r[key] for r in chosen)
    return chosen


def assign_record_ids(rng: random.Random, rows: list[Row], column: str) -> None:
    """Number rows 1..n in a shuffled order, like an autonumber column after a reload."""
    rng.shuffle(rows)
    for i, row in enumerate(rows, 1):
        row[column] = i


def normalize_languages(value: str) -> str:
    """The reference normalization: split on commas, trim, drop empties, rejoin with ', '."""
    return ", ".join(part.strip() for part in value.split(",") if part.strip())


# ---------------------------------------------------------------------------
# Answer key
# ---------------------------------------------------------------------------

class AnswerKey:
    def __init__(self, seed: int, scale: float):
        # No timestamp: the seed is the identity, and the key must be byte-identical
        # every time it is regenerated so the committed copy never churns.
        self.meta = {"seed": seed, "scale": scale, "cycle": CYCLE, "prior_cycle": PRIOR_CYCLE}
        self.sections: dict[str, dict[str, list]] = {"defects": defaultdict(list),
                                                     "changes": defaultdict(list)}
        self.facts: dict = {}
        self.counts: dict = {}

    def add(self, section: str, kind: str, **entry) -> None:
        self.sections[section][kind].append(entry)

    def to_dict(self) -> dict:
        return {
            "meta": self.meta,
            "counts": self.counts,
            "facts": self.facts,
            "summary": {s: {k: len(v) for k, v in kinds.items()} for s, kinds in self.sections.items()},
            "defects": dict(self.sections["defects"]),
            "changes": dict(self.sections["changes"]),
        }


def collect_tags(rows: Iterable[Row], table: str, id_col: str, key_col: str, answer: AnswerKey) -> None:
    """Turn the hidden tags on rows into answer-key entries, grouping group tags."""
    groups: dict[tuple, dict] = {}
    for row in rows:
        for t in row.get("_tags", []):
            section = t.get("section", "defects")
            extra = {k: v for k, v in t.items() if k not in ("kind", "group", "role", "section")}
            if "group" in t:
                g = groups.setdefault((section, t["kind"], t["group"]),
                                      {"table": table, "group": t["group"],
                                       "record_ids": [], "stable_keys": []})
                g["record_ids"].append(row[id_col])
                g["stable_keys"].append(row[key_col])
                g.update(extra)
            else:
                answer.add(section, t["kind"], table=table, record_id=row[id_col],
                           stable_key=row[key_col], **extra)
    for (section, kind, _), g in groups.items():
        g["record_ids"].sort()
        if kind == "exact_duplicate":
            g["keep_record_id"] = g["record_ids"][0]
        answer.add(section, kind, **g)


# ---------------------------------------------------------------------------
# Universe: professional providers
# ---------------------------------------------------------------------------

def build_practitioners(rng: random.Random, count: int) -> list[Row]:
    npis: set[str] = set()
    numbers: set[str] = set()
    specialties = [(s, w) for s, _, w in vocab.SPECIALTIES]
    out = []
    for key in range(1, count + 1):
        specialty = weighted_choice(rng, specialties)
        out.append({
            "ProviderKey": key,
            "NPI": unique_value(rng, npis, make_npi),
            "ProviderNumber": unique_value(rng, numbers, lambda r: f"P{r.randint(1_000_000, 9_999_999)}"),
            "FirstName": rng.choice(vocab.FIRST_NAMES),
            "LastName": rng.choice(vocab.LAST_NAMES),
            "Specialty": specialty,
            "ProviderType": vocab.PROVIDER_TYPE_FOR_SPECIALTY[specialty],
            "Source": weighted_choice(rng, vocab.PROFESSIONAL_SOURCES),
            "_home": weighted_choice(rng, vocab.BOROUGH_WEIGHTS),
        })
    return out


def build_practice_addresses(rng: random.Random, count: int, used_phones: set[str]) -> list[Row]:
    """A shared pool of practice locations; group practices put many practitioners at one."""
    out = []
    for key in range(1, count + 1):
        address = make_address(rng, key, used_phones=used_phones)
        pattern = rng.choice(vocab.OFFICE_NAME_PATTERNS)
        address["OfficeName"] = pattern.format(last=rng.choice(vocab.LAST_NAMES),
                                               prefix=rng.choice(vocab.NAME_PREFIXES))
        out.append(address)
    return out


def build_professional_rows(rng: random.Random, practitioners: list[Row],
                            addresses: list[Row]) -> list[Row]:
    """One row per practitioner per practice location, with a stable PracticeLocationKey."""
    by_borough: dict[str, list[Row]] = defaultdict(list)
    for a in addresses:
        by_borough[a["Borough"]].append(a)
    excluded = set(vocab.SPECIALTY_COUNTY_EXCLUSIONS)

    rows = []
    location_key = 0
    for p in practitioners:
        wanted = weighted_choice(rng, vocab.LOCATION_COUNT_WEIGHTS)
        chosen: dict[int, Row] = {}
        for _ in range(60):
            if len(chosen) == wanted:
                break
            pool = by_borough[p["_home"]] if rng.random() < 0.7 else addresses
            a = rng.choice(pool)
            if a["AddressKey"] in chosen or (p["Specialty"], a["County"]) in excluded:
                continue
            chosen[a["AddressKey"]] = a
        for a in chosen.values():
            location_key += 1
            row = {k: v for k, v in p.items() if not k.startswith("_")}
            row.update(a)
            row.update({
                "PracticeLocationKey": location_key,
                "Network": weighted_choice(rng, vocab.NETWORKS),
                "EffectiveDate": rand_date(rng, date(2015, 1, 1), date(2026, 7, 31)),
                **make_flags(rng),
                "PrintFlag": "1" if rng.random() < 0.96 else "0",
                "LineCode": "",
                "LimitationText": (vocab.SCHOOL_LIMITATION_TEXT
                                   if p["Specialty"] == vocab.SCHOOL_BASED_SPECIALTY else ""),
            })
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Universe: service directory (organizations)
# ---------------------------------------------------------------------------

def unique_org_name(rng: random.Random, names: set[str], suffixes: list[str], borough: str) -> str:
    base = f"{rng.choice(vocab.NAME_PREFIXES)} {rng.choice(suffixes)}"
    for candidate in (base, f"{base} of {borough}", f"{base} II", f"{base} III"):
        if candidate not in names:
            names.add(candidate)
            return candidate
    return unique_org_name(rng, names, suffixes, borough)


def build_organizations(rng: random.Random, count: int, staten_island_vision_orgs: int) -> list[Row]:
    names = {vocab.NAMED_ORG["DisplayName"]}
    npis: set[str] = set()
    numbers: set[str] = set()
    type_weights = [(ft, w) for ft, _, w, _, _ in vocab.FACILITY_TYPES]
    type_info = {ft: (services, suffixes, source)
                 for ft, services, _, suffixes, source in vocab.FACILITY_TYPES}

    orgs = []
    vision_forced = 0
    for key in range(1, count + 1):
        facility_type = weighted_choice(rng, type_weights)
        services, suffixes, source = type_info[facility_type]
        if facility_type == "Home Care Agency" and rng.random() < 0.3:
            source = vocab.EXPANDING_SOURCE
        home = weighted_choice(rng, vocab.BOROUGH_WEIGHTS)
        if facility_type == vocab.VISION_FACILITY_TYPE and vision_forced < staten_island_vision_orgs:
            home, vision_forced = "Staten Island", vision_forced + 1
        orgs.append({
            "VendorKey": key,
            "DisplayName": unique_org_name(rng, names, suffixes, home),
            "FacilityType": facility_type,
            "NPI": unique_value(rng, npis, make_npi),
            "ProviderNumber": unique_value(rng, numbers, lambda r: f"V{r.randint(100_000, 999_999)}"),
            "Network": weighted_choice(rng, vocab.NETWORKS),
            "Source": source,
            "_home": home,
            "_services": services,
        })
    # The organization the checklist singles out, with a fixed shape.
    orgs.append({
        "VendorKey": count + 1,
        "DisplayName": vocab.NAMED_ORG["DisplayName"],
        "FacilityType": vocab.NAMED_ORG["FacilityType"],
        "NPI": unique_value(rng, npis, make_npi),
        "ProviderNumber": unique_value(rng, numbers, lambda r: f"V{r.randint(100_000, 999_999)}"),
        "Network": "Harbor Network",
        "Source": "TransportVendorFeed",
        "_home": "Queens",
        "_services": [vocab.NAMED_ORG["ServiceType"]],
        "_named": True,
    })
    return orgs


def build_service_rows(rng: random.Random, orgs: list[Row], used_phones: set[str],
                       first_address_key: int = 100_001, first_location_key: int = 1) -> list[Row]:
    """One row per organization per location per service type, with a stable ServiceLocationKey."""
    rows = []
    address_key = first_address_key - 1
    location_key = first_location_key - 1
    for o in orgs:
        n_locations = 4 if o.get("_named") else weighted_choice(rng, vocab.ORG_LOCATION_COUNT_WEIGHTS)
        for _ in range(n_locations):
            address_key += 1
            borough = o["_home"] if rng.random() < 0.8 else weighted_choice(rng, vocab.BOROUGH_WEIGHTS)
            a = make_address(rng, address_key, borough, used_phones)
            if o["Source"] == vocab.EXPANDING_SOURCE:
                services = [vocab.EXPANDING_SOURCE_PRIOR_SERVICE]
            elif o.get("_named"):
                services = list(o["_services"])
            else:
                k = min(weighted_choice(rng, vocab.ORG_SERVICE_COUNT_WEIGHTS), len(o["_services"]))
                services = rng.sample(o["_services"], k)
            for service in services:
                location_key += 1
                row = {k: v for k, v in o.items() if not k.startswith("_")}
                row.update(a)
                is_vision = service == vocab.VISION_SERVICE_TYPE
                if o.get("_named"):
                    flags = {"LineA_Flag": "1", "LineB_Flag": "0", "LineC_Flag": "0", "LineD_Flag": "0"}
                else:
                    flags = make_flags(rng, force_a=is_vision)
                row.update({
                    "ServiceType": service,
                    "ServiceLocationKey": location_key,
                    "EffectiveStart": rand_date(rng, date(2016, 1, 1), date(2026, 7, 31)),
                    "EffectiveEnd": "" if rng.random() < 0.9 else rand_date(rng, date(2027, 1, 1), date(2029, 12, 31)),
                    **flags,
                    "PrintFlag": "1" if rng.random() < 0.97 else "0",
                    "LineCode": "",
                })
                rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Universe: pharmacies and reference tables
# ---------------------------------------------------------------------------

def build_pharmacies(rng: random.Random, count: int, used_phones: set[str]) -> list[Row]:
    names: set[str] = set()
    npis: set[str] = set()
    numbers: set[str] = set()
    language_counts = [(0, 10), (1, 35), (2, 30), (3, 17), (4, 8)]
    rows = []
    for key in range(1, count + 1):
        a = make_address(rng, key, used_phones=used_phones)
        a.pop("AddressKey")
        languages = rng.sample(vocab.LANGUAGES, weighted_choice(rng, language_counts))
        rows.append({
            "PharmacyRecordID": key,
            "ProviderNumber": unique_value(rng, numbers, lambda r: f"R{r.randint(100_000, 999_999)}"),
            "NPI": unique_value(rng, npis, make_npi),
            "DisplayName": unique_org_name(rng, names, vocab.PHARMACY_SUFFIXES, a["Borough"]),
            **a,
            "SpokenLanguages": ", ".join(languages),
            "Hours": rng.choice(vocab.PHARMACY_HOURS),
            "Network": weighted_choice(rng, vocab.NETWORKS),
            **make_flags(rng, all_blank_share=0.0),
            "PrintFlag": "1",
        })
    return rows


def build_facility_reference(rng: random.Random, count: int, id_column: str,
                             managed_care: bool = False) -> list[Row]:
    names: set[str] = set()
    npis: set[str] = set()
    numbers: set[str] = set()
    type_weights = [(ft, w) for ft, _, w, _, _ in vocab.FACILITY_TYPES if ft != "Pharmacy"]
    suffixes = {ft: s for ft, _, _, s, _ in vocab.FACILITY_TYPES}
    rows = []
    for key in range(1, count + 1):
        facility_type = weighted_choice(rng, type_weights)
        a = make_address(rng, key)
        a.pop("AddressKey")
        row = {
            id_column: key,
            "FacilityName": unique_org_name(rng, names, suffixes[facility_type], a["Borough"]),
            "FacilityType": facility_type,
            "NPI": unique_value(rng, npis, make_npi),
            "ProviderNumber": unique_value(rng, numbers, lambda r: f"F{r.randint(100_000, 999_999)}"),
            **a,
            "Network": weighted_choice(rng, vocab.NETWORKS),
        }
        if managed_care:
            row["ContractType"] = rng.choice(["Full Risk", "Fee Schedule", "Capitated"])
            row["EffectiveStart"] = rand_date(rng, date(2018, 1, 1), date(2026, 6, 30))
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Month derivation: professional providers
# ---------------------------------------------------------------------------

def derive_professional_months(rng: random.Random, scaled: Callable[[float], int],
                               universe: list[Row], addresses: list[Row],
                               answer: AnswerKey) -> tuple[list[Row], list[Row]]:
    provider_keys = sorted({r["ProviderKey"] for r in universe})
    added = set(rng.sample(provider_keys, max(1, round(len(provider_keys) * 0.03))))
    removable = [k for k in provider_keys if k not in added]
    removed = set(rng.sample(removable, max(1, round(len(provider_keys) * 0.02))))

    prior = [clone(r) for r in universe if r["ProviderKey"] not in added]
    for r in prior:
        r["LineCode"] = line_code(r)
    current = [clone(r) for r in universe if r["ProviderKey"] not in removed]

    answer.facts["professional"] = {
        "practitioners_new_this_month": len(added),
        "practitioners_gone_this_month": len(removed),
    }
    inject_professional_defects(rng, scaled, current, addresses, answer)
    assign_record_ids(rng, prior, "ProviderRecordID")
    assign_record_ids(rng, current, "ProviderRecordID")
    return prior, current


def inject_professional_defects(rng: random.Random, scaled: Callable[[float], int],
                                rows: list[Row], addresses: list[Row], answer: AnswerKey) -> None:
    key = "PracticeLocationKey"
    used: set[int] = set()
    next_key = max(r[key] for r in rows) + 1
    new_rows: list[Row] = []

    def take(count, predicate=None):
        return pick_rows(rng, rows, count, used, key, predicate)

    def fresh_key():
        nonlocal next_key
        next_key += 1
        return next_key - 1

    # Exact duplicates: the same location row loaded twice (or three times).
    for i, r in enumerate(take(scaled(150)), 1):
        group = f"PX-{i:04d}"
        tag(r, "exact_duplicate", group=group, role="original")
        for _ in range(2 if rng.random() < 0.1 else 1):
            c = clone(r)
            c["_tags"] = [{"kind": "exact_duplicate", "group": group, "role": "copy"}]
            new_rows.append(c)

    # Review duplicates: same grouping fields, different stable key, one meaningful difference.
    for i, r in enumerate(take(scaled(60)), 1):
        group = f"PR-{i:04d}"
        c = clone(r)
        c[key] = fresh_key()
        if rng.random() < 0.6:
            c["EffectiveDate"] = rand_date(rng, date(2024, 1, 1), date(2026, 7, 31))
            differs = "EffectiveDate"
        else:
            c["Phone"] = make_phone(rng, c["Borough"])
            differs = "Phone"
        tag(r, "review_duplicate", group=group, role="original", differs_in=differs)
        c["_tags"] = [{"kind": "review_duplicate", "group": group, "role": "variant", "differs_in": differs}]
        new_rows.append(c)

    # Legitimate multiples: same grouping fields, but a different network. Never a deletion.
    for i, r in enumerate(take(scaled(40)), 1):
        group = f"PL-{i:04d}"
        other = rng.choice([n for n, _ in vocab.NETWORKS if n != r["Network"]])
        c = clone(r)
        c[key] = fresh_key()
        c["Network"] = other
        tag(r, "legitimate_multiple", group=group, role="original", differs_in="Network")
        c["_tags"] = [{"kind": "legitimate_multiple", "group": group, "role": "variant", "differs_in": "Network"}]
        new_rows.append(c)

    # Missing required fields.
    for r in take(scaled(120)):
        tag(r, "missing_county", original=r["County"])
        r["County"] = ""
    for r in take(scaled(60)):
        tag(r, "missing_specialty", original=r["Specialty"])
        r["Specialty"] = ""
    for r in take(scaled(90)):
        tag(r, "missing_phone", original=r["Phone"])
        r["Phone"] = ""

    # Specialty / county pairs the placeholder rule says cannot exist.
    exclusions = vocab.SPECIALTY_COUNTY_EXCLUSIONS
    counties = {county for _, county in exclusions}
    for r in take(scaled(40), lambda r: r["County"] in counties):
        specialty = rng.choice([s for s, c in exclusions if c == r["County"]])
        tag(r, "invalid_specialty_county", original_specialty=r["Specialty"],
            specialty=specialty, county=r["County"])
        r["Specialty"] = specialty
        r["ProviderType"] = vocab.PROVIDER_TYPE_FOR_SPECIALTY[specialty]
        r["LimitationText"] = ""

    # School-based rows that lost their limitation text.
    for r in take(scaled(30), lambda r: r["Specialty"] == vocab.SCHOOL_BASED_SPECIALTY):
        tag(r, "missing_school_limitation")
        r["LimitationText"] = ""

    # ZIP codes that belong to a different borough than the row claims.
    for r in take(scaled(40)):
        other = rng.choice([b for b in vocab.BOROUGHS if b != r["Borough"]])
        tag(r, "zip_borough_mismatch", original_zip=r["ZIP"], zip_belongs_to=other)
        r["ZIP"] = rng.choice(vocab.BOROUGHS[other]["zips"])

    # Partially blank flags: no defined line code, and not the pipeline's call to make.
    for r in take(scaled(60), lambda r: r["LineA_Flag"] != ""):
        column = f"Line{rng.choice('ABCD')}_Flag"
        tag(r, "partial_flags", blank_column=column, original=r[column])
        r[column] = ""

    # The practitioner who must not appear, back in the feed at two locations.
    person = vocab.NAMED_EXCLUSION
    npi = make_npi(rng)
    provider_number = f"P{rng.randint(1_000_000, 9_999_999)}"
    provider_key = max(r["ProviderKey"] for r in rows) + 1
    for _ in range(2):
        a = rng.choice(addresses)
        row = {
            "ProviderKey": provider_key, "NPI": npi, "ProviderNumber": provider_number,
            "FirstName": person["FirstName"], "LastName": person["LastName"],
            "Specialty": person["Specialty"],
            "ProviderType": vocab.PROVIDER_TYPE_FOR_SPECIALTY[person["Specialty"]],
            "Source": "PracticeRosterFeed", **a, key: fresh_key(),
            "Network": "Harbor Network", "EffectiveDate": "2019-04-01",
            **make_flags(rng, all_blank_share=0.0), "PrintFlag": "1", "LineCode": "",
            "LimitationText": "",
        }
        tag(row, "named_exclusion", group="NE-0001", role="row")
        new_rows.append(row)
    answer.facts["named_exclusion"] = {**person, "NPI": npi, "ProviderNumber": provider_number}

    rows.extend(new_rows)


# ---------------------------------------------------------------------------
# Month derivation: service directory
# ---------------------------------------------------------------------------

def derive_service_months(rng: random.Random, scaled: Callable[[float], int], universe: list[Row],
                          used_phones: set[str], answer: AnswerKey) -> tuple[list[Row], list[Row], list[Row]]:
    named_name = vocab.NAMED_ORG["DisplayName"]
    org_keys = sorted({r["VendorKey"] for r in universe if r["DisplayName"] != named_name})
    added = set(rng.sample(org_keys, max(1, round(len(org_keys) * 0.03))))
    removable = [k for k in org_keys if k not in added]
    removed = set(rng.sample(removable, max(1, round(len(org_keys) * 0.02))))

    prior = [clone(r) for r in universe if r["VendorKey"] not in added]
    for r in prior:
        r["LineCode"] = line_code(r)
    current = [clone(r) for r in universe if r["VendorKey"] not in removed]

    answer.facts["service"] = {
        "organizations_new_this_month": len(added),
        "organizations_gone_this_month": len(removed),
    }
    deletion_list = inject_service_defects(rng, scaled, current, prior, used_phones, answer)
    assign_record_ids(rng, prior, "VendorRecordID")
    assign_record_ids(rng, current, "VendorRecordID")
    return prior, current, deletion_list


def inject_service_defects(rng: random.Random, scaled: Callable[[float], int], rows: list[Row],
                           prior: list[Row], used_phones: set[str], answer: AnswerKey) -> list[Row]:
    key = "ServiceLocationKey"
    used: set[int] = set()
    next_key = max(r[key] for r in rows) + 1
    next_vendor_key = max(r["VendorKey"] for r in rows) + 1
    next_address_key = max(r["AddressKey"] for r in rows) + 1
    new_rows: list[Row] = []

    def take(count, predicate=None):
        return pick_rows(rng, rows, count, used, key, predicate)

    def fresh_key():
        nonlocal next_key
        next_key += 1
        return next_key - 1

    def is_vision(r: Row) -> bool:
        return r["ServiceType"] == vocab.VISION_SERVICE_TYPE

    # A whole borough's vision listings vanished from the feed this month.
    dropped = [r for r in rows if is_vision(r) and r["Borough"] == "Staten Island"]
    rows[:] = [r for r in rows if not (is_vision(r) and r["Borough"] == "Staten Island")]
    answer.facts["vision_missing_borough"] = {
        "borough": "Staten Island", "service_type": vocab.VISION_SERVICE_TYPE,
        "prior_month_rows": sum(1 for r in prior if is_vision(r) and r["Borough"] == "Staten Island"),
        "current_month_rows": 0,
        "dropped_stable_keys": sorted(r[key] for r in dropped),
    }

    # One feed now sends a row per service line instead of a row per location.
    expanding = [r for r in rows if r["Source"] == vocab.EXPANDING_SOURCE]
    for r in expanding:
        group = f"SE-{r['AddressKey']}"
        used.add(r[key])
        tag(r, "source_expansion", section="changes", group=group, role="original")
        for service in vocab.EXPANDING_SOURCE_CURRENT_SERVICES:
            if service == r["ServiceType"]:
                continue
            c = clone(r)
            c["_tags"] = [{"kind": "source_expansion", "section": "changes", "group": group, "role": "added"}]
            c["ServiceType"] = service
            c[key] = fresh_key()
            used.add(c[key])
            new_rows.append(c)
    answer.facts["source_expansion"] = {
        "source": vocab.EXPANDING_SOURCE,
        "locations": len(expanding),
        "prior_month_rows": sum(1 for r in prior if r["Source"] == vocab.EXPANDING_SOURCE),
        "current_month_rows": len(expanding) * len(vocab.EXPANDING_SOURCE_CURRENT_SERVICES),
    }

    # A retired feed that is still arriving. Every row carries its exact source value.
    retired_orgs = []
    names = {r["DisplayName"] for r in rows}
    for _ in range(scaled(60)):
        borough = weighted_choice(rng, vocab.BOROUGH_WEIGHTS)
        retired_orgs.append({
            "VendorKey": next_vendor_key,
            "DisplayName": unique_org_name(rng, names, ["Med Supply", "Home Care", "Clinic"], borough),
            "FacilityType": rng.choice(["Equipment Supplier", "Home Care Agency", "Clinic"]),
            "NPI": make_npi(rng), "ProviderNumber": f"V{rng.randint(100_000, 999_999)}",
            "Network": "Harbor Network", "Source": vocab.RETIRED_SOURCE,
            "_home": borough, "_services": ["Durable Equipment", "Home Health Aide", "Outpatient"],
        })
        next_vendor_key += 1
    retired_rows = build_service_rows(rng, retired_orgs, used_phones, first_address_key=next_address_key,
                                      first_location_key=next_key)
    next_key += len(retired_rows)
    next_address_key += len(retired_rows)
    for r in retired_rows:
        r["LineCode"] = ""
        tag(r, "retired_source", source=vocab.RETIRED_SOURCE)
        used.add(r[key])
    new_rows.extend(retired_rows)
    answer.facts["retired_source"] = {"source": vocab.RETIRED_SOURCE, "rows": len(retired_rows)}

    # Organizations on the approved deletion list: every row of theirs goes.
    named_rows = [r for r in rows if r["DisplayName"] == vocab.NAMED_ORG["DisplayName"]]
    used.update(r[key] for r in named_rows)
    deletable = sorted({r["VendorKey"] for r in rows if r[key] not in used})
    deletion_list = []
    for i, vendor_key in enumerate(rng.sample(deletable, scaled(12)), 1):
        org_rows = [r for r in rows if r["VendorKey"] == vendor_key]
        for r in org_rows:
            tag(r, "approved_deletion", group=f"AD-{i:04d}", provider_number=r["ProviderNumber"])
            used.add(r[key])
        deletion_list.append({
            "DeletionID": i, "ProviderNumber": org_rows[0]["ProviderNumber"],
            "DisplayName": org_rows[0]["DisplayName"],
            "Reason": rng.choice(["Contract terminated", "Closed location",
                                  "Duplicate vendor record", "Requested removal"]),
            "ApprovedBy": "Directory owner",
            "ApprovedOn": rand_date(rng, date(2026, 8, 1), date(2026, 8, 31)),
        })

    # Exact address duplicates (these share a phone too, so they also show in the phone query).
    for i, r in enumerate(take(scaled(80)), 1):
        group = f"SX-{i:04d}"
        tag(r, "exact_duplicate", group=group, role="original", also_phone_duplicate=True)
        c = clone(r)
        c["_tags"] = [{"kind": "exact_duplicate", "group": group, "role": "copy", "also_phone_duplicate": True}]
        new_rows.append(c)

    # Review duplicates: same listing fields, one meaningful difference.
    for i, r in enumerate(take(scaled(30)), 1):
        group = f"SR-{i:04d}"
        c = clone(r)
        c[key] = fresh_key()
        if rng.random() < 0.5:
            c["EffectiveStart"] = rand_date(rng, date(2024, 1, 1), date(2026, 7, 31))
            differs = "EffectiveStart"
        else:
            c["Phone"] = make_phone(rng, c["Borough"], used_phones)
            differs = "Phone"
        tag(r, "review_duplicate", group=group, role="original", differs_in=differs)
        c["_tags"] = [{"kind": "review_duplicate", "group": group, "role": "variant", "differs_in": differs}]
        new_rows.append(c)

    # Legitimate multiples: same listing, different network.
    for i, r in enumerate(take(scaled(40)), 1):
        group = f"SL-{i:04d}"
        c = clone(r)
        c[key] = fresh_key()
        c["Network"] = rng.choice([n for n, _ in vocab.NETWORKS if n != r["Network"]])
        tag(r, "legitimate_multiple", group=group, role="original", differs_in="Network")
        c["_tags"] = [{"kind": "legitimate_multiple", "group": group, "role": "variant", "differs_in": "Network"}]
        new_rows.append(c)

    # Phone duplicates that are the same listing typed differently.
    name_variants = [lambda s: s.replace("Center", "Ctr"), lambda s: s.replace("Services", "Svcs"),
                     lambda s: s.replace(" ", "  ", 1), lambda s: s + " Inc"]
    street_variants = [lambda s: s.replace("Ave", "Avenue"), lambda s: s.replace("St", "Street"),
                       lambda s: s.replace("Blvd", "Boulevard"), lambda s: s.replace("Rd", "Road")]
    for i, r in enumerate(take(scaled(50)), 1):
        group = f"SP-{i:04d}"
        c = clone(r)
        c[key] = fresh_key()
        c["DisplayName"] = rng.choice(name_variants)(r["DisplayName"])
        c["Address1"] = rng.choice(street_variants)(r["Address1"])
        if c["DisplayName"] == r["DisplayName"] and c["Address1"] == r["Address1"]:
            c["DisplayName"] = r["DisplayName"] + " Inc"
        tag(r, "phone_duplicate_redundant", group=group, role="original")
        c["_tags"] = [{"kind": "phone_duplicate_redundant", "group": group, "role": "variant"}]
        new_rows.append(c)

    # Phone duplicates that are genuinely two sites sharing a central number.
    for i, r in enumerate(take(scaled(40)), 1):
        group = f"SQ-{i:04d}"
        c = clone(r)
        c[key] = fresh_key()
        a = make_address(rng, next_address_key, r["Borough"], used_phones)
        next_address_key += 1
        a["Phone"] = r["Phone"]  # deliberately shared: one switchboard, two sites
        c.update(a)
        tag(r, "phone_duplicate_legitimate", group=group, role="original")
        c["_tags"] = [{"kind": "phone_duplicate_legitimate", "group": group, "role": "second_site"}]
        new_rows.append(c)

    # Missing geography.
    for r in take(scaled(35)):
        tag(r, "missing_county", original=r["County"])
        r["County"] = ""
    for r in take(scaled(35)):
        tag(r, "missing_borough", original=r["Borough"])
        r["Borough"] = ""

    # Vision listings whose required first-line flag is not set.
    for r in take(scaled(12), is_vision):
        value = rng.choice(["", "0"])
        tag(r, "vision_flag_not_set", column="LineA_Flag", value=value)
        r["LineA_Flag"] = value

    # Vision listings with presentation problems.
    text_variants = [
        ("DisplayName", lambda s: s.replace(" ", "  ", 1)),
        ("DisplayName", lambda s: s + ","),
        ("DisplayName", lambda s: " " + s),
        ("Address1", lambda s: s.replace(" ", "  ", 1)),
    ]
    for r in take(scaled(15), is_vision):
        column, variant = rng.choice(text_variants)
        tag(r, "malformed_text", column=column, original=r[column])
        r[column] = variant(r[column])

    # The named organization with lines it should not carry.
    for r in rng.sample(named_rows, min(2, len(named_rows))):
        column = rng.choice(["LineB_Flag", "LineC_Flag"])
        tag(r, "named_org_nonzero_flag", column=column, display_name=r["DisplayName"])
        r[column] = "1"
    answer.facts["named_org"] = {**vocab.NAMED_ORG, "rows": len(named_rows),
                                 "must_be_zero": ["LineB_Flag", "LineC_Flag", "LineD_Flag"]}

    # Partially blank flags.
    for r in take(scaled(40), lambda r: r["LineA_Flag"] != "" and not is_vision(r)):
        column = f"Line{rng.choice('BCD')}_Flag"
        tag(r, "partial_flags", blank_column=column, original=r[column])
        r[column] = ""

    rows.extend(new_rows)
    return deletion_list


# ---------------------------------------------------------------------------
# Month derivation: pharmacies and reference tables
# ---------------------------------------------------------------------------

def derive_pharmacy_months(rng: random.Random, universe: list[Row],
                           answer: AnswerKey) -> tuple[list[Row], list[Row]]:
    prior = [clone(r) for r in universe]
    current = [clone(r) for r in universe]
    used: set[int] = set()
    # Always include some pharmacies with no languages, so the comma-only pattern
    # (", , , ,") that must normalize to blank is present at every scale.
    blank = pick_rows(rng, current, max(1, round(len(current) * 0.02)), used, "PharmacyRecordID",
                      lambda r: r["SpokenLanguages"] == "")
    rest = pick_rows(rng, current, round(len(current) * 0.35) - len(blank), used, "PharmacyRecordID")
    for r in blank + rest:
        languages = [s for s in r["SpokenLanguages"].split(", ") if s]
        if not languages:
            malformed = ", , , ,"
        elif rng.random() < 0.8 or len(languages) < 2:
            malformed = ", ".join(languages + [""] * (5 - len(languages))).rstrip()
        else:
            rest = ", ".join(languages[1:])
            malformed = rng.choice([
                f"{languages[0]},,{rest}, ,",
                f" , {' , '.join(languages)}",
                f"{languages[0]}, {rest} ,,",
                f",{languages[0]}, {rest},",
            ])
        expected = normalize_languages(malformed)
        assert expected == r["SpokenLanguages"], (malformed, expected, r["SpokenLanguages"])
        tag(r, "malformed_languages", original=malformed, expected=expected,
            comma_only=(expected == ""))
        r["SpokenLanguages"] = malformed
    return prior, current


def derive_reference_months(rng: random.Random, universe: list[Row], id_column: str,
                            added: int, removed: int) -> tuple[list[Row], list[Row]]:
    keys = [r[id_column] for r in universe]
    new = set(rng.sample(keys, added))
    gone = set(rng.sample([k for k in keys if k not in new], removed))
    prior = [clone(r) for r in universe if r[id_column] not in new]
    current = [clone(r) for r in universe if r[id_column] not in gone]
    return prior, current


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_sqlite(path: Path, tables: dict[str, tuple[list[str], list[Row]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    try:
        for name, (columns, rows) in tables.items():
            parts = []
            for i, c in enumerate(columns):
                kind = "INTEGER" if c.endswith(("ID", "Key")) else "TEXT"
                if i == 0 and kind == "INTEGER":
                    kind += " PRIMARY KEY"
                parts.append(f'"{c}" {kind}')
            con.execute(f'CREATE TABLE "{name}" ({", ".join(parts)})')
            placeholders = ", ".join("?" for _ in columns)
            con.executemany(f'INSERT INTO "{name}" VALUES ({placeholders})',
                            ([r[c] for c in columns] for r in rows))
        con.commit()
    finally:
        con.close()


def write_csv(path: Path, columns: list[str], rows: Iterable[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate(out: Path, seed: int = DEFAULT_SEED, scale: float = 1.0,
             sample_rows: int = 40, quiet: bool = False) -> AnswerKey:
    rng = random.Random(seed)
    answer = AnswerKey(seed, scale)

    def scaled(base: float) -> int:
        return max(1, round(base * scale))

    # Universe. One shared set keeps every phone unique unless a defect shares it on purpose.
    used_phones: set[str] = set()
    practitioners = build_practitioners(rng, scaled(8_800))
    addresses = build_practice_addresses(rng, scaled(5_200), used_phones)
    professional_universe = build_professional_rows(rng, practitioners, addresses)
    organizations = build_organizations(rng, scaled(2_150), staten_island_vision_orgs=scaled(12))
    service_universe = build_service_rows(rng, organizations, used_phones)
    pharmacy_universe = build_pharmacies(rng, scaled(600), used_phones)
    other_universe = build_facility_reference(rng, scaled(200), "FacilityRefID")
    managed_universe = build_facility_reference(rng, scaled(150), "FacilityID", managed_care=True)

    # Two months
    prof_prior, prof_current = derive_professional_months(rng, scaled, professional_universe,
                                                          addresses, answer)
    svc_prior, svc_current, deletion_list = derive_service_months(rng, scaled, service_universe,
                                                                  used_phones, answer)
    pharm_prior, pharm_current = derive_pharmacy_months(rng, pharmacy_universe, answer)
    other_prior, other_current = derive_reference_months(rng, other_universe, "FacilityRefID",
                                                         scaled(5), scaled(3))
    managed_prior, managed_current = derive_reference_months(rng, managed_universe, "FacilityID",
                                                             scaled(4), scaled(2))

    # Answer key
    collect_tags(prof_current, "ProfessionalProviderSource", "ProviderRecordID", "PracticeLocationKey", answer)
    collect_tags(svc_current, "AdditionalServiceSource", "VendorRecordID", "ServiceLocationKey", answer)
    collect_tags(pharm_current, "PharmacyPublicationDirectory", "PharmacyRecordID", "PharmacyRecordID", answer)
    answer.counts = {
        "prior_month": {
            "ProfessionalDirectory": len(prof_prior), "ServiceDirectory": len(svc_prior),
            "PharmacyPublicationDirectory": len(pharm_prior),
            "OtherFacilityReference": len(other_prior), "ManagedCareFacilitySource": len(managed_prior),
        },
        "current_source": {
            "ProfessionalProviderSource": len(prof_current), "AdditionalServiceSource": len(svc_current),
            "PharmacyPublicationDirectory": len(pharm_current),
            "OtherFacilityReference": len(other_current), "ManagedCareFacilitySource": len(managed_current),
        },
        "ApprovedDeletionList": len(deletion_list),
    }
    answer.facts["specialty_county_exclusions"] = [list(p) for p in vocab.SPECIALTY_COUNTY_EXCLUSIONS]
    answer.facts["school_limitation"] = {"specialty": vocab.SCHOOL_BASED_SPECIALTY,
                                         "required_text": vocab.SCHOOL_LIMITATION_TEXT}

    # Databases
    write_sqlite(out / "sources" / "PractitionerFeed.sqlite", {
        "ProfessionalProviderSource": (PROFESSIONAL_COLUMNS, prof_current),
    })
    write_sqlite(out / "sources" / "ServiceVendorFeed.sqlite", {
        "AdditionalServiceSource": (SERVICE_COLUMNS, svc_current),
        "OtherFacilityReference": (FACILITY_REF_COLUMNS, other_current),
        "ManagedCareFacilitySource": (MANAGED_CARE_COLUMNS, managed_current),
    })
    write_sqlite(out / "DirectoryQualityHub.sqlite", {
        "ProfessionalDirectory": (PROFESSIONAL_COLUMNS, prof_prior),
        "ServiceDirectory": (SERVICE_COLUMNS, svc_prior),
        "PharmacyPublicationDirectory": (PHARMACY_COLUMNS, pharm_current),
        "OtherFacilityReference": (FACILITY_REF_COLUMNS, other_prior),
        "ManagedCareFacilitySource": (MANAGED_CARE_COLUMNS, managed_prior),
        "ApprovedDeletionList": (DELETION_LIST_COLUMNS, deletion_list),
    })

    # CSV copies
    prior_tables = {
        "ProfessionalDirectory": (PROFESSIONAL_COLUMNS, prof_prior),
        "ServiceDirectory": (SERVICE_COLUMNS, svc_prior),
        "PharmacyPublicationDirectory": (PHARMACY_COLUMNS, pharm_prior),
        "OtherFacilityReference": (FACILITY_REF_COLUMNS, other_prior),
        "ManagedCareFacilitySource": (MANAGED_CARE_COLUMNS, managed_prior),
    }
    current_tables = {
        "ProfessionalProviderSource": (PROFESSIONAL_COLUMNS, prof_current),
        "AdditionalServiceSource": (SERVICE_COLUMNS, svc_current),
        "PharmacyPublicationDirectory": (PHARMACY_COLUMNS, pharm_current),
        "OtherFacilityReference": (FACILITY_REF_COLUMNS, other_current),
        "ManagedCareFacilitySource": (MANAGED_CARE_COLUMNS, managed_current),
        "ApprovedDeletionList": (DELETION_LIST_COLUMNS, deletion_list),
    }
    for name, (columns, rows) in prior_tables.items():
        write_csv(out / "archive" / PRIOR_CYCLE / f"{name}.csv", columns, rows)
    for name, (columns, rows) in current_tables.items():
        write_csv(out / "csv" / CYCLE / f"{name}.csv", columns, rows)
        write_csv(out / "samples" / f"{name}.csv", columns, rows[:sample_rows])

    checklist = [dict(zip(CHECKLIST_COLUMNS, note, strict=True)) for note in vocab.ADVISORY_CHECKLIST]
    write_csv(out / "advisory_checklist.csv", CHECKLIST_COLUMNS, checklist)

    with (out / "answer_key.json").open("w", encoding="utf-8", newline="\n") as f:
        json.dump(answer.to_dict(), f, indent=2)

    if not quiet:
        report(answer, out)
    return answer


def report(answer: AnswerKey, out: Path) -> None:
    print(f"Generated into {out}  (seed {answer.meta['seed']}, scale {answer.meta['scale']})")
    print("\nRows by table")
    for month, counts in answer.counts.items():
        if isinstance(counts, dict):
            for table, n in counts.items():
                print(f"  {month:15s} {table:30s} {n:>7,}")
        else:
            print(f"  {'hub':15s} {month:30s} {counts:>7,}")
    for section in ("defects", "changes"):
        print(f"\nPlanted {section}")
        for kind, n in sorted(answer.to_dict()["summary"][section].items()):
            print(f"  {kind:32s} {n:>5}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate the synthetic directory databases.")
    parser.add_argument("--out", default="demo", help="output folder (default: demo)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--scale", type=float, default=1.0,
                        help="size multiplier; 1.0 is ~20k professional rows, 0.05 is a quick test set")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    generate(Path(args.out), seed=args.seed, scale=args.scale, quiet=args.quiet)
    return 0
