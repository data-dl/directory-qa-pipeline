# Assumptions

Every default the generator and pipeline rely on, where it comes from (the project's
design brief, public knowledge, or a value chosen for this project) and whether it is
fixed or still open to change. Correct a row here and the generator follows.

## Wording rules

The repository keeps a neutral vocabulary: a short list of terms is banned in
code, config, data, docs and tests. The list lives in one place, `tests/test_wording.py`,
and that test fails if any of them appears anywhere else. Coverage is described with
four 0/1 **flags** (`LineA_Flag` ... `LineD_Flag`) and a combined **line code**.

## Data shape

| Area | Assumption | Source | Status |
|---|---|---|---|
| Professional rows | ~20,000, several practice locations per practitioner | design choice | fixed |
| Service (vendor) rows | ~6,000 | design choice | fixed |
| Pharmacy rows | ~600; the hub's `PharmacyPublicationDirectory` already holds the current month's staged rows (with malformed languages) when the cycle begins, and the archive holds last month's clean version | invented | open |
| Other facility reference / managed-care facility source | ~200 / ~150 | invented | open |
| Approved deletion list | a hub table `ApprovedDeletionList` keyed by organization `ProviderNumber`; every row of a listed organization is removed | design brief ("approved deletion lists") | invented shape |
| Cycles | two: `2026-08` archive and `2026-09` current, with realistic month-over-month change including one source feed that expanded across coverage lines | invented | open |
| Geography | five NYC boroughs, their counties and ZIP prefixes (public knowledge); one borough deliberately missing vision services | public | fixed |
| NPI | fake, passes the real check-digit test | public algorithm | fixed |
| Networks, sources | invented names; one source is a retired feed that must be removed | invented | open |

## Coverage flags

| Area | Assumption | Source | Status |
|---|---|---|---|
| Flags | four fields `LineA_Flag` … `LineD_Flag`, each 0 or 1, sometimes stored as text `"0"` / `"1"`, sometimes blank | design brief | fixed shape, invented names |
| Combined field | `LineCode`, a four-character string such as `1010`; blank when all four flags are blank; blank source flags are never converted to 0 without an explicit rule | design brief | fixed |

## Rules

| Area | Assumption | Source | Status |
|---|---|---|---|
| Duplicate grouping key (professional) | `LastName`, `FirstName`, `Address1`, `Address2`, `Specialty`, `NPI` | design choice | fixed |
| Duplicate grouping key (service, address) | `DisplayName`, `Address1`, `Address2`, `ZIP`, `ServiceType` - an organization offering several services at one address is several listings, not a duplicate | invented | open |
| Duplicate grouping key (service, phone) | `Phone` | design brief | fixed |
| Specialty availability by county | a small table of specialties with no listings in certain counties (placeholder: Care Management has none in Richmond County); any row with such a pair is invalid | design choice | placeholder |
| School limitation text | rows with `Specialty = School-Based Health` must have a `LimitationText` mentioning "school" | invented | open |
| Vision services | identified by `ServiceType = Vision` | design brief | fixed |
| Named exclusion | one invented practitioner who must not appear, matched on NPI, then provider number, then full name | design brief | fixed |
