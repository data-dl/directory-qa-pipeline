# The Guidebook

*How this project works and why it is built the way it is.*

This is written to be read once from the top, then kept nearby. Part 2 defines every
technical word the rest of the document uses. Parts 7 and 8 explain the design choices
and what building it taught.

---

## Part 1 - The story in one page

The scenario: every month a health-plan directory team refreshes two lists: **individual
practitioners** (doctors, therapists, nurse practitioners - and every address each one
practises at) and **facilities and vendors** (hospitals, clinics, pharmacies, vision
centers, transport companies, home-care agencies, equipment suppliers). The lists arrive
from two source systems, land in a central repository, get cleaned and checked, get
compared with last month, and are then handed off to a separate step that produces the
printed directory for each of the five boroughs.

In the scenario the platform is Microsoft Access, and the checks are spread across saved
queries, buttons on a form, and a spreadsheet of notes ("this provider should no longer
appear"). Several steps need a person's judgment. Some of the Access routines pop up dialog boxes and take
minutes with no visible sign of life.

This project is the engineering that goes around that cycle - without replacing the
platform:

- Every setting, name, path and rule lives in configuration files, not in code.
- The code talks to the database through one small interface, so the same pipeline runs
  against Access or against SQLite.
- Every run starts by copying the database and works on the copy. Production is touched
  once, at the very end, and only after a verified backup, a readiness review, and an
  exact authorization phrase.
- Every check is a declared rule with a severity. Blocking rules must pass; advisory
  rules are reported; reminders are for a future month.
- Duplicates are classified, never deleted on a name-and-address match. Only a row that is
  identical in every meaningful field *and* shares a stable identifier is removed
  automatically.
- Every run leaves a manifest, a summary and a CSV for every finding.
- The last step is a hard stop before borough generation, which stays manual on purpose.

The data in this repository is entirely synthetic. A generator invents ~20,000
practitioner rows and ~6,000 service rows from a fixed seed, plants twenty kinds of defect
in known places, and writes an answer key. The tests grade the pipeline against that key.

---

## Part 2 - The words

### Git and GitHub

**Repository (repo)** - a project folder whose entire history is kept: every version of
every file, with a note on what changed and why. GitHub is a website that hosts repos.
The account here is `data-dl`; this project is the repo `directory-qa-pipeline` inside it.

**Commit** - one saved snapshot of the repo with a message. The history is the list of
commits.

**Push** - send your local commits up to GitHub.

**CI (continuous integration)** - a robot that runs the tests every time code is pushed
and marks the commit with a green check or a red X. Here it is GitHub Actions; the
recipe is in `.github/workflows/tests.yml`.

**`.gitignore`** - the list of files git must not track. Generated databases, backups and
run folders are ignored; they are rebuilt on demand.

### Databases

**SQLite** - a free database that lives in a single file and comes built into Python. No
server, nothing to install. It is the closest stand-in for an Access file: one file, one
set of tables, SQL that is nearly the same.

**Microsoft Access** - the target platform. Also a single-file database, but with a
graphical front end (forms, buttons, macros) and its own query engine (Jet/ACE).

**Saved query** - in Access, a named query stored inside the database file (a
*QueryDef*). SQLite has no such thing, so this project keeps the same idea in
`config/queries.yaml`: a name mapped to the SQL it stands for. Stages and rules refer to
queries by name only.

**Table, row, column** - as usual. Two kinds of column matter especially here:

- **Record id** - the autonumber Access assigns to each row (`ProviderRecordID`,
  `VendorRecordID`). It changes every time a table is reloaded, so it is useless for
  remembering a row from one month to the next.
- **Stable key** - a column that identifies the same real-world thing across reloads
  (`PracticeLocationKey`, `ServiceLocationKey`). Automatic deletion is allowed only when a
  stable key exists and matches; without one, the pipeline only reports.

**Hash (SHA-256)** - a fingerprint of a file's bytes. Change one byte and the fingerprint
changes completely. Two files with the same hash are identical. Used to verify backups and
to notice when production changed behind the pipeline's back.

**Signature** - the same idea applied to a table's *contents* rather than a file:
a hash over every row, in a fixed order. Two tables with the same signature hold the same
rows.

**Seed** - the starting number for a random-number generator. The same seed gives the
same "random" sequence every time, so the synthetic data is reproducible byte for byte.

### Software design

**Interface** - a written promise of what a piece of code can do: a short list of named
operations, with no say about *how*. Like a wall outlet: every appliance plugs into the
same shape and does not care where the electricity came from.

**Backend** - the thing behind the interface that actually does the work: the power
plant. `SqliteBackend` keeps the promise using SQLite; `AccessBackend` keeps the same
promise using DAO (see below). The pipeline stages only ever see the interface.

**Dependency injection** - the plain habit of *handing* a function the objects it needs
(the backend, the config) instead of letting it build them itself. It is what makes it
possible to hand a stage a SQLite backend in a test and an Access backend in production.

**Refactor** - rearranging code so it does exactly the same thing but is organized
better. If behaviour changes, it was not a refactor.

**Config (configuration)** - a plain text file of settings the code reads at startup:
paths, table names, which query implements which rule, how many backups to keep.
`config/demo.yaml` is the environment; `config/rules.yaml` is the rule registry;
`config/queries.yaml` is the query library. YAML is the format - readable text with
indentation, the standard for declarative config in data tooling.

**Idempotent** - running it twice has the same effect as running it once. An elevator
button is idempotent; pressing it again does not summon a second elevator. Each stage
checks what has already been done before doing anything.

**Dry run** - a run that does everything except change production. Here a dry run does
the *entire* cycle on a working copy and reports exactly what a real run would do.

**Working copy** - the copy of the production database that a run actually edits. It
lives in the run folder. Production is overwritten by it only in the final `promote`
stage, and only when every condition holds.

**Manifest** - the machine-readable record of one run (`manifest.json`): every stage,
its status, its counts, its files, the backup path, the readiness verdict.

**Evidence** - the CSVs a run writes for every finding: the duplicate groups, the rows
behind every failing rule, the old and new value of every changed language string.

**Answer key** - `demo/answer_key.json`: the generator's list of every defect it planted,
by record id. The tests compare the pipeline's findings with it.

**Decision log** - CSVs in `config/decisions/` where a person records what to do about a
duplicate group the pipeline could not resolve. Keyed by a hash of the group's content, so
the decision reapplies automatically when the same group returns unchanged.

### Windows and Access automation

**DAO (Data Access Objects)** - Microsoft's library of ready-made commands for talking
to an Access database *file* directly: open it, read a table, run a saved query, count
rows. A "DAO call" is one of those commands. The Access program window does not need to
be open. Think of it as a phone line straight to the file.

**COM (Component Object Model)** - Windows' built-in way for one program to
remote-control another. Opening the actual Access application from Python and telling it
"run this macro" is COM. Remote control for the *program*, versus DAO's phone line to the
*file*. Both are needed: reading a table is faster through the file; a macro that pops up
dialog boxes only runs inside the program.

**UI Automation** - the part of Windows that lets a program see what is on screen
(windows, buttons, dialog boxes) and press them - the same plumbing screen readers use.
"Physical clicks" (moving the mouse to a spot and clicking) are the last resort when even
that fails.

**Runner** - the second interface in the design, for the interactive parts: run a macro,
click a form button, wait through a long operation, watch for dialogs. Built here as a
*dialog policy* (which dialogs may be answered, and how), a *watchdog* (slow versus
stalled), and a *scripted runner* that plays back declared dialogs so the policy is
tested without Access present. The Access implementation - COM to run macros, UI
Automation to find dialogs - is the next phase.

### This pipeline's own vocabulary

**Cycle** - one month's run of the whole process, named by month (`2026-09`).

**Stage** - one step of the pipeline. A function that takes the run context and returns a
record of what it did.

**Blocking / advisory / reminder** - the three rule severities. Blocking rules must pass
(or be explicitly accepted) before the verdict can be READY. Advisory rules are reported.
Reminders have no query at all; they are notes for a future cycle.

**Zero-row check / presence check / grouped report** - the three things a rule can
expect. "This query must return nothing" (no blank counties). "This query must return
something" (vision listings exist in Staten Island). "This is a listing for a person to
read; it cannot fail" (hospital rows by network and line code).

**Coverage lines and the line code** - four 0/1 flags (`LineA_Flag` … `LineD_Flag`)
saying which lines of coverage a listing belongs to, and a derived four-character code
(`1010`) that combines them. Blank flags are never turned into zeros; a row with *some*
flags blank has no defined code and is exported for a business decision.

**Promote** - the final stage: copy the working copy over production. Requires apply
mode, the exact authorization phrase, a verified backup from this run, a READY verdict,
and production's hash unchanged since the run began.

**Authorization phrase** - the exact text a person must supply to allow promotion:
`APPLY <cycle> TO <repository file name>`. It is printed by `python -m dirqa phrase`.

---

## Part 3 - The map

```
directory-qa-pipeline/
  README.md                 what it is and how to run it
  ASSUMPTIONS.md            every invented default, with source and status
  config/
    demo.yaml               paths, table names, transfers, duplicate settings
    queries.yaml            the saved-query library (name -> SQL)
    rules.yaml              the rule registry (severity, expectation, query, origin)
    decisions/              decision logs for duplicate groups (person-written)
    accepted_findings.example.yaml   template for owner-accepted blocking failures
  dirqa/                    the pipeline package
    config.py               loads demo.yaml into a Config object
    queries.py              the QueryLibrary
    context.py              starts a run: working copy, backends, manifest
    pipeline.py             stage order and stop rules
    state.py                completion markers that survive between runs
    cli.py                  python -m dirqa run | rules | phrase
    backends/
      base.py               the Backend interface (the outlet)
      sqlite.py             SqliteBackend (the portable power plant)
      access.py             AccessBackend - documented stub mapping each method to DAO
    runners/
      base.py               DialogSpec, ActionSpec, DialogPolicy, the Runner interface
      watchdog.py           slow-versus-stalled detection with injectable clock
      scripted.py           ScriptedRunner: actions as callables, dialogs from a script
    rules/registry.py       Rule, load_rules, evaluate
    evidence/manifest.py    StageRecord, Manifest, summary.md rendering
    stages/                 one file per stage, in the order they run
  synth/                    the synthetic-data generator and answer key
  demo/                     generated databases (ignored) and committed samples
  docs/
    guidebook.md            this document
    sample_run/             one real run's summary, manifest and evidence
  tests/                    69 tests; CI runs ruff and pytest on every push
```

---

## Part 4 - How data flows

```
 SOURCES (read-only)                        REPOSITORY
 +----------------------------+             +--------------------------------+
 | PractitionerFeed           |             | DirectoryQualityHub            |
 |   ProfessionalProviderSource -----+      |   ProfessionalDirectory        |
 +----------------------------+      |      |   ServiceDirectory             |
 | ServiceVendorFeed          |      |      |   PharmacyPublicationDirectory |
 |   AdditionalServiceSource  -------+----> |   OtherFacilityReference       |
 |   OtherFacilityReference   -------+      |   ManagedCareFacilitySource    |
 |   ManagedCareFacilitySource ------+      |   ApprovedDeletionList         |
 +----------------------------+             +--------------------------------+
                                                     |
                start of run: copy ----------------> |  runs/<cycle>/<run>/work/   (working copy)
                                                     |     every stage edits this
                                                     |
                promote (apply mode only) <--------- +  copied back over production
                                                        after backup + READY + phrase
```

The sources are never written. Production is written once, by `promote`. Everything in
between happens on the working copy, which is deleted from older runs to save disk (never
from failed runs, which are kept for inspection).

---

## Part 5 - A run, stage by stage

Each stage records a status: `completed`, `skipped` (nothing to do - the sign of
idempotency), `dry-run`, `blocked`, or `failed`. The first three stages stop the run on
failure; everything after them records its result and continues, so one pass collects
every finding.

**1. preflight** - Do all three database files exist? Is there a lock file beside any of
them? Inventory every table and its row count, every file's size, modification time and
hash. Check that every table the config names, every source table the transfers name,
and every query the rules and duplicate reviews name actually exists. Write
`preflight.json`. Stop if anything expected is missing.

**2. backup** - Close every handle on production, hash it *now*, copy it to
`demo/backups/<name>_<cycle>_<run>.sqlite`, hash the copy, compare hash and size. Record
the path in the manifest as "this restores the state before this cycle". Delete backups
beyond the retention count. Stop if the copy does not verify. Done in every mode, because
a dry run should rehearse the real thing.

**3. transfer** - For each declared transfer: compare the source and target columns
(stop on mismatch); skip if a completion marker from a promoted run says this exact source
was already loaded into this exact production file, or if the target already holds the
source rows verbatim; otherwise delete-and-load, then require the loaded count to equal
the source count exactly. Write `transfer.json`.

**4. professional_duplicates** - Run the official duplicate query. Split each group by the
fields whose difference means a different listing (NPI, provider number, network, source).
Classify each remaining partition: *exact* (delete the copies, keep the lowest record id),
*likely redundant*, or *review*. Apply any logged decisions. Export every candidate row
and every group with its reason and content hash. Rerun the official query and report what
remains.

**5. service_cleanup** - Export, then delete, every row of every organization on the
approved deletion list (matched on provider number) and every row whose Source is exactly
a retired feed's name. Reconcile: rows before minus deleted must equal rows after.

**6. service_duplicates** - The address review, then the phone review on what remains.
Same classifier, different settings: for phone groups, a different address key means a
different site (legitimate), while the same keys with different spelling means likely
redundant. Nothing is deleted here except exact copies.

**7. line_codes** - For every row with a blank line code: all four flags present, write
the concatenation; all four blank, leave blank; some blank, export as "needs a rule" and
write nothing. Then a grouped count of codes per table, for a person to read.

**8. pharmacy_languages** - Run the malformed-language query. For each hit: split at
commas, trim, drop empties, keep the rest in order, rejoin with ", ". Export old and new.
Update. Rerun the query; expect zero.

**9. quality_checks** - Evaluate every rule in the registry. Export the results table and
the rows behind every non-passing rule. Read the informal checklist and classify each
note: HIGH (translated into a blocking rule that is failing), CLEAR (blocking and
passing), REVIEW (advisory, or not translated at all), REMINDER.

**10. comparison** - Totals and breakdowns (source, borough, facility type, service type,
network) against last month's archive, with differences and percentages. For each source,
rows per distinct location - so a feed that quadrupled by sending one row per service line
is explained as "rows per location rose 1.0 → 4.0", not reported as new sites.

**11. readiness** - Every condition the directory must meet, as a yes/no with a detail:
transfer done, no unresolved duplicate groups, blocking rules clear or accepted, pharmacy
QA clear, line codes populated, retired sources gone. Advisory findings listed, not
counted. Verdict READY or NOT READY. Then the explicit note: stopped before borough
generation.

**12. promote** - In a dry run: record what would happen and print the exact command to
do it. In apply mode: require the phrase, the verified backup, the READY verdict and an
unchanged production hash; copy the working copy over production; verify the hash; write
the cycle's completion markers.

**Where the runner fits.** On SQLite, the cleanup, line-code and language stages are
plain SQL, so they run directly. On Access, the same three stages go through the runner:
the stage asks it to run the platform's own routine (`RunServiceDirectoryCleanup`,
`PopulateProfessionalLineCodes`, ...), the runner answers the dialogs declared in config,
pauses on any other, and watches the routine against its declared ceiling. The stage
logic and the evidence it writes do not change; only who does the work does.

