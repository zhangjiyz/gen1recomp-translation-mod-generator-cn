"""Build a Simplified Chinese Gold/Silver parallel corpus from human sources.

The upstream PokeCorpus snapshot does not publish a Chinese target file.  This
module keeps the generator reproducible without checking a third party's full
translation into this repository: it reads hash-pinned workbooks/text tables
from TomJinW's Gold/Silver fan-translation projects and materializes the one
parallel file needed by the existing conservative join pipeline.

Only exact labels, numeric registry indices, exact source strings, and the
projects' own table order are used.  Missing rows stay empty and therefore
fall back to English later; this importer never invents or machine-translates
prose.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Iterable, Mapping
import xml.etree.ElementTree as ET
import zipfile


ZH_HANS = "zh-Hans"
ZH_HANS_DIALOGUE_DECISIONS_SCHEMA = "gen1recomp-translation-mods/zh-hans-dialogue-decisions"
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REF_RE = re.compile(r"([A-Z]+)[0-9]+")
_VERSION_SUFFIX_RE = re.compile(r"\^(?:G|S|GS)$")


class ChineseSourceError(ValueError):
    """A pinned Chinese source cannot be mapped safely."""


@dataclass(frozen=True)
class ChineseCorpusStats:
    translated: int
    total: int
    by_source: Mapping[str, int]


def load_dialogue_decisions(path: str | Path | None) -> dict[str, str]:
    """Load reviewed PokeCorpus-qid to Chinese-workbook-label alignments.

    Decisions carry no translated prose. They only authorize a known workbook
    row when the US ROM wording differs from the English reference attached to
    the human Chinese source.
    """
    if path is None:
        return {}
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChineseSourceError(f"invalid Chinese dialogue decisions JSON: {path}") from exc
    if not isinstance(data, dict) or data.get("schema") != ZH_HANS_DIALOGUE_DECISIONS_SCHEMA:
        raise ChineseSourceError("unsupported Chinese dialogue decisions schema")
    if data.get("version") != 1 or not isinstance(data.get("entries"), dict):
        raise ChineseSourceError("Chinese dialogue decisions require version 1 entries")
    result: dict[str, str] = {}
    for qid, row in data["entries"].items():
        if (not isinstance(qid, str) or not qid.startswith("gs.") or
                not isinstance(row, dict) or set(row) != {"source_label", "reason"} or
                not isinstance(row.get("source_label"), str) or not row["source_label"] or
                not isinstance(row.get("reason"), str) or not row["reason"].strip()):
            raise ChineseSourceError(f"invalid Chinese dialogue decision for {qid!r}")
        result[qid] = row["source_label"]
    return result


def _column_index(reference: str) -> int:
    match = _CELL_REF_RE.fullmatch(reference)
    if match is None:
        raise ChineseSourceError(f"invalid XLSX cell reference: {reference!r}")
    result = 0
    for character in match.group(1):
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def _xml_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(part.text or "" for part in node.iter(f"{{{_MAIN_NS}}}t"))


def read_xlsx_rows(path: str | Path) -> dict[str, list[dict[int, str]]]:
    """Read cell values from an XLSX using only the Python standard library.

    The source workbooks contain no formulas needed by this importer.  A tiny
    reader avoids adding openpyxl (and its large frozen-app dependency tree)
    solely to consume string cells.
    """
    path = Path(path)
    try:
        source = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ChineseSourceError(f"invalid Chinese source workbook: {path}") from exc
    with source:
        try:
            workbook = ET.fromstring(source.read("xl/workbook.xml"))
            relationships = ET.fromstring(source.read("xl/_rels/workbook.xml.rels"))
        except (KeyError, ET.ParseError) as exc:
            raise ChineseSourceError(f"incomplete Chinese source workbook: {path}") from exc

        shared_strings: list[str] = []
        try:
            shared_root = ET.fromstring(source.read("xl/sharedStrings.xml"))
        except KeyError:
            shared_root = None
        except ET.ParseError as exc:
            raise ChineseSourceError(f"invalid shared strings in {path}") from exc
        if shared_root is not None:
            shared_strings = [_xml_text(item) for item in shared_root.findall(f"{{{_MAIN_NS}}}si")]

        targets = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relationships.findall(f"{{{_PKG_REL_NS}}}Relationship")
            if "Id" in relation.attrib and "Target" in relation.attrib
        }
        result: dict[str, list[dict[int, str]]] = {}
        sheets = workbook.find(f"{{{_MAIN_NS}}}sheets")
        if sheets is None:
            raise ChineseSourceError(f"workbook has no sheets: {path}")
        for sheet in sheets.findall(f"{{{_MAIN_NS}}}sheet"):
            name = sheet.attrib.get("name", "")
            relation_id = sheet.attrib.get(f"{{{_DOC_REL_NS}}}id", "")
            target = targets.get(relation_id)
            if not name or not target:
                continue
            relative = PurePosixPath(target.lstrip("/"))
            member = relative.as_posix() if relative.parts[:1] == ("xl",) else (PurePosixPath("xl") / relative).as_posix()
            try:
                worksheet = ET.fromstring(source.read(member))
            except (KeyError, ET.ParseError) as exc:
                raise ChineseSourceError(f"invalid worksheet {name!r} in {path}") from exc
            rows: list[dict[int, str]] = []
            sheet_data = worksheet.find(f"{{{_MAIN_NS}}}sheetData")
            if sheet_data is None:
                result[name] = rows
                continue
            for row_node in sheet_data.findall(f"{{{_MAIN_NS}}}row"):
                row: dict[int, str] = {}
                for cell in row_node.findall(f"{{{_MAIN_NS}}}c"):
                    reference = cell.attrib.get("r", "")
                    if not reference:
                        continue
                    cell_type = cell.attrib.get("t", "")
                    if cell_type == "inlineStr":
                        value = _xml_text(cell.find(f"{{{_MAIN_NS}}}is"))
                    else:
                        value_node = cell.find(f"{{{_MAIN_NS}}}v")
                        value = value_node.text if value_node is not None and value_node.text is not None else ""
                        if cell_type == "s" and value:
                            try:
                                value = shared_strings[int(value)]
                            except (IndexError, ValueError) as exc:
                                raise ChineseSourceError(
                                    f"invalid shared-string index in {path}:{name}:{reference}"
                                ) from exc
                    row[_column_index(reference)] = value
                rows.append(row)
            result[name] = rows
        return result


def _value(row: Mapping[int, str], column: int) -> str:
    return str(row.get(column, "") or "").replace("\r", "").replace("\n", "")


def _translation_key(value: str) -> str:
    value = value.replace("<BSP>", " ").replace("<WBR>", " ")
    value = value.strip().strip('"').rstrip("@").casefold()
    return re.sub(r"\s+", " ", value)


def _append_terminator(value: str) -> str:
    return value if value.endswith("@") else value + "@"


def _render_text_block(lines: list[str], controls: list[str], next_cr: bool, eom: str) -> str:
    rendered: list[str] = []
    line_count = 0
    paragraph_count = 0
    for raw_line in lines:
        line = raw_line.replace("|", "")
        for index, control in enumerate(controls):
            line = line.replace(f"【{index}】", f"@{{{control}}}{{text_start}}")
        if line == "":
            if line_count or paragraph_count:
                line_count = 0
                paragraph_count += 1
            continue
        if line_count == 0 and paragraph_count == 0:
            rendered.append("{text_start}" + line)
        elif line_count == 0:
            rendered.append("<PARA>" + line)
        elif line_count == 1:
            rendered.append(("<NEXT>" if next_cr else "<LINE>") + line)
        else:
            rendered.append(("<NEXT>" if next_cr else "<CONT>") + line)
        line_count += 1
    ending = {
        "EOMeom": "<DONE>",
        "EOMwaiteom": "<PROMPT>",
        "EOM": "@",
        "EOM^2": "@",
    }.get(eom)
    if ending is None:
        raise ChineseSourceError(f"unsupported Chinese text terminator: {eom!r}")
    return "".join(rendered) + ending


def _dialogue_sources(
    workbook: Mapping[str, list[dict[int, str]]],
) -> tuple[dict[str, tuple[str, str]], dict[str, set[str]]]:
    from .gs_text import normalise

    labels: dict[str, tuple[str, str]] = {}
    for row in workbook.get("标", [])[1:]:
        version = _value(row, 8).strip()
        if version not in {"", "GS"}:
            continue
        original_label = _value(row, 3)
        destination_label = _value(row, 2)
        eom = _value(row, 5)
        if original_label and destination_label and eom:
            labels[original_label] = (destination_label, eom)

    translations: dict[str, tuple[str, str]] = {}
    by_english: dict[str, set[str]] = defaultdict(set)
    for sheet_name in (f"文{index}" for index in range(1, 11)):
        active = ""
        active_version = ""
        english_lines: list[str] = []
        chinese_lines: list[str] = []
        controls: list[str] = []

        def finish() -> None:
            nonlocal english_lines, chinese_lines, controls
            if not active or active not in labels or active_version not in {"", "GS"}:
                return
            while chinese_lines and chinese_lines[-1] == "":
                chinese_lines.pop()
            next_cr = bool(controls and controls[0] == "LINE_CR")
            if next_cr:
                controls.pop(0)
            destination_label, eom = labels[active]
            rendered = _render_text_block(chinese_lines, controls, next_cr, eom)
            source_english = " ".join(line for line in english_lines if line)
            # The workbook represents command insertions as 【0】, 【1】...
            # while PokeCorpus spells the same slots as {text_ram ...} or
            # {text_decimal ...}; both are non-prose for normalized matching.
            english_key = normalise(re.sub(r"【[0-9]+】", "", source_english))
            # The source project's importer keeps the first block when two
            # original-script labels deliberately converge on one pokegold
            # destination label (and reports the duplicate to its console).
            # Mirror that deterministic behavior instead of choosing a later
            # prose variant here.
            translations.setdefault(destination_label, (rendered, english_key))
            if destination_label.startswith("_"):
                translations.setdefault(destination_label.lstrip("_"), (rendered, english_key))
            if english_key:
                by_english[english_key].add(rendered)

        for row in workbook.get(sheet_name, []):
            english = _value(row, 0)
            control = _value(row, 9)
            version = _value(row, 10).strip()
            if "英文" in english or "结束" in english:
                finish()
                active = control if "英文" in english else ""
                active_version = version
                english_lines = []
                chinese_lines = []
                controls = []
                continue
            if not active:
                continue
            english_lines.append(english)
            chinese_lines.append(_value(row, 4))
            if control:
                controls.append(control)
        finish()
    return translations, by_english


def _indexed_sheet(workbook: Mapping[str, list[dict[int, str]]], sheet_name: str) -> dict[int, str]:
    result: dict[int, str] = {}
    for row in workbook.get(sheet_name, [])[1:]:
        identifier = _value(row, 0)
        match = re.search(r"([0-9]+)(?:\$)?$", identifier)
        translation = _value(row, 3)
        if match and translation:
            result[int(match.group(1))] = _append_terminator(translation)
    return result


def _exact_string_pairs(workbook: Mapping[str, list[dict[int, str]]]) -> dict[str, set[str]]:
    pairs: dict[str, set[str]] = defaultdict(set)
    for row in workbook.get("其", [])[1:]:
        english, chinese = _value(row, 1), _value(row, 3)
        if english and chinese:
            pairs[_translation_key(english)].add(_append_terminator(chinese))
    for rows in workbook.values():
        for row in rows:
            english, chinese = _value(row, 4), _value(row, 5)
            if not (english.startswith('"') and english.endswith('"') and
                    chinese.startswith('"') and chinese.endswith('"')):
                continue
            pairs[_translation_key(english)].add(chinese[1:-1])
    return pairs


def _dex_rows(workbook: Mapping[str, list[dict[int, str]]]) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    rows = workbook.get("Sheet1", [])
    for row in rows:
        species = _value(row, 3)
        gold = _value(row, 5).replace(";", "<NEXT>").replace("/", "@")
        silver = _value(row, 7).replace(";", "<NEXT>").replace("/", "@")
        if species and gold and silver:
            result.append((_append_terminator(species), _append_terminator(gold), _append_terminator(silver)))
    return result


def _description_rows(path: str | Path) -> list[str]:
    result: list[str] = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        fields = line.rstrip("\r").split(",", 2)
        if len(fields) != 3 or not fields[2]:
            raise ChineseSourceError(f"invalid legacy description row in {path}: {line!r}")
        translation = fields[2].replace("{P59}", "<NEXT>").replace("{59}", "<NEXT>").replace("{50}", "@")
        result.append(_append_terminator(translation))
    return result


def build_zh_hans_parallel(
    corpus_dir: str | Path,
    *,
    dialogue_workbook: str | Path,
    data_workbook: str | Path,
    dex_workbook: str | Path,
    item_descriptions: str | Path,
    move_descriptions: str | Path,
    dialogue_decisions: str | Path | None = None,
    destination: str | Path | None = None,
) -> ChineseCorpusStats:
    """Materialize ``zh-Hans_msg.txt`` beside PokeCorpus qid/en files."""
    corpus_dir = Path(corpus_dir)
    qid_path = corpus_dir / "qid_msg.txt"
    english_path = corpus_dir / "en_msg.txt"
    qids = qid_path.read_text(encoding="utf-8").splitlines()
    english = english_path.read_text(encoding="utf-8").splitlines()
    if len(qids) != len(english):
        raise ChineseSourceError("GoldSilver qid/en files are not parallel")
    targets = [""] * len(qids)
    provenance = [""] * len(qids)

    def assign(index: int, translation: str, source: str) -> None:
        if not translation:
            return
        if "\n" in translation or "\r" in translation:
            raise ChineseSourceError(f"multiline target cannot be written at {qids[index]!r}")
        if targets[index] and targets[index] != translation:
            raise ChineseSourceError(
                f"conflicting Chinese sources for {qids[index]!r}: {provenance[index]} vs {source}"
            )
        targets[index] = translation
        provenance[index] = source

    from .gs_text import normalise

    structured_prefixes = (
        "gs.landmarks.", "gs.dex_entries", "gs.names.",
        "gs.class_names.", "gs.descriptions.",
    )
    dialogue_book = read_xlsx_rows(dialogue_workbook)
    dialogue, dialogue_by_english = _dialogue_sources(dialogue_book)
    for index, qid in enumerate(qids):
        label = _VERSION_SUFFIX_RE.sub("", qid.rsplit(".", 1)[-1])
        candidate = dialogue.get(label)
        if candidate is not None and candidate[1] == normalise(english[index]):
            assign(index, candidate[0], "current-dialogue")
    for index, source_text in enumerate(english):
        values = dialogue_by_english.get(normalise(source_text), set())
        if len(values) == 1 and not targets[index] and not qids[index].startswith(structured_prefixes):
            assign(index, next(iter(values)), "current-dialogue-english")

    reviewed_dialogue = load_dialogue_decisions(dialogue_decisions)
    qid_indices = {qid: index for index, qid in enumerate(qids)}
    for qid, source_label in reviewed_dialogue.items():
        if qid not in qid_indices:
            raise ChineseSourceError(f"unknown reviewed Chinese dialogue qid: {qid}")
        candidate = dialogue.get(source_label)
        if candidate is None:
            raise ChineseSourceError(
                f"reviewed Chinese dialogue source label is missing: {qid} -> {source_label}"
            )
        index = qid_indices[qid]
        if candidate[1] == normalise(english[index]):
            raise ChineseSourceError(
                f"reviewed Chinese dialogue decision is no longer needed: {qid}"
            )
        assign(index, candidate[0], "reviewed-current-dialogue")

    indexed_sources = (
        ("gs.names.PokemonNames.", _indexed_sheet(dialogue_book, "宝"), "current-pokemon-names"),
        ("gs.names.MoveNames.", _indexed_sheet(dialogue_book, "招"), "current-move-names"),
        ("gs.names.ItemNames.", _indexed_sheet(dialogue_book, "道GS"), "current-item-names"),
        ("gs.class_names.TrainerClassNames.", _indexed_sheet(dialogue_book, "类"), "current-trainer-classes"),
    )
    for prefix, values, source in indexed_sources:
        for index, qid in enumerate(qids):
            suffix = qid[len(prefix):] if qid.startswith(prefix) else ""
            if suffix.isdigit() and int(suffix) in values:
                assign(index, values[int(suffix)], source)

    exact_pairs = _exact_string_pairs(dialogue_book)
    current_data = _exact_string_pairs(read_xlsx_rows(data_workbook))
    for key, values in current_data.items():
        exact_pairs[key].update(values)
    for index, source_text in enumerate(english):
        values = exact_pairs.get(_translation_key(source_text), set())
        if len(values) == 1 and not targets[index] and not qids[index].startswith(structured_prefixes):
            assign(index, next(iter(values)), "current-exact-string")

    landmark_values: dict[str, set[str]] = defaultdict(set)
    for row in dialogue_book.get("城GS", [])[1:]:
        source_text, target_text = _value(row, 1), _value(row, 3)
        if source_text and target_text:
            landmark_values[_translation_key(source_text)].add(_append_terminator(target_text))
    for index, qid in enumerate(qids):
        if not qid.startswith("gs.landmarks."):
            continue
        values = landmark_values.get(_translation_key(english[index]), set())
        if len(values) == 1:
            assign(index, next(iter(values)), "current-landmarks")

    dex = _dex_rows(read_xlsx_rows(dex_workbook))
    dex_qids = {
        "species": [
            i for i, qid in enumerate(qids)
            if qid.startswith("gs.dex_entries.") and qid.rsplit(".", 1)[-1] in {"Species", "Species^G"}
        ],
        "gold": [i for i, qid in enumerate(qids) if qid.startswith("gs.dex_entries_gold.")],
        "silver": [i for i, qid in enumerate(qids) if qid.startswith("gs.dex_entries_silver.")],
    }
    if any(len(indices) != len(dex) for indices in dex_qids.values()):
        counts = {name: len(indices) for name, indices in dex_qids.items()}
        raise ChineseSourceError(f"Chinese Pokédex rows do not match PokeCorpus: source={len(dex)}, qids={counts}")
    for dex_index, (species, gold, silver) in enumerate(dex):
        assign(dex_qids["species"][dex_index], species, "current-pokedex-species")
        assign(dex_qids["gold"][dex_index], gold, "current-pokedex-gold")
        assign(dex_qids["silver"][dex_index], silver, "current-pokedex-silver")

    description_indices = [i for i, qid in enumerate(qids) if qid.startswith("gs.descriptions.")]
    move_indices = [i for i in description_indices if qids[i].endswith("Description") and english[i] != "?@"]
    item_indices = [i for i in description_indices if qids[i].endswith("Desc") and english[i] != "?@"]
    move_rows = _description_rows(move_descriptions)
    item_rows = _description_rows(item_descriptions)
    if len(move_indices) != len(move_rows) or len(item_indices) != len(item_rows):
        raise ChineseSourceError(
            "legacy description rows do not match PokeCorpus: "
            f"moves={len(move_rows)}/{len(move_indices)}, items={len(item_rows)}/{len(item_indices)}"
        )
    for index, translation in zip(move_indices, move_rows):
        assign(index, translation, "legacy-move-descriptions")
    for index, translation in zip(item_indices, item_rows):
        assign(index, translation, "legacy-item-descriptions")

    destination = Path(destination) if destination is not None else corpus_dir / f"{ZH_HANS}_msg.txt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}-", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as output:
            output.write("\n".join(targets) + "\n")
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    counts: dict[str, int] = defaultdict(int)
    for source in provenance:
        if source:
            counts[source] += 1
    return ChineseCorpusStats(sum(bool(value) for value in targets), len(targets), dict(sorted(counts.items())))


def prepare_zh_hans_corpus(workspace: str | Path, config: Mapping, corpus_root: str | Path) -> ChineseCorpusStats:
    """Fetch pinned human sources and add the private Chinese parallel file."""
    from .dependencies import fetch_files

    workspace = Path(workspace)
    corpus_dir = Path(corpus_root) / "corpus" / "GoldSilver"
    sources = config.get("chinese_sources", {})

    def fetch(name: str) -> Path:
        source = sources.get(name, {})
        if not source:
            raise ChineseSourceError(f"missing pinned Chinese source config: {name}")
        return fetch_files(
            str(source.get("archive_base_url", "")),
            dict(source.get("archive_files", {})),
            workspace / "dependencies" / f"chinese-source-{name}",
            revision=str(source.get("revision", "")),
        )

    shared = fetch("shared_text")
    current = fetch("current_gold_silver")
    legacy = fetch("legacy_descriptions")
    from .project import resource_root

    return build_zh_hans_parallel(
        corpus_dir,
        dialogue_workbook=shared / "text.xlsx",
        data_workbook=current / "src" / "xlsx" / "data.xlsx",
        dex_workbook=current / "src" / "xlsx" / "dex.xlsx",
        item_descriptions=legacy / "02_Text" / "ItemDescription.TXT",
        move_descriptions=legacy / "02_Text" / "MoveDescription.50.TXT",
        dialogue_decisions=resource_root() / "config" / "gs" / "zh_hans_dialogue_decisions.json",
    )
