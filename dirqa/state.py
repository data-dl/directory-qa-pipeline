"""Cycle state: completion markers that survive between runs.

After a run promotes, production holds cleaned data while the source databases
still hold the raw rows, so "is the target identical to the source?" can no
longer tell whether the transfer happened. This file records, per cycle, the
signature of each source table that was loaded and the hash of the production
file that resulted. A later run trusts the markers only if production still has
that hash: restore production from a backup and the markers no longer apply,
which is exactly right - the restored file is pre-transfer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CycleState:
    path: Path
    production_hash: str = ""
    transfers: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, runs_dir: Path, cycle: str) -> CycleState:
        path = runs_dir / cycle / "state.json"
        if not path.exists():
            return cls(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(path, raw.get("production_hash", ""), dict(raw.get("transfers", {})))

    def applies_to(self, production_hash: str) -> bool:
        return bool(self.production_hash) and self.production_hash == production_hash

    def transferred(self, target: str, source_signature: str, production_hash: str) -> dict | None:
        """The marker for ``target`` if it describes this production file and this source."""
        marker = self.transfers.get(target)
        if marker and self.applies_to(production_hash) and marker.get("source_signature") == source_signature:
            return marker
        return None

    def save(self, production_hash: str, transfers: dict[str, dict]) -> None:
        self.production_hash = production_hash
        self.transfers = dict(transfers)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"production_hash": production_hash, "transfers": transfers}, indent=2),
                             encoding="utf-8")