On the demo data, a dry run ends **NOT READY** - by design. The pipeline removes 243 exact
duplicate copies, 166 rows from the deletion list and the retired feed, populates 24,307
line codes and fixes 210 language strings; it then reports the things only a person can
fix: 120 blank counties, 60 blank specialties, 90 blank phones, 40 impossible
specialty/county pairs, a practitioner who should not be there, a borough with no vision
listings, and 156 duplicate groups that need a decision.

---

## Part 6 - The safety design

The specification listed eight principles. Where each one lives:

| Principle | Where |
|---|---|
| Analysis mode by default | `run` is a dry run unless `--apply` is given; even then, only `promote` can touch production |
| Exact authorization for destructive actions | `--authorize` must equal `Config.authorization_phrase` character for character |
| Idempotency | every stage checks state first: transfer markers and signatures, empty official queries, zero malformed values, zero rows needing a code |
| State-based checkpoints | counts, signatures, file hashes, completion markers and the manifest together - never a hardcoded count |
| Clear separation of work | config / backends / rules / evidence / stages are separate packages; stages never import a database driver |
| Safety | deletion only by exact identifier: record ids inside an exact group, provider numbers on the deletion list, the exact Source value for a retired feed |
| Auditability | manifest.json, summary.md, one CSV per finding, backup path, counts before and after, every note |
| Recovery | the backup stage records which file restores the pre-cycle state; promote refuses if production changed during the run |

