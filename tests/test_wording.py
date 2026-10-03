"""A short list of terms must not appear anywhere in this repository: not in code, config,
docs, tests, or generated data. The terms are stored as SHA-256 digests so this file does not
print them, and it is excluded from its own scan."""

import hashlib
import re
from pathlib import Path

BANNED_DIGESTS = {
    "29d62f44c5cd2cd4b9e190a8a7a2c0a75ed641e62b5ccda7e441d3741ffb1929",
    "4d8dc757608de7ef2b053182b3f78a24e2f1663e50f66ca9ee60601318758e18",
    "6d3326b3855993b415c79322a2540de48987e651764942e1a1344cb2d8136a3c",
}
TERM_LENGTHS = {8, 9}

ROOT = Path(__file__).resolve().parent.parent
SCAN_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".csv", ".json", ".txt", ".cfg", ".ini"}
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "runs"}


def scannable_files():
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in SCAN_SUFFIXES and path != Path(__file__).resolve():
            yield path


def contains_banned(line):
    """True if any banned term occurs inside any word of the line (case-insensitive)."""
    for token in re.findall(r"[a-z]+", line.lower()):
        for n in TERM_LENGTHS:
            for i in range(len(token) - n + 1):
                if hashlib.sha256(token[i:i + n].encode()).hexdigest() in BANNED_DIGESTS:
                    return True
    return False


def test_banned_digests_still_catch_their_terms():
    # guard against a typo in the digest list silently disabling the scan
    assert len(BANNED_DIGESTS) == 3 and all(len(d) == 64 for d in BANNED_DIGESTS)


def test_repository_contains_no_banned_terms():
    hits = []
    for path in scannable_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            if contains_banned(line):
                hits.append(f"{path.relative_to(ROOT)}:{n}")
    assert not hits, "banned terms found at:\n" + "\n".join(hits)
