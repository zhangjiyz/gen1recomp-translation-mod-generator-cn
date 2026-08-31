"""Versioned translation seed catalogs used when no PokeCorpus language exists."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .engine import _decode_lua_string
from .project import ROOT


SEED_SCHEMA = "gen1recomp-translation-mods/zh-seed"
_ENTRY = re.compile(
    r'^\s*\[("(?:\\.|[^"\\])*")]\s*=\s*("(?:\\.|[^"\\])*")\s*,?\s*$'
)
CRYSTAL_CATALOG_SCHEMA = "gen1recomp-translation-mods/crystal-zh-labels"


def read_lua_catalog(path: str | Path) -> dict[str, str]:
    """Read a generated one-entry-per-line string-to-string Lua table."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    meaningful = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("--")]
    if not meaningful or meaningful[0] != "return {" or meaningful[-1] != "}":
        raise ValueError(f"seed catalog must contain exactly a return table: {path}")
    values: dict[str, str] = {}
    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("--") or stripped in {"return {", "}"}:
            continue
        match = _ENTRY.match(line)
        if not match:
            raise ValueError(f"invalid seed catalog entry at {path}:{line_no}")
        key = _decode_lua_string(match.group(1))
        value = _decode_lua_string(match.group(2))
        if key is None or value is None:
            raise ValueError(f"invalid Lua escape at {path}:{line_no}")
        if key in values:
            raise ValueError(f"duplicate seed catalog key {key!r}: {path}")
        values[key] = value
    return values


def seed_directory(profile: str, root: str | Path = ROOT) -> Path:
    name = "gsc-gs" if profile in {"gsc", "gsc-gs"} else profile
    return Path(root) / "seeds" / "zh-Hans" / name


def load_seed(profile: str, root: str | Path = ROOT) -> dict[str, Any]:
    """Verify provenance hashes and return parsed catalogs for a profile."""
    directory = seed_directory(profile, root)
    metadata_path = directory / "seed.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Simplified Chinese seed metadata missing: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("schema") != SEED_SCHEMA or metadata.get("version") != 1:
        raise ValueError(f"unsupported Simplified Chinese seed metadata: {metadata_path}")
    if metadata.get("language") != "zh-Hans":
        raise ValueError(f"seed language must be zh-Hans: {metadata_path}")
    catalogs: dict[str, dict[str, str]] = {}
    crystal_rows: list[tuple[str, str, str]] = []
    for row in metadata.get("files", []):
        relative = Path(str(row.get("path", "")))
        path = directory / relative
        if not path.is_file():
            raise ValueError(f"seed file missing: {path}")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != row.get("sha256"):
            raise ValueError(f"seed file hash mismatch: {path}")
        if relative.parts[:1] == ("lang",) and relative.suffix == ".lua":
            if relative.name in {"literal_handlers.lua", "naming.lua"}:
                continue
            catalogs[relative.stem] = read_lua_catalog(path)
        elif relative.name == "crystal_catalog.json":
            crystal = json.loads(payload.decode("utf-8"))
            if (crystal.get("schema") != CRYSTAL_CATALOG_SCHEMA or
                    crystal.get("version") != 1 or crystal.get("language") != "zh-Hans"):
                raise ValueError(f"unsupported Simplified Chinese Crystal catalog: {path}")
            entries = crystal.get("entries")
            if not isinstance(entries, list):
                raise ValueError(f"invalid Simplified Chinese Crystal catalog entries: {path}")
            qids: set[str] = set()
            for row in entries:
                if (not isinstance(row, dict) or
                        not all(isinstance(row.get(key), str) and row[key]
                                for key in ("qid", "english", "translation")) or
                        row["qid"] in qids):
                    raise ValueError(f"invalid or duplicate Simplified Chinese Crystal row: {path}")
                qids.add(row["qid"])
                crystal_rows.append((row["qid"], row["english"], row["translation"]))
    overlay_dir = Path(root) / "config" / "zh-Hans" / "mod_overlays"
    overlays: list[dict[str, Any]] = []
    for path in sorted(overlay_dir.glob("*.json")) if overlay_dir.is_dir() else ():
        overlay = json.loads(path.read_text(encoding="utf-8"))
        if overlay.get("schema") != "gen1recomp-translation-mods/zh-mod-overlay" or overlay.get("version") != 1:
            raise ValueError(f"unsupported Simplified Chinese mod overlay: {path}")
        entries = overlay.get("entries")
        if not isinstance(entries, dict) or not all(
            isinstance(key, str) and key and isinstance(value, str) and value
            for key, value in entries.items()
        ):
            raise ValueError(f"invalid Simplified Chinese mod overlay entries: {path}")
        strings = catalogs.setdefault("strings", {})
        conflicts = {
            key for key, value in entries.items()
            if key in strings and strings[key] and strings[key] != value
        }
        decisions = overlay.get("reviewed_overrides") or {}
        if not isinstance(decisions, dict) or not all(
            isinstance(key, str) and isinstance(reason, str) and reason
            for key, reason in decisions.items()
        ):
            raise ValueError(f"invalid reviewed mod overlay overrides: {path}")
        unresolved = conflicts - set(decisions)
        if unresolved:
            raise ValueError(f"mod overlay conflicts with seed strings: {sorted(unresolved)!r}")
        strings.update(entries)
        overlays.append({"path": path, "metadata": overlay})
    return {
        "metadata": metadata,
        "directory": directory,
        "catalogs": catalogs,
        "crystal_rows": crystal_rows,
        "mod_overlays": overlays,
    }