---

## Part 7 - Design decisions and why

**Why SQLite in the repository, when the target platform is Access?**
Because a reviewer cannot be assumed to have Windows and Access, and because the stages
should never know which database they are talking to. SQLite is the closest free
stand-in - one file, no server, nearly the same SQL - and it ships inside Python. The
backend interface is the design; SQLite is the portable proof that it holds.

**Why is the run done on a working copy instead of editing production stage by stage?**
Three reasons. A dry run can then do the *whole* cycle and show its full effect. Production
changes at most once, atomically, at the end. And if any stage fails, production is
untouched - there is no half-cleaned state to recover from.

**Why hash production twice - at the start and again just before promoting?**
The first hash is the baseline; the second proves nobody else wrote to the file while the
run was in progress. If they did, promoting would silently discard their change.

**Why is the backup compared with a hash taken immediately before copying, rather than a
hash from the preflight inventory?**
Because opening and closing the database can rewrite internal metadata even when no table
changes (this is documented Access behaviour). A hash from earlier in the session can be
stale; the comparison must be against the file's state at the instant of copying.

**Why are rules in YAML instead of Python?**
A rule is a business decision, not an algorithm: which query, what counts as a pass, how
much it matters. Keeping them in a data file means the registry can be reviewed by someone
who does not read Python, a new note from the business owner becomes a new entry rather
than new code, promotion from advisory to blocking is a one-word edit, and the file's git
history is the record of when each rule started to bind. This is the same idea as test
severity in dbt or an expectation suite in Great Expectations.

