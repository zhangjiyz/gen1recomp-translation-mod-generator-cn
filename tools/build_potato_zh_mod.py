#!/usr/bin/env python3
"""Build the pinned PotatoVoxel localization bridge against current Gen1Recomp."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.engine_backlog import iter_literal_strings_callsites
from pipeline.project import which_luajit


EXPECTED_REVISION = "a4675f9017c78a3a00bbefe389f1bc33ec4c1394"
OVERLAY = ROOT / "config" / "zh-Hans" / "mod_overlays" / "potato_voxel.json"
PATCH = ROOT / "config" / "zh-Hans" / "mod_overlays" / "potato_voxel-main-a4675f9.patch"


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print("\n>", " ".join(command))
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="official PotatoVoxel git checkout at the pinned main revision")
    parser.add_argument("--gen1recomp", type=Path, required=True,
                        help="current Gen1Recomp checkout containing tools/modkit.py")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--build-root", type=Path,
                        default=ROOT / ".cache" / "potato-voxel-main-a4675f9-zh")
    parser.add_argument("--luajit", default=which_luajit())
    args = parser.parse_args()

    source = args.source.resolve()
    engine = args.gen1recomp.resolve()
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=source, check=True,
        text=True, stdout=subprocess.PIPE,
    ).stdout.strip()
    if revision != EXPECTED_REVISION:
        parser.error(
            f"PotatoVoxel revision mismatch: expected {EXPECTED_REVISION}, got {revision}; "
            "refresh and review the localization patch before building"
        )
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("id") != "potato_voxel" or manifest.get("version") != "1.9.4":
        parser.error("unexpected PotatoVoxel manifest id/version at pinned revision")
    if not args.luajit:
        parser.error("LuaJIT is required by Modkit packaging")

    build_root = args.build_root.resolve()
    if build_root.exists():
        shutil.rmtree(build_root)
    shutil.copytree(
        source, build_root, symlinks=True,
        ignore=shutil.ignore_patterns(".git", ".github", ".DS_Store"),
    )
    # Use the POSIX patch tool because the ignored build directory lives under
    # this Git checkout; git apply would discover the parent repository and
    # resolve the patch paths against that repository instead of build_root.
    _run([
        "patch", "--no-backup-if-mismatch", "-p1", "-i", str(PATCH),
    ], cwd=build_root)

    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    entries = overlay["entries"]
    callsites = iter_literal_strings_callsites(build_root)
    keys = sorted({row["source"] for row in callsites})
    missing = sorted(set(keys) - set(entries))
    if missing:
        raise RuntimeError(f"localized PotatoVoxel Strings keys missing from overlay: {missing!r}")
    coverage = overlay["coverage"]
    actual = (len(callsites), len(keys), len(entries))
    expected = (
        coverage["explicit_strings_callsites"],
        coverage["explicit_strings_unique"],
        coverage["catalog_entries"],
    )
    if actual != expected:
        raise RuntimeError(f"PotatoVoxel coverage drift: expected {expected}, got {actual}")

    modkit = engine / "tools" / "modkit.py"
    env = dict(os.environ)
    env.update({
        "SOURCE_DATE_EPOCH": "0",
        "PYTHONUTF8": "1",
        "MODKIT_LUAJIT": str(args.luajit),
        "LUA": str(args.luajit),
    })
    _run([sys.executable, str(modkit), "lint", str(build_root)], cwd=engine, env=env)
    _run([
        sys.executable, str(modkit), "validate", str(build_root),
        "--strict", "--base", "fixture",
    ], cwd=engine, env=env)

    args.output.mkdir(parents=True, exist_ok=True)
    archive = (args.output / overlay["source_package"]["name"]).resolve()
    _run([
        sys.executable, str(modkit), "pack", str(build_root),
        "--base", "fixture", "-o", str(archive),
    ], cwd=engine, env=env)
    digest = _sha256(archive)
    expected_digest = overlay["source_package"]["sha256"]
    if digest != expected_digest:
        raise RuntimeError(
            f"PotatoVoxel archive hash mismatch: expected {expected_digest}, got {digest}"
        )
    print(json.dumps({
        "archive": str(archive),
        "sha256": digest,
        "upstream_revision": revision,
        "manifest_version": manifest["version"],
        "catalog_entries": len(entries),
        "explicit_strings_callsites": len(callsites),
        "explicit_strings_unique": len(keys),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
