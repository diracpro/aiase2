"""Source integrity verification (PRD §5 Verification, §8).

Captures a snapshot (size, mtime_ns, sha256) of every file under the configured
source read paths before and after the scan. If anything changes, the scan is a
technical NO-GO.

The snapshot itself reads files read-only and writes nothing to source paths.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


def _iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file():
                yield p


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:  # read-only
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(roots: Iterable[Path]) -> dict[str, dict]:
    """Map of file path -> {size, mtime_ns, sha256}."""
    snap: dict[str, dict] = {}
    for p in _iter_files(roots):
        try:
            st = p.stat()
            snap[str(p)] = {
                "size": st.st_size,
                "mtime_ns": st.st_mtime_ns,
                "sha256": _hash_file(p),
            }
        except OSError:
            # Unreadable file: record its absence of metadata rather than failing.
            snap[str(p)] = {"size": None, "mtime_ns": None, "sha256": None}
    return snap


def diff(before: dict[str, dict], after: dict[str, dict]) -> dict:
    """Return a structured diff. `unchanged` is True only if nothing differs."""
    before_keys = set(before)
    after_keys = set(after)
    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    modified = sorted(
        k for k in (before_keys & after_keys) if before[k] != after[k]
    )
    return {
        "unchanged": not (added or removed or modified),
        "added": added,
        "removed": removed,
        "modified": modified,
        "files_checked": len(after_keys | before_keys),
    }
