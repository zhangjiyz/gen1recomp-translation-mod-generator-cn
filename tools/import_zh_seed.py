#!/usr/bin/env python3
"""Import reviewed Simplified Chinese catalogs from previously built mods.

The imported files are source seeds, not release archives: executable entry
points, manifests, fonts and generated validation reports are deliberately
excluded.  This lets the current generator rebuild packaging and validation
against its pinned Gen1Recomp version while preserving reviewed translations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOT_FILES = {"TRANSLATION_SOURCE.md"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_seed(archive: Path, profile: str, destination: Path) -> dict[str, object]:
    if not archive.is_file():
        raise FileNotFoundError(archive)
    destination.mkdir(parents=True, exist_ok=True)
    imported: list[dict[str, object]] = []
    with zipfile.ZipFile(archive) as bundle:
        names = sorted(bundle.namelist())
        for name in names:
            path = Path(name)
            allowed = (
                name in ALLOWED_ROOT_FILES
                or (len(path.parts) == 2 and path.parts[0] == "lang" and path.suffix == ".lua")
            )
            if not allowed:
                continue
            payload = bundle.read(name)
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            imported.append({
                "path": path.as_posix(),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
    if not imported or not any(row["path"] == "lang/strings.lua" for row in imported):
        raise ValueError(f"archive has no usable translation catalogs: {archive}")
    provenance = {
        "schema": "gen1recomp-translation-mods/zh-seed",
        "version": 1,
        "profile": profile,
        "language": "zh-Hans",
        "source_archive_name": archive.name,
        "source_archive_sha256": _sha256(archive),
        "files": imported,
        "notice": (
            "Imported from a user-reviewed generated mod. Rebuild release packaging "
            "and validation against the current pinned engine; do not redistribute "
            "fan-translation text without permission from its authors."
        ),
    }
    (destination / "seed.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rby", required=True, type=Path)
    parser.add_argument("--gs", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "seeds" / "zh-Hans")
    args = parser.parse_args()
    targets = {"rby": args.output / "rby", "gsc-gs": args.output / "gsc-gs"}
    for target in targets.values():
        if target.exists():
            shutil.rmtree(target)
    reports = {
        "rby": import_seed(args.rby.resolve(), "rby", targets["rby"]),
        "gsc-gs": import_seed(args.gs.resolve(), "gsc-gs", targets["gsc-gs"]),
    }
    print(json.dumps({key: len(value["files"]) for key, value in reports.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
