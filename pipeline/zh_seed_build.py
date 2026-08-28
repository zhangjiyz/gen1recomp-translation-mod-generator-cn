"""ROM-free builders for the reviewed Simplified Chinese seed catalogs.

This path packages the already pointer-keyed RBY/GS catalogs and derives
Crystal pointers from pret/pokecrystal's public linker symbol table. The
regular interactive builders remain the stronger, ROM-backed refresh audit.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from .builder import BuildError, _run, inspect_archive
from .generate import lua_string
from .gs_join import GsJoinEntry, NO_MATCH, OVERRIDE
from .gs_mod import generate_gs_mod, gs_archive_name
from .mod import generate_mod
from .orchestration import package_release
from .project import project_version, resource_root
from .seed import load_seed
from .tokens import check_placeholders


CRYSTAL_SYMBOL_REVISION = "cc6fc04f19c645f5c40f64f8d88b2ab42c7bdde8"
CRYSTAL_SYMBOL_SHA256 = "697fe20b3c659273a3ab8aa85db2eb78dcf674a3dd17c98b52fc1dddd37783f2"
CRYSTAL_ROM_SHA1 = "f4cd194bdee0d04ca4eac29e09b8e4e9d818c133"
_SYMBOL_LINE = re.compile(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)")


def _crystal_symbol_decisions() -> dict[str, str]:
    path = resource_root() / "config" / "gsc" / "crystal_symbol_decisions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("schema") != "gen1recomp-translation-mods/crystal-symbol-decisions"
            or data.get("version") != 1 or not isinstance(data.get("entries"), dict)):
        raise BuildError(f"unsupported Crystal symbol decisions: {path}")
    decisions: dict[str, str] = {}
    for qid, row in data["entries"].items():
        if (not isinstance(qid, str) or not qid or not isinstance(row, dict)
                or not isinstance(row.get("symbol"), str) or not row["symbol"]
                or not isinstance(row.get("reason"), str) or not row["reason"]):
            raise BuildError(f"invalid Crystal symbol decision for {qid!r}")
        decisions[qid] = row["symbol"]
    return decisions


def _engine_zh_font(engine: Path) -> tuple[Path, int]:
    root = engine / "assets" / "fonts" / "fusionpixel"
    candidates = (
        (root / "fusion-pixel-12px-proportional-zh_hans.ttf", 12),
        (root / "fusion-pixel-10px-proportional-zh_hans.ttf", 10),
    )
    for path, size in candidates:
        if path.is_file():
            return path, size
    raise BuildError(f"Simplified Chinese Fusion Pixel font missing under {root}")


def _install_engine_zh_font(mod_dir: Path, engine: Path) -> None:
    """Install the main checkout's already licensed zh-Hans runtime font."""
    source, size = _engine_zh_font(engine)
    font_dir = mod_dir / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, font_dir / source.name)
    license_path = source.parent / "OFL.txt"
    if not license_path.is_file():
        raise BuildError(f"Fusion Pixel license missing: {license_path}")
    shutil.copy2(license_path, font_dir / "OFL.txt")
    main = mod_dir / "main.lua"
    body = main.read_text(encoding="utf-8")
    old = 'mod.content.font:register("ttf", {})'
    new = (
        'mod.content.font:register("ttf", '
        f'{{ file = mod.assets:path("fonts/{source.name}"), size = {size} }})'
    )
    if old not in body:
        raise BuildError("generated mod does not contain the Plain Pixel font registration")
    main.write_text(body.replace(old, new, 1), encoding="utf-8")


def _copy_seed_catalogs(seed: dict, mod_dir: Path) -> None:
    source = seed["directory"] / "lang"
    destination = mod_dir / "lang"
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.glob("*.lua")):
        shutil.copy2(path, destination / path.name)
    # load_seed() merges reviewed third-party Mod overlays into the in-memory
    # catalogs. Copying only the immutable seed files would report those keys
    # in the counts without actually shipping them. Rewrite every loaded
    # catalog so the packaged strings match the catalog that was validated.
    for name, entries in sorted(seed["catalogs"].items()):
        lines = ["return {"]
        lines.extend(
            f"  [{lua_string(key)}] = {lua_string(value)},"
            for key, value in sorted(entries.items())
        )
        lines.append("}")
        (destination / f"{name}.lua").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _env(luajit: str | Path | None) -> dict[str, str] | None:
    result = dict(os.environ)
    # Modkit records an informational packed_at field. Pin it so two seed
    # builds over identical inputs are byte-for-byte identical.
    result["SOURCE_DATE_EPOCH"] = "0"
    result["PYTHONUTF8"] = "1"
    if luajit is not None:
        result["MODKIT_LUAJIT"] = str(luajit)
        result["LUA"] = str(luajit)
    return result


