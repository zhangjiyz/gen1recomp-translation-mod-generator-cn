from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from pipeline.zh_hans import build_zh_hans_parallel, load_dialogue_decisions, read_xlsx_rows
from pipeline.zh_hans_rby import build_zh_hans_rby_parallel, load_rby_dialogue_decisions
from pipeline.engine import load_engine_overrides


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def column_name(index: int) -> str:
    result = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def write_xlsx(path: Path, sheets: dict[str, list[list[str | None]]]) -> None:
    ET.register_namespace("", MAIN_NS)
    ET.register_namespace("r", DOC_REL_NS)
    workbook = ET.Element(f"{{{MAIN_NS}}}workbook")
    sheet_list = ET.SubElement(workbook, f"{{{MAIN_NS}}}sheets")
    relationships = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    worksheet_xml: dict[str, bytes] = {}
    for sheet_index, (name, rows) in enumerate(sheets.items(), 1):
        relation_id = f"rId{sheet_index}"
        sheet = ET.SubElement(sheet_list, f"{{{MAIN_NS}}}sheet")
        sheet.set("name", name)
        sheet.set("sheetId", str(sheet_index))
        sheet.set(f"{{{DOC_REL_NS}}}id", relation_id)
        relation = ET.SubElement(relationships, f"{{{PKG_REL_NS}}}Relationship")
        relation.set("Id", relation_id)
        relation.set("Target", f"worksheets/sheet{sheet_index}.xml")
        relation.set("Type", f"{DOC_REL_NS}/worksheet")

        worksheet = ET.Element(f"{{{MAIN_NS}}}worksheet")
        sheet_data = ET.SubElement(worksheet, f"{{{MAIN_NS}}}sheetData")
        for row_index, values in enumerate(rows, 1):
            row = ET.SubElement(sheet_data, f"{{{MAIN_NS}}}row", {"r": str(row_index)})
            for column_index, value in enumerate(values):
                if value is None:
                    continue
                cell = ET.SubElement(
                    row, f"{{{MAIN_NS}}}c",
                    {"r": f"{column_name(column_index)}{row_index}", "t": "inlineStr"},
                )
                inline = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
                text = ET.SubElement(inline, f"{{{MAIN_NS}}}t")
                text.text = str(value)
        worksheet_xml[f"xl/worksheets/sheet{sheet_index}.xml"] = ET.tostring(
            worksheet, encoding="utf-8", xml_declaration=True,
        )

    with zipfile.ZipFile(path, "w") as output:
        output.writestr("xl/workbook.xml", ET.tostring(workbook, encoding="utf-8", xml_declaration=True))
        output.writestr(
            "xl/_rels/workbook.xml.rels",
            ET.tostring(relationships, encoding="utf-8", xml_declaration=True),
        )
        for name, body in worksheet_xml.items():
            output.writestr(name, body)


