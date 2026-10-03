"""The portable backend: SQLite.

SQLite is the closest free stand-in for a single-file Access database: one file,
no server, SQL close enough that the saved queries port with little change. It
ships inside Python, so the demo and the tests run on any machine with nothing
installed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from ..queries import QueryLibrary
from .base import Backend, BackupRecord, sha256_of_file


def q(identifier: str) -> str:
    """Quote a table or column name."""
    return '"' + identifier.replace('"', '""') + '"'


class SchemaMismatch(Exception):
    pass


class SqliteBackend(Backend):
    def __init__(self, path: str | Path, queries: QueryLibrary | None = None):
        self.path = Path(path)
        self.queries = queries or QueryLibrary({})
        self._con: sqlite3.Connection | None = None

    def __repr__(self) -> str:
        return f"SqliteBackend({self.path.name})"

    # --- connection --------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        if self._con is None:
            self._con = sqlite3.connect(self.path)
            self._con.row_factory = sqlite3.Row
        return self._con

    def close(self) -> None:
        if self._con is not None:
            self._con.commit()
            self._con.close()
            self._con = None

    # --- reading -----------------------------------------------------------

    def tables(self) -> list[str]:
        rows = self._connect().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
        return [r[0] for r in rows]

    def columns(self, table: str) -> list[str]:
        rows = self._connect().execute(f"PRAGMA table_info({q(table)})")
        return [r["name"] for r in rows]

    def count(self, table: str) -> int:
        return self._connect().execute(f"SELECT COUNT(*) FROM {q(table)}").fetchone()[0]

    def query(self, sql: str, params: Sequence = ()) -> list[dict]:
        cur = self._connect().execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]

    def run_saved_query(self, name: str) -> list[dict]:
        return self.query(self.queries.sql(name))

    def signature(self, table: str) -> str:
        cols = self.columns(table)
        order = ", ".join(q(c) for c in cols)
        digest = hashlib.sha256()
        for row in self._connect().execute(f"SELECT * FROM {q(table)} ORDER BY {order}"):
            digest.update(json.dumps(list(row), default=str).encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()

    # --- writing -----------------------------------------------------------

    def execute(self, sql: str, params: Sequence = ()) -> int:
        con = self._connect()
        cur = con.execute(sql, tuple(params))
        con.commit()
        return cur.rowcount

    def execute_many(self, sql: str, rows: Iterable[Sequence]) -> int:
        con = self._connect()
        cur = con.executemany(sql, rows)
        con.commit()
        return cur.rowcount

    def replace_table_from(self, source: Backend, source_table: str, target: str) -> int:
        if not isinstance(source, SqliteBackend):
            raise TypeError("SqliteBackend can only load from another SqliteBackend")
        target_cols = self.columns(target)
        source_cols = source.columns(source_table)
        if set(target_cols) != set(source_cols):
            missing = sorted(set(target_cols) - set(source_cols))
            extra = sorted(set(source_cols) - set(target_cols))
            raise SchemaMismatch(f"{source_table} -> {target}: missing {missing}, extra {extra}")
        cols = ", ".join(q(c) for c in target_cols)
        source.close()  # so the attach sees a consistent file
        con = self._connect()
        con.execute("ATTACH DATABASE ? AS src", (str(source.path),))
        try:
            con.execute("BEGIN")
            con.execute(f"DELETE FROM {q(target)}")
            con.execute(f"INSERT INTO {q(target)} ({cols}) SELECT {cols} FROM src.{q(source_table)}")
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.execute("DETACH DATABASE src")
        return self.count(target)

    # --- the file itself ---------------------------------------------------

    def file_hash(self) -> str:
        self.close()
        return sha256_of_file(self.path)

    def backup(self, dest_dir: Path, label: str) -> BackupRecord:
        # Hash with the handle closed, immediately before copying. A hash taken
        # earlier - before any inspection session - can be stale even when no
        # table changed, because the engine may rewrite internal metadata.
        self.close()
        dest_dir.mkdir(parents=True, exist_ok=True)
        fresh_hash = sha256_of_file(self.path)
        fresh_size = self.path.stat().st_size
        dest = dest_dir / f"{self.path.stem}_{label}{self.path.suffix}"
        shutil.copy2(self.path, dest)
        backup_hash = sha256_of_file(dest)
        backup_size = dest.stat().st_size
        return BackupRecord(
            source=str(self.path), source_sha256=fresh_hash, source_size=fresh_size,
            backup=str(dest), backup_sha256=backup_hash, backup_size=backup_size,
            verified=(backup_hash == fresh_hash and backup_size == fresh_size),
            taken_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