**Why are the official duplicate queries the source of candidates, rather than a smarter
grouping written in Python?**
Because the official query is the agreed definition of "duplicate" and the thing whose
result the team is accountable for. The pipeline's job is to make that result tractable -
classify, explain, delete only the certain cases - not to substitute its own opinion of
what a duplicate is.

**Why never delete on a name-and-address match?**
Two practitioners can share a name; one practitioner can legitimately appear twice at one
address (two networks, two sources). Only a row identical in every meaningful field *and*
sharing a stable identifier is provably the same row loaded twice. Everything else is a
judgment, and judgments are exported, decided by a person, and logged.

**Why key the decision log by a content hash instead of by record id?**
Record ids are reassigned every reload, so a decision keyed by them would be meaningless
next month. The hash covers the grouping and compared fields, so the same group returning
unchanged reapplies the decision, and a group that changed is surfaced again.

**Why are blank flags never turned into zeros?**
Blank and zero mean different things: "not set" versus "no". Converting silently would
invent a business fact. The pipeline populates codes only for rows where all four flags
are present, leaves all-blank rows blank (legitimate), and exports the partial rows for a
rule that only the business can write.

**Why translate the checklist rather than run it as free text?**
Because a note like "confirm vision services are included for Staten Island" is actually
two checks - a presence test (at least one row) and an exception test (rows with the flag
not set) - and they can pass or fail independently. Translating makes the distinction
explicit and testable; classifying the notes shows which ones have not been translated
yet.

