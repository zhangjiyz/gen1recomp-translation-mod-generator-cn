import hashlib
import tempfile
import unittest
from pathlib import Path

from pipeline.builder import BuildError
from pipeline.zh_seed_build import crystal_catalog_from_symbols


class CrystalSymbolCatalogTests(unittest.TestCase):
    def test_builds_pointer_catalog_without_rom(self):
        body = b"3A:4567 ExampleText\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pokecrystal.sym"
            path.write_bytes(body)
            catalog, stats, entries = crystal_catalog_from_symbols(
                path,
                [("maps/Test.asm:ExampleText:block", "Hello {PLAYER}", "你好{PLAYER}")],
                expected_sha256=hashlib.sha256(body).hexdigest(),
            )
        self.assertEqual(catalog, {"3a:4567": "你好{PLAYER}"})
        self.assertEqual(stats["translated"], 1)
        self.assertEqual(stats["fallback_english"], 0)
        self.assertEqual(entries[0].translation, "你好{PLAYER}")

    def test_missing_label_and_placeholder_mismatch_fall_back(self):
        body = b"01:4000 HasLabel\n"
        rows = [
            ("maps/Test.asm::missing", "Hello", "你好"),
            ("maps/Test.asm:HasLabel:block", "Hello {PLAYER}", "你好"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pokecrystal.sym"
            path.write_bytes(body)
            catalog, stats, entries = crystal_catalog_from_symbols(
                path, rows, expected_sha256=hashlib.sha256(body).hexdigest(),
            )
        self.assertEqual(catalog, {})
        self.assertEqual(stats["fallback_english"], 2)
        self.assertEqual(len(stats["missing_labels"]), 1)
        self.assertEqual(len(stats["rejected_placeholder_mismatch"]), 1)
        self.assertIsNone(entries[0].translation)

    def test_rejects_unpinned_symbol_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pokecrystal.sym"
            path.write_text("00:4000 Label\n", encoding="utf-8")
            with self.assertRaises(BuildError):
                crystal_catalog_from_symbols(path, [], expected_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
