#!/usr/bin/env python3
"""Audit current main-checkout engine keys against Chinese catalogs."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.engine import _decode_lua_string
from pipeline.engine_backlog import (
    iter_literal_strings_callsites,
    iter_render_literal_callsites,
    iter_romtext_fallback_callsites,
)
from pipeline.engine_scope import classify_catalog, complete_engine_keys, load_scope
from pipeline.seed import load_seed


_LUA_KEY = re.compile(r'\[("(?:\\.|[^"\\])*")]\s*=')


def locale_keys(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {
        value for value in (
            _decode_lua_string(match.group(1)) for match in _LUA_KEY.finditer(text)
        ) if value is not None
    }


def audit(checkout: Path) -> dict:
    scope = load_scope()
    strings = iter_literal_strings_callsites(checkout)
    render = iter_render_literal_callsites(checkout)
    romtext = iter_romtext_fallback_callsites(checkout)
    callsites = strings + render + romtext
    keys = complete_engine_keys(callsites, scope)
    classified = classify_catalog(keys, callsites, scope)
    built_in = set()
    for relative in ("src/locales/zh_CN.lua", "src/locales/zh_CN_app.lua"):
        built_in.update(locale_keys(checkout / relative))
    seed_keys = set(load_seed("rby")["catalogs"]["strings"])
    covered = keys & (built_in | seed_keys)
    missing = sorted(keys - covered)
    return {
        "schema": "gen1recomp-translation-mods/zh-coverage-audit",
        "version": 1,
        "checkout": str(checkout.resolve()),
        "counts": {
            "strings_callsites": len(strings),
            "render_literal_callsites": len(render),
            "romtext_fallback_callsites": len(romtext),
            "engine_keys": len(keys),
            "built_in_keys": len(built_in),
            "seed_engine_keys": len(seed_keys),
            "covered": len(covered),
            "missing": len(missing),
        },
        "categories": dict(sorted(Counter(row["category"] for row in classified.values()).items())),
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.checkout)
    body = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    print(body, end="")
    return 1 if report["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
