import hashlib
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from pipeline.seed import load_seed, read_lua_catalog
from pipeline.gs_join import NO_MATCH, audit_join, join_gs_pointers
from pipeline.gs_text import GsTextRecord
from pipeline.tokens import check_placeholders
from tools.import_crystal_zh_catalog import _runtime_text


class SeedTests(unittest.TestCase):
    def test_read_lua_catalog_decodes_generated_escapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "strings.lua"
            path.write_text('return {\n  ["A\\nB"] = "中\\012文",\n}\n', encoding="utf-8")
            self.assertEqual(read_lua_catalog(path), {"A\nB": "中\f文"})

    def test_load_seed_verifies_each_file_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "seeds" / "zh-Hans" / "rby"
            lang = directory / "lang"
            lang.mkdir(parents=True)
            payload = b'return {\n  ["HELLO"] = "\xe4\xbd\xa0\xe5\xa5\xbd",\n}\n'
            (lang / "strings.lua").write_bytes(payload)
            metadata = {
                "schema": "gen1recomp-translation-mods/zh-seed",
                "version": 1,
                "profile": "rby",
                "language": "zh-Hans",
                "files": [{
                    "path": "lang/strings.lua",
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }],
            }
            (directory / "seed.json").write_text(json.dumps(metadata), encoding="utf-8")
            seed = load_seed("rby", root)
            self.assertEqual(seed["catalogs"]["strings"], {"HELLO": "你好"})
            (lang / "strings.lua").write_text("return {}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_seed("rby", root)

    def test_repository_seed_counts_are_stable(self):
        rby = load_seed("rby")
        gs = load_seed("gsc")
        self.assertEqual(len(rby["catalogs"]["dialogue"]), 2592)
        self.assertEqual(len(rby["catalogs"]["strings"]), 1319)
        self.assertEqual(len(gs["catalogs"]["dialogue"]), 3045)
        self.assertEqual(len(gs["catalogs"]["strings"]), 466)
        self.assertEqual(len(gs["crystal_rows"]), 5157)
        self.assertEqual(len({row[0] for row in gs["crystal_rows"]}), 5157)
        self.assertEqual(gs["catalogs"]["strings"]["MEDIUM"], "中")
        self.assertEqual(rby["catalogs"]["strings"]["WATER"], "水面效果")
        self.assertEqual(len(rby["mod_overlays"]), 1)

    def test_crystal_workbook_controls_match_gen2_runtime_markers(self):
        lines = ["你好【0】", "第一行", "第二行", "", "下一页【1】"]
        controls = ["text_ram wStringBuffer1", "text_decimal wScriptVar, 1, 3"]
        self.assertEqual(
            _runtime_text(lines, controls, next_cr=False),
            "你好{STRBUF}\n第一行\v第二行\f下一页{NUM}",
        )

    def test_crystal_seed_conservative_join_is_placeholder_safe(self):
        rows = load_seed("gsc")["crystal_rows"]
        records = [
            GsTextRecord(f"{index // 0x4000:02x}:{0x4000 + index % 0x4000:04x}", english, qid)
            for index, (qid, english, _translation) in enumerate(rows)
        ]
        entries, stats = join_gs_pointers(records, rows)
        entries = [
            replace(entry, translation=None, provenance=NO_MATCH)
            if entry.translation and check_placeholders(entry.english, entry.translation)
            else entry
            for entry in entries
        ]
        self.assertEqual(stats["unique"], 4717)
        self.assertEqual(stats["harmless_ambiguous"], 387)
        self.assertEqual(stats["unresolved"], 19)
        self.assertEqual(sum(entry.translation is not None for entry in entries), 5094)
        self.assertEqual(audit_join(entries), [])


if __name__ == "__main__":
    unittest.main()