**Why stop before borough generation?**
Borough generation runs macros that take minutes, pop dialogs, and produce the published
output. Mixing that with repository cleanup in one destructive pass would mean one failure
could leave both half-done. The pipeline ends with a readiness verdict and a hard stop;
borough generation is a separate phase, run one borough at a time, by a person.

**Why a completion marker for transfers, when the signature comparison already exists?**
After a promoted run, production holds *cleaned* data while the sources still hold raw
rows, so "target identical to source" can no longer tell whether the transfer happened -
and re-importing would undo the cleaning. The marker records which source signature was
loaded into which production file (by hash). Restore production from a backup and the
marker no longer applies, which is exactly right: the restored file is pre-transfer.

---

## Part 8 - Problems hit while building, and what they taught

Four bugs found while building this, and the lesson from each.

**Phone numbers collided by chance.** The first generator gave every location a random
555 number. With ~6,000 rows over ~40,000 possible numbers, birthday-paradox math produces
hundreds of accidental matches - and the phone-duplicate review drowned in them. The fix
was to make every phone unique unless a defect shares it on purpose. Lesson: synthetic
data has to be *shaped* like the real thing, including what is rare.

**The classifier called a whole group "legitimate" when only part of it was.** An
official phone group might hold a location's two service lines plus one redundant copy.
Because *something* in the group differed in service type, the whole group was waved
through, and 15 of the 50 planted redundant copies went unreported. The fix: partition
each official group by the legitimate-difference fields first, then classify each
partition. Lesson: classify at the level where the question is actually asked.

**Decisions stopped applying after the first promotion.** The decision-log hash covered
every column. The line-code stage runs *after* the duplicate review, so the second run's
rows had a populated code, the hashes changed, and every logged decision was ignored. The
fix: hash only the grouping and compared fields. Lesson: a key that says "has this
changed?" must cover only the things whose change should matter.

**The second run re-imported raw data over cleaned data.** The transfer's "already done?"
check compared the target with the source. After a promotion, production was cleaner than
the source, so the check said "not done" and reloaded the raw rows, undoing everything.
The fix was the completion marker tied to the production hash. Lesson: "is it done?" and
"does it match?" are different questions once a process changes what it loaded.

---

## Part 9 - Running it and reading the output

