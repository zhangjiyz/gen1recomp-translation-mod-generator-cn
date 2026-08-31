#!/usr/bin/env python3
"""Build both Simplified Chinese mods from reviewed seeds, without ROMs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.project import which_luajit
from pipeline.zh_seed_build import build_all_zh_seeds_without_rom


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gen1recomp", type=Path, required=True,
                        help="current main-engine checkout (not a ROM)")
    parser.add_argument("--crystal-symbols", type=Path, required=True,
                        help="pinned pret/pokecrystal linker .sym file")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--build-root", type=Path, default=ROOT / ".cache" / "zh-seed-build")
    parser.add_argument("--luajit", default=which_luajit())
    args = parser.parse_args()
    if not args.luajit:
        parser.error("LuaJIT is required by Modkit packaging")
    report = build_all_zh_seeds_without_rom(
        args.gen1recomp, args.crystal_symbols, args.output,
        build_root=args.build_root, luajit=args.luajit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
