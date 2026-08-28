#!/usr/bin/env python3
"""Refresh per-file hashes after a reviewed edit to versioned seed catalogs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def refresh(directory: Path, reason: str) -> None:
    metadata_path = directory / "seed.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for row in metadata.get("files", []):
        path = directory / row["path"]
        payload = path.read_bytes()
        row["bytes"] = len(payload)
        row["sha256"] = hashlib.sha256(payload).hexdigest()
    changes = metadata.setdefault("derived_changes", [])
    if reason not in changes:
        changes.append(reason)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reason", required=True)
    parser.add_argument(
        "directories", nargs="*", type=Path,
        default=[ROOT / "seeds" / "zh-Hans" / "rby", ROOT / "seeds" / "zh-Hans" / "gsc-gs"],
    )
    args = parser.parse_args()
    for directory in args.directories:
        refresh(directory.resolve(), args.reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