```bash
python -m synth --out demo                     # build the synthetic databases (1-2 s)
python -m dirqa run --config config/demo.yaml  # dry run: full cycle on a working copy
python -m dirqa rules --config config/demo.yaml
python -m dirqa phrase --config config/demo.yaml
python -m dirqa run --config config/demo.yaml --apply --authorize "APPLY 2026-09 TO DirectoryQualityHub.sqlite"
```

A run prints one line per stage and the readiness verdict, then writes
`runs/<cycle>/<run>/`:

- `summary.md` - the human-readable account (start with this)
- `manifest.json` - the same, for machines
- `evidence/` - `rule_results.csv`, `rule_<id>.csv` for every non-passing rule,
  `duplicates_<name>_groups.csv` and `_rows.csv`, `cleanup_*.csv`,
  `pharmacy_language_changes.csv`, `line_codes_*.csv`, `comparison_*.csv`,
  `checklist_classification.csv`, `preflight.json`, `transfer.json`, `readiness.json`
- `work/` - the working copy (kept for the two most recent runs, and for any failed run)

`docs/sample_run/` holds one real run's summary, manifest and main evidence files.

To make the demo READY: write decisions for the review groups into `config/decisions/`
(the format is in the README there) and an `accepted_findings.yaml` naming the blocking
failures the owner accepts. The end-to-end test does exactly this and then promotes.

---

## Part 10 - The synthetic schema

**ProfessionalDirectory** (and its source `ProfessionalProviderSource`) - one row per
practitioner per practice location. `ProviderRecordID` (autonumber), `ProviderNumber`,
`NPI` (fake but passes the real check-digit test), names, `OfficeName`, `Specialty`,
`ProviderType`, address fields, `County`, `Borough`, `Phone`, `Network`, `Source`,
`EffectiveDate`, the stable keys `ProviderKey` / `AddressKey` / `PracticeLocationKey`, the
four line flags, `PrintFlag`, `LineCode`, `LimitationText`.

**ServiceDirectory** (source `AdditionalServiceSource`) - one row per organization per
location per service type. `VendorRecordID`, `ProviderNumber`, `NPI`, `DisplayName`,
`FacilityType`, `ServiceType`, address fields, `Phone`, `Network`, `Source`,
`EffectiveStart` / `EffectiveEnd`, stable keys `VendorKey` / `AddressKey` /
`ServiceLocationKey`, flags, `PrintFlag`, `LineCode`.

**PharmacyPublicationDirectory** - the publication staging table; `SpokenLanguages` is
the comma-delimited field that arrives malformed.

**OtherFacilityReference**, **ManagedCareFacilitySource** - reference tables refreshed
each month; **ApprovedDeletionList** - organizations to remove, by provider number.

Geography is real (five boroughs, their counties, real ZIP codes); everything else is
invented. Every planted defect is listed in `demo/answer_key.json`.

---

## Part 11 - What comes next

1. **AccessBackend** - the DAO implementation of the interface, run against Access files,
   including synthetic `.accdb` files made by the generator.
2. **AccessRunner** - the COM / UI Automation implementation of the runner: run the
   declared actions, find dialogs on screen, apply the same policy the scripted runner
   applies, feed real signals (file modification time, process CPU time) to the watchdog.
3. **Access-file output from the generator** - the same synthetic data written into real
   `.accdb` files, so the Access path can be exercised and recorded without real data.
4. **Optional orchestration** - only if scheduling and visibility are wanted, and only with
   a tool whose quality primitives reinforce the blocking/advisory model.
5. **SQL Server** - a third backend, for teams that have moved off Access.

---

## Part 12 - A reading tour of the code

Read the files in this order. Each entry says what the file is for and what its main
functions do, in plain words, so nothing in the repository is a black box.

### `synth/` - the data

**`vocab.py`** - lists. Names, the five boroughs with their counties and real ZIP codes,
street names, specialties with a provider type each, networks, source feeds, facility
types with the services they offer, languages, and the nine natural-language checklist
notes. Also the "special" fixtures: the practitioner who must not appear, the
organization that must carry one line only, the feed that expanded, the feed that was
retired. Everything invented except geography.

**`npi.py`** - `luhn_check_digit`, `is_valid_npi`, `make_npi`. A real NPI's tenth digit
is a Luhn check digit over the prefix 80840 plus the first nine; the generator makes
identifiers that pass that test so the data survives real validation.

**`generate.py`** - the generator, top to bottom:

