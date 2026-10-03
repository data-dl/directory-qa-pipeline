# Five-minute demo script

What to type and what to point at when showing this live. Everything below runs on
any machine with Python 3.11+ and takes under a minute of compute in total.

## 0. Before the demo (once)

```bash
git clone https://github.com/data-dl/directory-qa-pipeline
cd directory-qa-pipeline
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # Windows; on Mac/Linux: .venv/bin/python
```

Open three things: this file, `docs/guidebook.md` Part 5 (the stages), and a terminal at
the repo root. Delete any old `runs/` folder so the first run is fresh.

## 1. The premise (30 seconds)

> "This is a monthly data-quality pipeline for a healthcare provider directory that lives
> on a legacy single-file database. A realistic workflow with real controls, but every row is
> synthetic - a generator invents the data and plants twenty kinds of defect in known
> places, so I can prove what the pipeline catches."

Point at `README.md`, the stage table.

## 2. Generate the data (30 seconds)

```bash
.venv/Scripts/python -m synth --out demo
```

Point at the printed table: ~19,600 practitioner rows, ~5,800 service rows, two months,
then the list of planted defects with counts. Say:

> "Same seed, same bytes, every time. The answer key lists every defect by record id."

Open `demo/samples/ProfessionalProviderSource.csv` in Excel if they want to see a row.

## 3. Run the cycle (60 seconds)

```bash
.venv/Scripts/python -m dirqa run --config config/demo.yaml
```

Twelve lines, one per stage. Walk down them:

- **backup** - "hashed, copied, hash compared. Every mode, every run."
- **transfer** - "four tables, exact counts, or the run stops."
- **professional_duplicates** - "250 groups from the official query: 150 exact - deleted,
  40 legitimate - never touched, 60 for a person. 163 rows removed, zero false deletions."
- **service_cleanup** - "the approved deletion list and a retired feed, by exact identifier."
- **line_codes** - "24,000 codes derived; 104 rows with partial flags exported instead
  of guessed."
- **pharmacy_languages** - "210 malformed strings fixed, QA query rerun, zero remain."
- **quality_checks** - "22 rules; 9 blocking failures, all things only a person can fix."
- **comparison** - "one source grew 300 percent - explained as rows per location, not new sites."
- **readiness: NOT READY** - "which is the correct answer for this data."
- **promote: dry-run** - "production untouched. Here is the exact phrase that would change it."

Say the key sentence:

> "The run never edited production. It worked on a copy, and the last stage is the only
> one that can write production - with a phrase, a verified backup, and a READY verdict."

## 4. The evidence (60 seconds)

```bash
cd runs/2026-09/<the run folder>
```

Open `summary.md` - the whole run on one page. Then two evidence files:

- `evidence/duplicates_professional_groups.csv` - point at the `kind` and `reason`
  columns: exact / legitimate / review, and why. Point at `group_hash`: "this is how a
  human decision gets remembered next month."
- `evidence/checklist_classification.csv` - "the informal spreadsheet of notes,
  classified: which are enforced, which are only reported, which nobody has translated yet."

## 5. The tests (30 seconds)

```bash
.venv/Scripts/python -m pytest -q
```

> "69 tests. The important ones run the whole pipeline on generated data and grade it
> against the answer key - every planted copy gone, every original kept - then promote
> with logged decisions, then run again and confirm there is nothing left to do."

Point at the green check on GitHub.

## 6. The design in one breath (30 seconds)

> "Rules live in YAML with a severity and a promotion date. The database is behind one
> small interface, so the same stages run on Access or SQLite. Decisions
> people make are logged by content hash and reapplied. And the pipeline stops before the
> publishing step on purpose - that stays manual."

If asked "what's next": the Access backend through DAO, the runner for dialogs and slow
routines, and the generator writing real Access files so that path can be exercised on
synthetic data too.

## Questions that come up, and where the answer is

| Question | Answer lives in |
|---|---|
| Why not migrate off Access? | guidebook Part 9 |
| How do you know it's correct? | guidebook Part 9; `tests/test_pipeline.py` |
| What's deliberately manual? | guidebook Part 9 |
| Hardest bug? | guidebook Part 8 |
| What would SQL Server change? | guidebook Part 9 |
| Where did the numbers come from? | `ASSUMPTIONS.md` |