def crystal_catalog_from_symbols(
    symbols_path: str | Path,
    rows: list[tuple[str, str, str]],
    *,
    expected_sha256: str | None = CRYSTAL_SYMBOL_SHA256,
) -> tuple[dict[str, str], dict, list[GsJoinEntry]]:
    """Resolve source-labelled Crystal translations without reading a ROM."""
    symbols_path = Path(symbols_path)
    payload = symbols_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise BuildError(
            f"pokecrystal symbol hash mismatch: expected {expected_sha256}, got {digest}"
        )
    symbols: dict[str, str] = {}
    duplicates: set[str] = set()
    for raw in payload.decode("utf-8").splitlines():
        match = _SYMBOL_LINE.match(raw)
        if not match:
            continue
        name = match.group(3)
        pointer = f"{int(match.group(1), 16):02x}:{int(match.group(2), 16):04x}"
        if name in symbols and symbols[name] != pointer:
            duplicates.add(name)
        else:
            symbols[name] = pointer

    catalog: dict[str, str] = {}
    entries: list[GsJoinEntry] = []
    missing_labels: list[str] = []
    rejected_placeholders: list[str] = []
    duplicate_pointers: list[str] = []
    decisions = _crystal_symbol_decisions()
    for qid, english, translation in rows:
        parts = qid.split(":", 2)
        label = parts[1] if len(parts) == 3 else ""
        symbol = decisions.get(qid, label)
        pointer = symbols.get(symbol) if symbol and symbol not in duplicates else None
        if pointer is None:
            missing_labels.append(qid)
            continue
        if check_placeholders(english, translation):
            rejected_placeholders.append(qid)
            entries.append(GsJoinEntry(pointer, label, english, None, NO_MATCH, qid))
            continue
        if pointer in catalog:
            duplicate_pointers.append(pointer)
            continue
        catalog[pointer] = translation
        entries.append(GsJoinEntry(pointer, label, english, translation, OVERRIDE, qid))
    if duplicate_pointers:
        raise BuildError(f"duplicate Crystal symbol pointers: {sorted(set(duplicate_pointers))[:10]!r}")
    stats = {
        "source_rows": len(rows),
        "translated": len(catalog),
        "fallback_english": len(missing_labels) + len(rejected_placeholders),
        "missing_labels": missing_labels,
        "rejected_placeholder_mismatch": rejected_placeholders,
        "symbol_revision": CRYSTAL_SYMBOL_REVISION,
        "symbol_sha256": digest,
        "compatible_rom_sha1": CRYSTAL_ROM_SHA1,
    }
    return catalog, stats, entries


def _validation(mode: str, counts: dict, *, crystal: dict | None = None) -> dict:
    result = {
        "schema": 1,
        "mode": mode,
        "policy": "english-fallback",
        "catalog_entries": counts,
        "note": (
            "Built from reviewed versioned catalogs without a ROM. Pointer and id "
            "re-extraction validation was not run; use the ROM-backed builder for that audit."
        ),
    }
    if crystal is not None:
        result["crystal"] = crystal
    return result


def _attach_validation(mod_dir: Path, validation: dict) -> None:
    path = mod_dir / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["validation"] = validation
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_rby_zh_seed_without_rom(
    engine: str | Path,
    destination: str | Path,
    *,
    build_root: str | Path,
    luajit: str | Path | None = None,
) -> tuple[Path, dict]:
    engine = Path(engine).resolve()
    destination = Path(destination).resolve()
    build_root = Path(build_root).resolve()
    seed = load_seed("rby")
    catalogs = seed["catalogs"]
    yellow_catalogs = {
        name.removesuffix("_yellow"): values
        for name, values in catalogs.items() if name.endswith("_yellow")
    }
    mod_dir = build_root / "translation-zh-hans"
    if mod_dir.exists():
        shutil.rmtree(mod_dir)
    generate_mod(
        [], mod_dir, mod_id="translation-zh-hans", language="zh-Hans",
        target_name="简体中文（红、蓝、黄）",
        target_description=(
            "Simplified Chinese translation rebuilt from reviewed, provenance-pinned "
            "catalog seeds; unmatched text remains English."
        ),
        yellow_catalogs=yellow_catalogs,
    )
    _copy_seed_catalogs(seed, mod_dir)
    _install_engine_zh_font(mod_dir, engine)
    counts = {name: len(values) for name, values in sorted(catalogs.items())}
    _attach_validation(mod_dir, _validation("rom-free-seed", counts))
    archive_name = f"translation-zh-hans-{project_version()}.zip"
    archive = package_release(
        mod_dir, engine, engine / "tools" / "modkit.py", build_root,
        destination, archive_name, base="fixture", env=_env(luajit),
    )
    inspect_archive(archive)
    return archive, {"catalog_entries": counts, "total_entries": sum(counts.values())}


