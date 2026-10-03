import sqlite3

import pytest

from dirqa.backends.sqlite import SchemaMismatch, SqliteBackend
from dirqa.queries import QueryLibrary


def make_db(path, rows, table="T", extra_col=False):
    con = sqlite3.connect(path)
    cols = "id INTEGER PRIMARY KEY, name TEXT" + (", extra TEXT" if extra_col else "")
    con.execute(f"CREATE TABLE {table} ({cols})")
    con.executemany(f"INSERT INTO {table} VALUES ({'?,?,?' if extra_col else '?,?'})", rows)
    con.commit()
    con.close()


def test_read_methods(tmp_path):
    db = tmp_path / "a.sqlite"
    make_db(db, [(1, "x"), (2, "y")])
    b = SqliteBackend(db, QueryLibrary({"all": "SELECT * FROM T ORDER BY id"}))
    assert b.tables() == ["T"]
    assert b.columns("T") == ["id", "name"]
    assert b.count("T") == 2
    assert b.query("SELECT name FROM T WHERE id = ?", (2,)) == [{"name": "y"}]
    assert [r["id"] for r in b.run_saved_query("all")] == [1, 2]
    with pytest.raises(KeyError):
        b.run_saved_query("nope")
    b.close()


def test_write_methods_and_signature(tmp_path):
    db = tmp_path / "a.sqlite"
    make_db(db, [(1, "x"), (2, "y")])
    b = SqliteBackend(db)
    before = b.signature("T")
    assert b.execute("UPDATE T SET name = ? WHERE id = ?", ("z", 2)) == 1
    assert b.signature("T") != before
    assert b.execute_many("UPDATE T SET name = ? WHERE id = ?", [("x", 1), ("y", 2)]) == 2
    assert b.signature("T") == before, "same content -> same signature"
    b.close()


def test_replace_table_from_and_schema_check(tmp_path):
    src, dst, bad = tmp_path / "src.sqlite", tmp_path / "dst.sqlite", tmp_path / "bad.sqlite"
    make_db(src, [(10, "a"), (11, "b"), (12, "c")])
    make_db(dst, [(1, "old")])
    make_db(bad, [(1, "x", "e")], extra_col=True)
    d = SqliteBackend(dst)
    assert d.replace_table_from(SqliteBackend(src), "T", "T") == 3
    assert [r["id"] for r in d.query("SELECT id FROM T ORDER BY id")] == [10, 11, 12]
    with pytest.raises(SchemaMismatch):
        d.replace_table_from(SqliteBackend(bad), "T", "T")
    assert d.count("T") == 3, "a failed transfer leaves the target untouched"
    d.close()


def test_backup_is_verified_against_fresh_hash(tmp_path):
    db = tmp_path / "a.sqlite"
    make_db(db, [(1, "x")])
    b = SqliteBackend(db)
    b.execute("INSERT INTO T VALUES (2, 'y')")  # dirty the connection first
    rec = b.backup(tmp_path / "backups", "label")
    assert rec.verified
    assert rec.backup.endswith("a_label.sqlite")
    assert rec.source_sha256 == rec.backup_sha256
    assert rec.source_sha256 == b.file_hash()