- *Schemas* - the column lists for each table, in the order they are written.
- *Helpers* - `weighted_choice`, `unique_value`, `rand_date`, `make_phone` (unique unless
  told to share), `make_address` (real borough / county / ZIP, invented street number),
  `make_flags` (four text flags, sometimes all blank), `line_code` (concatenate, or blank,
  or refuse), `clone` / `tag` (rows carry hidden tags naming the defect planted on them),
  `pick_rows` (choose rows no other injection has touched), `assign_record_ids` (shuffle,
  then number - like an autonumber after a reload), `normalize_languages` (the reference
  rule).
- *AnswerKey* and `collect_tags` - turn the hidden tags into the JSON answer key, grouping
  tags that describe a group (a duplicate pair) and listing single-row tags one by one.
- *Universe builders* - `build_practitioners`, `build_practice_addresses` (a shared pool,
  because group practices put many people at one address), `build_professional_rows` (one
  row per practitioner per location, honouring the specialty/county exclusions),
  `build_organizations`, `build_service_rows` (one row per organization per location per
  service type), `build_pharmacies`, `build_facility_reference`.
- *Month derivations* - `derive_professional_months` and `derive_service_months` split
  the universe into a clean prior month and a current month with 3% new and 2% gone, then
  call `inject_professional_defects` / `inject_service_defects`, which plant every defect
  kind in known rows and tag them. `derive_pharmacy_months` malforms 35% of the language
  strings in every pattern the spec lists; `derive_reference_months` adds and removes a few
  reference rows.
- *Writers* - `write_sqlite` (creates tables, first column as primary key), `write_csv`.
- *`generate()`* - the recipe: build the universe, derive the months, collect the answer
  key, write the three databases, the archive, the CSV copies, the samples, the checklist
  and the key. `report()` prints the table you see on the console. `main()` is the CLI.

### `dirqa/` - the pipeline

**`config.py`** - `Config.load` reads `demo.yaml` into a typed object. `TransferSpec`,
`DuplicateSpec` are the shapes of two config sections. `authorization_phrase` is derived
from the cycle and the repository filename, so it cannot be guessed from one run to the
next without reading the config.

**`queries.py`** - `QueryLibrary`: a name-to-SQL dictionary loaded from `queries.yaml`,
standing in for Access saved queries.

**`backends/base.py`** - the `Backend` interface (abstract methods only) plus
`sha256_of_file` and the `BackupRecord` dataclass. **`backends/sqlite.py`** - the
implementation: `tables`, `columns`, `count`, `query`, `run_saved_query`, `signature`
(hash of every row in a fixed order), `execute`, `execute_many`, `replace_table_from`
(ATTACH the source file, compare columns, delete-and-insert in one transaction),
`file_hash` and `backup` (close the handle first, hash, copy, hash the copy, compare).
**`backends/access.py`** - the same methods as a stub, each documented with the DAO call
it maps to and the Access-only pitfalls.

**`runners/base.py`** - `DialogSpec` (title and text patterns, the one allowed response,
whether it is informational), `ActionSpec` (expected and ceiling seconds), `DialogEvent`,
`ActionResult`, `DialogPolicy.decide` (known informational dialog gets its response;
anything else pauses), the `Runner` interface. **`runners/watchdog.py`** - `Watchdog.check`
reads the side signals and returns running / quiet / stalled; never "stalled" before the
ceiling. **`runners/scripted.py`** - `ScriptedRunner.run_action`: play the scripted dialogs
through the policy, pause on the first one that needs a person, otherwise run the callable.

**`rules/registry.py`** - `Rule` (validated on construction), `RuleResult`, `load_rules`
(rejects duplicate ids), `evaluate` (the pass/fail/warn/report/reminder/error logic),
`evaluate_all`.

**`evidence/manifest.py`** - `StageRecord` (name, status, summary, files, notes),
`Evidence` (writes CSV and JSON into the run folder and returns the relative path),
`Manifest` (the run as a whole; `write` produces `manifest.json` and `summary.md`),
`render_summary`.

**`state.py`** - `CycleState`: the completion markers. `transferred()` answers "was this
exact source already loaded into this exact production file?"; `save()` is called only by
promote.

**`context.py`** - `RunContext`, the one object every stage receives, and `start_run`:
hash production, copy it into the run folder, open the backends, load queries, rules,
accepted findings and cycle state, and decide whether the supplied phrase authorizes.

**`stages/`** - one file per stage. Each exposes `run(ctx) -> StageRecord`.
`duplicates.py` is the most involved: `classify` (exact / legitimate / likely_redundant /
review), `partition` (split an official group by the legitimate-difference fields),
`group_hash` (content hash over the compared fields), `load_decisions`, `decide` (exact
groups delete automatically; review groups only with a logged decision), `review` (the
whole procedure for one official query, including evidence and the rerun), and the two
stage entry points `run_professional` and `run_service`.