class ChineseSourceTests(unittest.TestCase):
    def test_xlsx_reader_preserves_unicode_and_sparse_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.xlsx"
            write_xlsx(path, {"中文": [["甲", None, "乙"]]})
            self.assertEqual(read_xlsx_rows(path), {"中文": [{0: "甲", 2: "乙"}]})

    def test_builds_rby_parallel_from_human_blocks_data_and_pokedex(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus"
            source = root / "source"
            corpus.mkdir()
            source.mkdir()
            qids = [
                "rb.map.RenamedText",
                "rb.map.LabelMatchedText",
                "rb.names.ItemNames.1",
                "rb.main_menu.MenuText",
                "rb.dex_entries.BulbasaurDexEntry.Species",
                "rb.dex_text.BulbasaurDexEntry",
                "rb.unmapped.NoSource",
                "y.test.CurrentPriceText",
            ]
            english = [
                "{text_start}Original wording.<DONE>",
                "{text_start}Changed ROM wording.<DONE>",
                "MASTER BALL@",
                "CONTINUE<NEXT>OPTION@",
                "SEED@",
                "{text_start}Stores energy<NEXT>in its seed.<DEXEND>@",
                "NO SOURCE@",
                "{text_start}Pay ¥{text_bcd wPriceTemp, 3 | LEADING_ZEROES | LEFT_ALIGN}.<DONE>",
            ]
            (corpus / "qid_msg.txt").write_text("\n".join(qids) + "\n", encoding="utf-8")
            (corpus / "en_msg.txt").write_text("\n".join(english) + "\n", encoding="utf-8")

            write_xlsx(source / "core.xlsx", {"text": [
                ["source.asm"],
                ["_OldText::", None, None, None, "_OldText::"],
                [None, "text", "Original wording.", None, None, "text", "人工原文。"],
                [None, "done", None, None, None, "done"],
                ["_LabelMatchedText::", None, None, None, "_LabelMatchedText::"],
                [None, "text", "Older wording.", None, None, "text", "按标签对齐。"],
                [None, "done", None, None, None, "done"],
                ["_OldPriceText::", None, None, None, "_OldPriceText::"],
                [None, "text", "Pay ¥", None, None, "text", "支付¥"],
                [None, "text_bcd", "wPriceTemp, $c3", None, None, "text_bcd", "wPriceTemp, $c3"],
                [None, "text", ".", None, None, "text", "。"],
                [None, "done", None, None, None, "done"],
            ]})
            write_xlsx(source / "data.xlsx", {"Main": [
                ["source.asm"],
                [None, '"MASTER BALL"', "大师球"],
                [None, '"CONTINUE"', "继续游戏"],
                [None, '"OPTION@"', "更改设置@"],
            ]})
            write_xlsx(source / "dexEntry.xlsx", {"Sheet1": [
                ["header"],
                [None, None, None, None, None, None, None, None, None,
                 "_BulbasaurDexEntry", None, None, None, "种子", None, None,
                 "_BulbasaurDexEntry"],
            ]})
            write_xlsx(source / "dex.xlsx", {"dex": [
                ["dex.asm"],
                ["_BulbasaurDexEntry::", None, None, None, "_BulbasaurDexEntry::"],
                [None, "text", "Stores energy", None, None, "text", "种子里储存着能量。"],
                [None, "next", "in its seed.", None, None, "dex"],
            ]})

            decisions = root / "decisions.json"
            decisions.write_text(json.dumps({
                "schema": "gen1recomp-translation-mods/zh-hans-rby-dialogue-decisions",
                "version": 1,
                "entries": {
                    "y.test.CurrentPriceText": {
                        "source_label": "OldPriceText",
                        "reason": "Reviewed same price event.",
                    },
                },
            }), encoding="utf-8")
            stats = build_zh_hans_rby_parallel(
                corpus, source_root=source, dialogue_decisions=decisions
            )
            targets = (corpus / "zh-Hans_msg.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(targets[0], "{text_start}人工原文。<DONE>")
            self.assertEqual(targets[1], "{text_start}按标签对齐。<DONE>")
            self.assertEqual(targets[2], "大师球@")
            self.assertEqual(targets[3], "继续游戏<NEXT>更改设置@")
            self.assertEqual(targets[4], "种子@")
            self.assertEqual(targets[5], "{text_start}种子里储存着能量。<DEXEND>@")
            self.assertEqual(targets[6], "")
            self.assertEqual(
                targets[7],
                "{text_start}支付¥{text_bcd wPriceTemp, 3 | LEADING_ZEROES | LEFT_ALIGN}{text_start}。<DONE>",
            )
            self.assertEqual(stats.translated, 7)
            self.assertEqual(stats.total, 8)

    def test_reviewed_yellow_aliases_are_traceable(self):
        decisions = load_rby_dialogue_decisions(
            Path("config/rby/zh_hans_yellow_dialogue_decisions.json")
        )
        self.assertEqual(len(decisions), 14)
        self.assertEqual(
            decisions["y.RocketHideoutB4F.RocketHideoutB4FRocketEndBattleText"],
            "RocketHideout4EndBattleText4",
        )
        self.assertEqual(
            decisions["y.SafariZoneGate.SafariZoneGateSafariZoneWorker1ThatllBe500PleaseText"],
            "SafariZoneEntranceText_9e747",
        )

    def test_rby_chinese_engine_gap_overrides_are_complete_and_reviewed(self):
        overrides = load_engine_overrides(Path("overrides/zh-Hans/rby/engine.json"))
        self.assertEqual(len(overrides), 148)
        self.assertEqual(overrides["BUY"]["override"], "购买")
        self.assertEqual(overrides["EXIT GAME"]["override"], "关闭")
        expected_port_menu = {
            "BATTLE LAYOUT": "战斗布局",
            "BATTLE SIZE": "战斗画面尺寸",
            "BATTLE HUD": "战斗界面",
            "BATTLE BG": "战斗背景",
            "UI LAYOUT": "界面布局",
            "RULESET": "战斗规则",
            "PIKACHU VOL": "皮卡丘音量",
            "SHADER FX": "着色器效果",
            "SHADER FX 2": "着色器效果2",
            "MODS": "模组",
            "%d INSTALLED": "已安装%d个模组",
            "CONTROLS": "按键设置",
            "RETURN TO MAIN\nMENU?": "返回主菜单？",
            "WINDOWED": "窗口",
            "BORDERLESS": "无边框全屏",
        }
        for source, translated in expected_port_menu.items():
            self.assertEqual(overrides[source]["override"], translated)
        self.assertEqual(overrides["%s\nis refusing!"]["override"], "%s\n不听话！")
        self.assertIn("provenance", overrides["PIKACHU looks\ncontent."])

    def test_rby_visible_text_corrections_remove_debug_and_mixed_english(self):
        data = json.loads(Path("overrides/zh-Hans/rby/corpus.json").read_text(encoding="utf-8"))
        entries = data["entries"]
        for prefix, oak_key in (("rb", "rb.text_2.OakSpeechText1"),
                                ("y", "y.text_3.OakSpeechText1")):
            self.assertNotIn("Debug", entries[oak_key]["override"])
            self.assertEqual(
                entries[f"{prefix}.FuchsiaCity.FuchsiaCityPokemonText"]["override"],
                "{text_start}！<DONE>",
            )
        self.assertIn("出发吧", entries["rb.text_2.OakSpeechText3"]["override"])
        self.assertNotIn("Please", entries["rb.VermilionGym_2.TM24ExplanationText"]["override"])
        self.assertNotIn("You", entries["y.VermilionGym.VermilionGymLTSurgePreBattleText"]["override"])

    def test_reviewed_dialogue_decision_reuses_mismatched_human_source_row(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus"
            corpus.mkdir()
            (corpus / "qid_msg.txt").write_text("gs.test.RewordedText\n", encoding="utf-8")
            (corpus / "en_msg.txt").write_text("US ROM wording.\n", encoding="utf-8")
            dialogue = root / "text.xlsx"
            write_xlsx(dialogue, {
                "标": [
                    ["dmap", "omap", "dlabel", "olabel", "file", "eom", "eom-en", None, "version"],
                    ["source.asm", "COMMON", "RewordedText", "source_reworded", "common.mg", "EOMeom", "EOMeom", None, ""],
                ],
                "文1": [
                    ["英文", None, None, None, None, None, None, None, None, "source_reworded", None],
                    ["Different source wording.", None, None, None, "人工译文。"],
                    ["结束"],
                ],
            })
            empty = root / "empty.xlsx"
            write_xlsx(empty, {"Sheet1": []})
            items = root / "items.txt"
            moves = root / "moves.txt"
            items.write_text("", encoding="utf-8")
            moves.write_text("", encoding="utf-8")
            decisions = root / "decisions.json"
            decisions.write_text(json.dumps({
                "schema": "gen1recomp-translation-mods/zh-hans-dialogue-decisions",
                "version": 1,
                "entries": {
                    "gs.test.RewordedText": {
                        "source_label": "RewordedText",
                        "reason": "Reviewed same event.",
                    },
                },
            }), encoding="utf-8")

            stats = build_zh_hans_parallel(
                corpus,
                dialogue_workbook=dialogue,
                data_workbook=empty,
                dex_workbook=empty,
                item_descriptions=items,
                move_descriptions=moves,
                dialogue_decisions=decisions,
            )
            self.assertEqual(
                (corpus / "zh-Hans_msg.txt").read_text(encoding="utf-8"),
                "{text_start}人工译文。<DONE>\n",
            )
            self.assertEqual(stats.by_source["reviewed-current-dialogue"], 1)

    def test_real_reviewed_dialogue_decisions_are_traceable(self):
        decisions = load_dialogue_decisions(Path("config/gs/zh_hans_dialogue_decisions.json"))
        self.assertEqual(len(decisions), 72)
        self.assertEqual(decisions["gs.common_2.MaySmashText"], "MaySmashText")
        self.assertEqual(decisions["gs.common_2.OakRating12"], "OakRating12")

    def test_chinese_naming_case_controls_are_reviewed_as_one_ui_group(self):
        overrides = load_engine_overrides(Path("overrides/zh-Hans/gs/engine.json"))
        self.assertEqual(overrides["END"]["override"], "完成")
        self.assertEqual(overrides["UPPER"]["override"], "大写")
        self.assertEqual(overrides["lower"]["override"], "小写")
        for key in ("END", "UPPER", "lower"):
            self.assertEqual(overrides[key]["reason"], "engine-contract-gap")
            self.assertIn("Requires in-game layout review", overrides[key]["provenance"])

    def test_builds_parallel_human_chinese_corpus_without_fallback_copying(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus"
            corpus.mkdir()
            qids = [
                "gs.std_text.NurseMornText",
                "gs.other.RenamedNurseText",
                "gs.names.PokemonNames.1",
                "gs.names.MoveNames.1",
                "gs.names.ItemNames.1",
                "gs.class_names.TrainerClassNames.1",
                "gs.landmarks.NewBarkTownName",
                "gs.dex_entries.BulbasaurPokedexEntry.Species",
                "gs.dex_entries_gold.BulbasaurPokedexEntry",
                "gs.dex_entries_silver.BulbasaurPokedexEntry",
                "gs.descriptions.PoundDescription",
                "gs.descriptions.MasterBallDesc",
                "gs.main_menu.Cancel",
                "gs.unmapped.RemainsEnglish",
            ]
            english = [
                "{text_start}Good morning!<LINE>Welcome.<DONE>",
                "{text_start}Good morning!<LINE>Welcome.<DONE>",
                "BULBASAUR@", "POUND@", "MASTER BALL@", "LEADER@",
                "NEW BARK<BSP>TOWN@", "SEED@", "Gold dex@", "Silver dex@",
                "Pounds with forelegs.@", "The best BALL.@", "CANCEL@", "NO SOURCE@",
            ]
            (corpus / "qid_msg.txt").write_text("\n".join(qids) + "\n", encoding="utf-8")
            (corpus / "en_msg.txt").write_text("\n".join(english) + "\n", encoding="utf-8")

            dialogue = root / "text.xlsx"
            header = ["英文", None, None, None, None, None, None, None, None, "msg_heal_11_common", None]
            write_xlsx(dialogue, {
                "标": [
                    ["dmap", "omap", "dlabel", "olabel", "file", "eom", "eom-en", None, "version"],
                    ["data/text/std_text.asm", "COMMON", "NurseMornText", "msg_heal_11_common", "common.mg", "EOMeom", "EOMeom", None, ""],
                ],
                "文1": [
                    header,
                    ["Good morning!", None, None, None, "早上好！"],
                    ["Welcome.", None, None, None, "欢迎光临。"],
                    ["结束"],
                ],
                "宝": [["id", "en", "jp", "zh"], ["N001", "BULBASAUR", "", "妙蛙种子"]],
                "招": [["id", "en", "jp", "zh"], ["M001", "POUND", "", "拍击"]],
                "道GS": [["id", "en", "jp", "zh"], ["ItemName001$", "MASTER BALL", "", "大师球"]],
                "类": [["id", "en", "jp", "zh"], ["Name_P2DL_001$", "LEADER", "", "道馆馆主"]],
                "城GS": [["id", "en", "jp", "zh"], ["name_wakaba", "NEW BARK TOWN", "", "若叶镇"]],
                "其": [["id", "en", "jp", "zh"]],
            })
            data = root / "data.xlsx"
            write_xlsx(data, {"Misc": [[None, None, None, None, '"CANCEL@"', '"取消@"']]})
            dex = root / "dex.xlsx"
            write_xlsx(dex, {"Sheet1": [[None, "妙蛙种子", "bulbasaur", "种子", None, "金;版/说明@", None, "银;版/说明@"]]})
            item_text = root / "items.txt"
            move_text = root / "moves.txt"
            item_text.write_text("001,1,最好的球{50}\n", encoding="utf-8")
            move_text.write_text("002,1,用手或尾巴{P59}拍打对手\n", encoding="utf-8")

            stats = build_zh_hans_parallel(
                corpus,
                dialogue_workbook=dialogue,
                data_workbook=data,
                dex_workbook=dex,
                item_descriptions=item_text,
                move_descriptions=move_text,
            )
            targets = (corpus / "zh-Hans_msg.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(targets), len(qids))
            self.assertEqual(targets[0], "{text_start}早上好！<LINE>欢迎光临。<DONE>")
            self.assertEqual(targets[1], targets[0])
            self.assertEqual(targets[2:7], ["妙蛙种子@", "拍击@", "大师球@", "道馆馆主@", "若叶镇@"])
            self.assertEqual(targets[7:10], ["种子@", "金<NEXT>版@说明@", "银<NEXT>版@说明@"])
            self.assertEqual(targets[10:13], ["用手或尾巴<NEXT>拍打对手@", "最好的球@", "取消@"])
            self.assertEqual(targets[13], "")
            self.assertEqual(stats.translated, 13)
            self.assertEqual(stats.total, 14)


if __name__ == "__main__":
    unittest.main()
