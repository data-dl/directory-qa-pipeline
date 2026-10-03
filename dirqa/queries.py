"""The saved-query library.

In Access, a "saved query" is a named object inside the database file. SQLite has
no such thing, so the portable backend keeps the same idea in a YAML file: a name
mapped to the SQL it stands for. Stages and rules refer to queries by name only,
so they do not care which of the two is behind it.
"""

from __future__ import annotations

from pathlib import Path

import yaml


class QueryLibrary:
    def __init__(self, queries: dict[str, str]):
        self._queries = dict(queries)

    @classmethod
    def load(cls, path: str | Path) -> QueryLibrary:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls({name: str(sql).strip() for name, sql in raw.items()})

    def names(self) -> list[str]:
        return sorted(self._queries)

    def __contains__(self, name: str) -> bool:
        return name in self._queries

    def sql(self, name: str) -> str:
        try:
            return self._queries[name]
        except KeyError:
            raise KeyError(f"no saved query named {name!r}; known: {', '.join(self.names())}") from None