**`pipeline.py`** - `STAGES` (the order), `STOP_ON_FAILURE`, `run_pipeline` (the loop,
which always writes the manifest and closes the backends), `final_status`,
`prune_working_copies`, `run` (config path in, manifest out). **`cli.py`** - `run`, `rules`,
`phrase`.

---

## Part 13 - What each test proves

**`test_npi.py`** - the check-digit math against a published example, and that every
generated identifier passes.

**`test_synth.py`** - the generator's contract. Every table exists; the counts in the key
match the databases; every defect record id in the key exists in the named table; exact
duplicate copies are byte-identical except for the record id; legitimate multiples differ
*only* in network; review duplicates differ in exactly the declared field; every malformed
language string normalizes to the expected value with an independently written
normalizer, and normalization is idempotent; the prior month is clean in every way the
rules check; the same seed gives the same bytes; the samples and checklist are written.

**`test_wording.py`** - three production vocabulary terms appear nowhere in the
repository. The list lives only in this test.

**`test_backend.py`** - the SQLite backend: reads, writes, signature stability,
replace-from with schema check (and that a failed replace leaves the target untouched),
backup verification against a fresh hash.

**`test_rules.py`** - each expectation and severity combination produces the right status;
a broken query is a finding, not a crash; invalid rules and duplicate ids are rejected; the
shipped registry loads and every query it names exists.

**`test_duplicates.py`** - the classifier's four outcomes, that no stable key means no
automatic deletion, that partitioning separates distinct listings, that the group hash
ignores record ids and row order, and that logged decisions are applied exactly.

**`test_runner.py`** - the dialog policy answers known informational dialogs, pauses on
unknown ones and on known questions, and keeps the exact text; the scripted runner pauses
*before* acting when a dialog needs a person; the watchdog reports quiet / running /
stalled correctly against a fake clock and never says stalled before the ceiling; the
shipped config's dialogs and action timings load and behave.

**`test_pipeline.py`** - end to end on generated data. A dry run leaves production's hash
unchanged and every stage completed; the transfer loaded exactly the source counts; every
planted exact duplicate copy is gone and every original, legitimate, review and phone row
is still there; every planted redundant phone pair was surfaced and none deleted; cleanup,
language and line-code counts match the key; the rules find the planted failures and pass
what the run fixed; the comparison explains the feed growth as row expansion; an apply run
is blocked while NOT READY and with a wrong phrase; an apply run with logged decisions and
accepted findings reaches READY, promotes, and production's hash equals the working
copy's; a further run skips the transfer, cleanup, languages and line codes, deletes
nothing, and is READY.

---

## Part 14 - The config files, key by key

**`config/demo.yaml`**

| key | meaning |
|---|---|
| `cycle`, `prior_cycle` | the month being run and the month to compare against |
| `databases` | `repository` (production) and the named source databases |
| `archive_dir`, `backup_dir`, `runs_dir` | where prior-month CSVs live, where backups go, where run folders go |
| `decisions_dir`, `queries_file`, `rules_file` | the decision logs, the query library, the rule registry |
| `checklist_file`, `accepted_findings_file` | the informal notes CSV; the owner's acceptances (optional) |
| `backup_retention`, `working_copy_retention` | how many backups and working copies to keep |
| `stop_before_borough` | always true in practice; recorded in the manifest |
| `tables` | role -> table name, so stages never hardcode a name |
| `transfers` | source database, source table, target table, mode |
| `duplicates.<name>` | the official query, table, record id, stable key, grouping fields, compared fields, legitimate-difference fields, text fields, location keys |
| `service_cleanup`, `retired_sources` | the columns the cleanup matches on; the exact retired source values |
| `line_code` | the code column, the four flag columns, the tables and their record ids |
| `pharmacy` | table, record id, column, and the QA query |
| `dialogs` | every dialog the runner may answer: patterns, response, whether informational |
| `actions` | expected and ceiling seconds per interactive action |

**`config/queries.yaml`** - name: SQL. The three official duplicate queries, the
zero-row checks, the checklist translations, the advisory checks, the grouped reports.

**`config/rules.yaml`** - one entry per rule: `id`, `description`, `severity`, `expect`,
`query`, `origin`, `checklist_note`, `promoted_on`, `note`.

**`config/decisions/<name>.csv`** - `group_hash`, `decision`, `keep_stable_key`,
`decided_by`, `decided_on`, `note`.

**`config/accepted_findings.yaml`** - `rule`, `accepted_by`, `accepted_on`, `reason`.
