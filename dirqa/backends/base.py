"""The storage-backend interface.

A backend is the one place that knows how to talk to a database file. Every
stage in the pipeline talks to a backend through the methods below and nothing
else, so the stages never import a database driver. Two implementations are
planned:

* ``SqliteBackend`` - portable; used for the demo, the tests, and any machine.
* ``AccessBackend`` - the target platform; Windows + Microsoft Access only.

The methods are deliberately few and deliberately plain: count rows, run a
query, run a saved query by name, replace a table from another database, hash
the file, back it up. If a stage needs something a backend cannot promise, that
is a sign the stage is doing the backend's job.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class BackupRecord:
    source: str
    source_sha256: str
    source_size: int
    backup: str
    backup_sha256: str
    backup_size: int
    verified: bool
    taken_at: str


class Backend(ABC):
    """What every storage backend promises."""

    path: Path

    # --- reading -----------------------------------------------------------

    @abstractmethod
    def tables(self) -> list[str]:
        """Names of the tables in the database."""

    @abstractmethod
    def columns(self, table: str) -> list[str]:
        """Column names of a table, in order."""

    @abstractmethod
    def count(self, table: str) -> int:
        """Row count of a table."""

    @abstractmethod
    def query(self, sql: str, params: Sequence = ()) -> list[dict]:
        """Run SQL that returns rows; each row as a dict keyed by column name."""

    @abstractmethod
    def run_saved_query(self, name: str) -> list[dict]:
        """Run a saved query by name (an Access QueryDef, or a library entry)."""

    @abstractmethod
    def signature(self, table: str) -> str:
        """A hash of a table's contents, for 'has this already been done?' checks."""

    # --- writing -----------------------------------------------------------

    @abstractmethod
    def execute(self, sql: str, params: Sequence = ()) -> int:
        """Run SQL that changes data; returns the number of rows affected."""

    @abstractmethod
    def execute_many(self, sql: str, rows: Iterable[Sequence]) -> int:
        """Run one statement for many parameter sets; returns rows affected."""

    @abstractmethod
    def replace_table_from(self, source: Backend, source_table: str, target: str) -> int:
        """Delete every row of ``target`` and load ``source_table`` from another database."""

    # --- the file itself ---------------------------------------------------

    @abstractmethod
    def file_hash(self) -> str:
        """SHA-256 of the database file, taken with no handle open on it."""

    @abstractmethod
    def backup(self, dest_dir: Path, label: str) -> BackupRecord:
        """Copy the file to ``dest_dir`` and verify the copy against a fresh hash."""

    @abstractmethod
    def close(self) -> None:
        """Release the file."""
