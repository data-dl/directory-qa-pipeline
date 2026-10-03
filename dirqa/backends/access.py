"""The target backend: Microsoft Access, through DAO.

It is not implemented in this repository yet: it needs Windows, Microsoft
Access and the ``pywin32`` package, none of which a reviewer can be assumed to
have. What is here is the shape - every method of the interface, each with the
DAO call it maps to - so the portable ``SqliteBackend`` and this one stay in
step.

How the methods map:

    tables()             DBEngine.OpenDatabase(path).TableDefs, skipping MSys* tables
    columns(table)       TableDefs(table).Fields
    count(table)         OpenRecordset("SELECT COUNT(*) FROM [table]")
    query(sql)           OpenRecordset(sql), walked into dicts
    run_saved_query(n)   QueryDefs(n).OpenRecordset()  - the saved query object itself
    execute(sql)         Database.Execute(sql, dbFailOnError); RecordsAffected
    replace_table_from   Execute("DELETE FROM [target]") then
                         Execute("INSERT INTO [target] SELECT * FROM [table] IN 'source.accdb'")
    file_hash()          close every handle first; the .laccdb lock file must be gone
    backup()             same as SQLite: close, fresh hash, copy, hash the copy, compare

Things the SQLite backend never has to think about, and this one must:

* Opening the database may change internal metadata even when no table changes,
  so a hash taken before an inspection session is not a valid backup baseline.
* DAO does not evaluate every Access expression function in ad-hoc SQL (``Nz()``
  is the usual casualty); saved queries do, because the Access expression
  service runs them.
* Text flags may hold ``"0"`` / ``"1"`` rather than numbers, and blanks are
  blanks, never zero.
* A ``.laccdb`` file beside the database means another session has it open.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from ..queries import QueryLibrary
from .base import Backend, BackupRecord

_NOT_YET = "AccessBackend is a documented stub in this repository; see the module docstring."


class AccessBackend(Backend):
    def __init__(self, path: str | Path, queries: QueryLibrary | None = None):
        self.path = Path(path)
        self.queries = queries or QueryLibrary({})

    def tables(self) -> list[str]:
        raise NotImplementedError(_NOT_YET)

    def columns(self, table: str) -> list[str]:
        raise NotImplementedError(_NOT_YET)

    def count(self, table: str) -> int:
        raise NotImplementedError(_NOT_YET)

    def query(self, sql: str, params: Sequence = ()) -> list[dict]:
        raise NotImplementedError(_NOT_YET)

    def run_saved_query(self, name: str) -> list[dict]:
        raise NotImplementedError(_NOT_YET)

    def signature(self, table: str) -> str:
        raise NotImplementedError(_NOT_YET)

    def execute(self, sql: str, params: Sequence = ()) -> int:
        raise NotImplementedError(_NOT_YET)

    def execute_many(self, sql: str, rows: Iterable[Sequence]) -> int:
        raise NotImplementedError(_NOT_YET)

    def replace_table_from(self, source: Backend, source_table: str, target: str) -> int:
        raise NotImplementedError(_NOT_YET)

    def file_hash(self) -> str:
        raise NotImplementedError(_NOT_YET)

    def backup(self, dest_dir: Path, label: str) -> BackupRecord:
        raise NotImplementedError(_NOT_YET)

    def close(self) -> None:
        pass
