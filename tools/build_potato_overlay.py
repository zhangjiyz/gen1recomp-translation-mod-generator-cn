#!/usr/bin/env python3
"""Build the PotatoVoxel zh-Hans compatibility overlay from reviewed text."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.engine import _decode_lua_string
from pipeline.engine_backlog import (
    _decode_lua_literal,
    _read_lua_literal,
    _strip_lua_comments,
    iter_literal_strings_callsites,
)


_PAIR = re.compile(
    r'\[("(?:\\.|[^"\\])*")]\s*=\s*("(?:\\.|[^"\\])*")'
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locale", required=True, type=Path)
    parser.add_argument("--mod-root", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "config" / "zh-Hans" / "mod_overlays" / "potato_voxel.json",
    )
    args = parser.parse_args()
    locale = args.locale.read_text(encoding="utf-8")
    marker = "-- Third-party option schemas are translated when LauncherSettings imports"
    start = locale.find(marker)
    if start < 0:
        raise ValueError("PotatoVoxel locale marker not found")
    section = locale[start:]
    entries: dict[str, str] = {}
    for match in _PAIR.finditer(section):
        key = _decode_lua_string(match.group(1))
        value = _decode_lua_string(match.group(2))
        if key is not None and value is not None and value:
            entries[key] = value

    explicit = sorted({row["source"] for row in iter_literal_strings_callsites(args.mod_root)})
    settings = args.mod_root / "lib" / "SettingsFeature.lua"
    settings_text = settings.read_text(encoding="utf-8")
    settings_block = settings_text.split("local settings = {", 1)[1].split("local feature =", 1)[0]
    cleaned = _strip_lua_comments(settings_block)
    help_lines: list[str] = []
    index = 0
    while index < len(cleaned):
        if cleaned[index] in {"'", '"', "["}:
            token = _read_lua_literal(settings_block, index)
            if token is not None:
                value = _decode_lua_literal(token[0])
                if value is not None:
                    help_lines.append(value)
                index = token[1]
                continue
        index += 1
    missing_explicit = sorted(set(explicit) - set(entries))
    if missing_explicit:
        raise ValueError(f"PotatoVoxel explicit Strings keys missing from overlay: {missing_explicit!r}")
    body = {
        "schema": "gen1recomp-translation-mods/zh-mod-overlay",
        "version": 1,
        "language": "zh-Hans",
        "mod": {"id": "potato_voxel", "version": "1.9.3"},
        "source_package": {
            "name": args.source_zip.name,
            "sha256": sha256(args.source_zip),
        },
        "coverage": {
            "catalog_entries": len(entries),
            "explicit_strings_callsites": len(iter_literal_strings_callsites(args.mod_root)),
            "explicit_strings_unique": len(explicit),
            "explicit_strings_covered": len(explicit),
            "schema_help_physical_lines": len(help_lines),
            "schema_help_unique_lines": len(set(help_lines)),
            "schema_help_rendered_by_current_mod": 0,
            "note": (
                "SettingsFeature help arrays are schema metadata but PotatoVoxel 1.9.3 "
                "does not render them; translate them when a UI begins displaying descriptions."
            ),
        },
        "reviewed_overrides": {
            "MEDIUM": (
                "Use the quality-level meaning 中. The old GSC strings seed matched the "
                "trainer class Medium; trainer_class_names owns that separate context."
            ),
            "WATER": (
                "Use the PotatoVoxel and launcher option label 水面效果 instead of the "
                "short RBY type-style value 水."
            ),
        },
        "entries": dict(sorted(entries.items())),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(body["coverage"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