def build_gsc_zh_seed_without_rom(
    engine: str | Path,
    symbols_path: str | Path,
    destination: str | Path,
    *,
    build_root: str | Path,
    luajit: str | Path | None = None,
) -> tuple[Path, dict]:
    engine = Path(engine).resolve()
    destination = Path(destination).resolve()
    build_root = Path(build_root).resolve()
    seed = load_seed("gsc")
    catalogs = seed["catalogs"]
    crystal_catalog, crystal_stats, _entries = crystal_catalog_from_symbols(
        symbols_path, seed["crystal_rows"],
    )
    mod_dir = build_root / "translation-zh-hans-gen2"
    if mod_dir.exists():
        shutil.rmtree(mod_dir)
    extra = {key: value for key, value in catalogs.items() if key != "dialogue"}
    generate_gs_mod(
        mod_dir, language="zh-Hans", target_name="简体中文（金、银、水晶）",
        target_description=(
            "Simplified Chinese translation rebuilt from reviewed Gold/Silver catalogs "
            "and a provenance-pinned Crystal symbol map; unmatched text remains English."
        ),
        text_catalog=catalogs["dialogue"], extra_catalogs=extra,
        crystal_text_catalog=crystal_catalog,
    )
    _copy_seed_catalogs(seed, mod_dir)
    _install_engine_zh_font(mod_dir, engine)
    counts = {name: len(values) for name, values in sorted(catalogs.items())}
    _attach_validation(
        mod_dir, _validation("rom-free-seed-and-symbols", counts, crystal=crystal_stats),
    )
    if luajit is None:
        raise BuildError("Crystal runtime gate requires LuaJIT")
    crystal_only = next(
        (pointer for pointer in sorted(crystal_catalog) if pointer not in catalogs["dialogue"]),
        None,
    )
    if crystal_only is None:
        raise BuildError("Crystal runtime gate requires a Crystal-only translated pointer")
    expectation = build_root / ".crystal-dialogue-gate.json"
    expectation.parent.mkdir(parents=True, exist_ok=True)
    expectation.write_text(
        json.dumps({"pointer": crystal_only, "value": crystal_catalog[crystal_only]}, ensure_ascii=False),
        encoding="utf-8",
    )
    try:
        _run([
            str(luajit), str(resource_root() / "tools" / "gate_crystal_dialogue.lua"),
            str(engine), str(mod_dir), str(expectation),
        ])
    finally:
        expectation.unlink(missing_ok=True)
    archive_name = gs_archive_name("zh-Hans", project_version())
    archive = package_release(
        mod_dir, engine, engine / "tools" / "modkit.py", build_root,
        destination, archive_name, base="fixture", env=_env(luajit),
    )
    inspect_archive(archive)
    return archive, {
        "catalog_entries": counts,
        "gold_silver_entries": sum(counts.values()),
        "crystal": crystal_stats,
    }


def build_all_zh_seeds_without_rom(
    engine: str | Path,
    symbols_path: str | Path,
    destination: str | Path,
    *,
    build_root: str | Path,
    luajit: str | Path | None = None,
) -> dict:
    build_root = Path(build_root)
    rby, rby_stats = build_rby_zh_seed_without_rom(
        engine, destination, build_root=build_root / "rby", luajit=luajit,
    )
    gsc, gsc_stats = build_gsc_zh_seed_without_rom(
        engine, symbols_path, destination, build_root=build_root / "gsc", luajit=luajit,
    )
    return {
        "rby": {"archive": str(rby), **rby_stats},
        "gsc": {"archive": str(gsc), **gsc_stats},
    }
