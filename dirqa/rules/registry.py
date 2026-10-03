"""The rule registry: every quality check, declared once, in one file.

A rule names a saved query, says what result counts as a pass, and says how
much a failure matters:

    severity   blocking   must pass before the directory can be published
               advisory   reported, never stops the run
               reminder   a note for a future cycle; has no query

    expect     zero_rows          the query must return nothing
               at_least_one_row   the query must return something (a presence test)
               grouped_report     a listing for a person to read; cannot fail

A rule that came from the informal checklist carries the note it was translated
from. Promotion from advisory to blocking is a one-word edit plus a date, so the
file's history shows when each rule started to matter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..backends.base import Backend

SEVERITIES = ("blocking", "advisory", "reminder")
EXPECTATIONS = ("zero_rows", "at_least_one_row", "grouped_report")


@dataclass
class Rule:
    id: str
    description: str
    severity: str
    expect: str | None = None
    query: str | None = None
    origin: str = "spec"              # "spec" or "checklist"
    checklist_note: str | None = None
    promoted_on: str | None = None
    note: str | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"rule {self.id}: severity must be one of {SEVERITIES}")
        if self.severity == "reminder":
            return
        if self.expect not in EXPECTATIONS:
            raise ValueError(f"rule {self.id}: expect must be one of {EXPECTATIONS}")
        if not self.query:
            raise ValueError(f"rule {self.id}: a {self.severity} rule needs a query")


@dataclass
class RuleResult:
    rule: Rule
    status: str            # pass | fail | warn | report | reminder | error
    row_count: int
    rows: list[dict]
    message: str

    @property
    def blocking_failure(self) -> bool:
        return self.rule.severity == "blocking" and self.status in ("fail", "error")


def load_rules(path: str | Path) -> list[Rule]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    rules = [Rule(**entry) for entry in raw]
    ids = [r.id for r in rules]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate rule ids: {duplicates}")
    return rules


def evaluate(rule: Rule, backend: Backend) -> RuleResult:
    if rule.severity == "reminder":
        return RuleResult(rule, "reminder", 0, [], rule.description)
    try:
        rows = backend.run_saved_query(rule.query)
    except Exception as exc:  # a broken query is a finding, not a crash
        return RuleResult(rule, "error", 0, [], f"query {rule.query!r} failed: {exc}")
    n = len(rows)
    if rule.expect == "grouped_report":
        return RuleResult(rule, "report", n, rows, f"{n} rows to review")
    if rule.expect == "zero_rows":
        passed = n == 0
        message = "clear" if passed else f"{n} rows returned"
    else:  # at_least_one_row
        passed = n >= 1
        message = f"present ({n} rows)" if passed else "absent"
    if passed:
        status = "pass"
    else:
        status = "fail" if rule.severity == "blocking" else "warn"
    return RuleResult(rule, status, n, rows, message)


def evaluate_all(rules: list[Rule], backend: Backend) -> list[RuleResult]:
    return [evaluate(rule, backend) for rule in rules]
