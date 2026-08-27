"""Build Red/Blue and Yellow Simplified Chinese parallel corpora.

The pinned TomJinW projects are human translations of the same US ROMs used
by this generator.  Their prose lives in XLSX import tables rather than in a
PokeCorpus target file.  This module reads those tables, aligns whole text
blocks by their original English text or retained pret label, and only then
materializes ``zh-Hans_msg.txt`` beside the pinned PokeCorpus files.

No prose is generated here.  Rows that cannot be tied to an exact source
block, label, or unambiguous data-table replacement remain empty.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Mapping

from .zh_hans import ChineseSourceError, read_xlsx_rows


ZH_HANS = "zh-Hans"
_DIALOGUE_BOOKS = (
    "indoor.xlsx",
    "routes.xlsx",
    "core.xlsx",
    "buildingsB.xlsx",
    "buildingsA.xlsx",
    "outdoor.xlsx",
    "ratings.xlsx",
)
_TOKEN_RE = re.compile(r"(<[^>]+>|\{[^}]+\})")
_VERSION_SUFFIX_RE = re.compile(r"\^(?:RG|R|G|B)(?=\.|$)")
_DYNAMIC_RE = re.compile(r"\{text_(?:ram|decimal|bcd)\s+[^}]+\}")
_DIALOGUE_DECISIONS_SCHEMA = "gen1recomp-translation-mods/zh-hans-rby-dialogue-decisions"


@dataclass(frozen=True)
class RbyChineseCorpusStats:
    translated: int
    total: int
    by_source: Mapping[str, int]


def _label(value: object) -> str:
    return str(value or "").strip().lstrip("_").rstrip(":")


def _cell(value: object) -> str:
    """Decode a source-table assembly string and remove fixed-width padding."""
    text = str(value or "").strip()
    if len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        try:
            text = str(ast.literal_eval(text))
        except (SyntaxError, ValueError):
            text = text[1:-1]
    # The ROM patch pads ten-byte name fields with repeated terminators.  The
    # recomp catalog stores one logical Unicode string, so it needs one.
    text = re.sub(r"@+$", "@", text)
    return _decode_chinese_source(text)


def _decode_chinese_source(value: str) -> str:
    """Expand glyph aliases used only by the patched Game Boy charmap."""
    return value.replace("#", "宝可梦").replace("ñ", "HP").replace("%", "PP")


def _append_command(parts: list[str], command: object, content: object) -> None:
    command = str(command or "").strip()
    content = str(content or "").replace("\r", "").replace("\n", "")
    if command in {"text", "text_start"}:
        parts.extend(("{text_start}", content))
    elif command in {"line", "cont", "para", "next", "page"}:
        parts.extend((f"<{command.upper()}>", content))
    elif command in {"text_ram", "text_decimal", "text_bcd"}:
        parts.append("{" + command + ((" " + content) if content else "") + "}")
    elif command == "done":
        parts.append("<DONE>")
    elif command == "prompt":
        parts.append("<PROMPT>")
    elif command == "text_end":
        parts.append("@")
    elif command == "dex":
        parts.append("<DEXEND>@")


def _append_source_command(parts: list[str], command: object, content: object) -> None:
    before = len(parts)
    _append_command(parts, command, content)
    for index in range(before, len(parts)):
        # Control tokens contain none of these aliases, so applying the
        # expansion to the newly appended pieces is safe and keeps command
        # rendering identical between source and target columns.
        parts[index] = _decode_chinese_source(parts[index])


def _text_blocks(source_root: Path) -> list[tuple[str, str, str, str, str]]:
    """Return label, original English, Chinese, source kind and sheet context."""
    result: list[tuple[str, str, str, str, str]] = []
    for workbook_name in (*_DIALOGUE_BOOKS, "dex.xlsx"):
        workbook_path = source_root / workbook_name
        if not workbook_path.is_file():
            continue
        for sheet_name, rows in read_xlsx_rows(workbook_path).items():
            active = ""
            english: list[str] = []
            chinese: list[str] = []

            def finish() -> None:
                if active and english and chinese:
                    kind = "human-pokedex" if workbook_name == "dex.xlsx" else "human-dialogue"
                    result.append((active, "".join(english), "".join(chinese), kind, sheet_name))

            for row in rows:
                original_label = str(row.get(0, "") or "").strip()
                translated_label = str(row.get(4, "") or "").strip()
                if original_label.endswith(":") or translated_label.endswith(":"):
                    finish()
                    active = _label(translated_label or original_label)
                    english = []
                    chinese = []
                    continue
                if not active:
                    continue
                _append_command(english, row.get(1), row.get(2))
                _append_source_command(chinese, row.get(5), row.get(6))
            finish()
    return result


def _data_pairs(source_root: Path) -> dict[str, set[str]]:
    pairs: dict[str, set[str]] = defaultdict(set)
    workbook = read_xlsx_rows(source_root / "data.xlsx")
    for rows in workbook.values():
        for row in rows:
            english = _cell(row.get(1))
            chinese = _cell(row.get(2))
            if english and english != "@" and chinese:
                pairs[english].add(chinese)
    return pairs


def _species_pairs(source_root: Path) -> dict[str, set[str]]:
    pairs: dict[str, set[str]] = defaultdict(set)
    workbook = read_xlsx_rows(source_root / "dexEntry.xlsx")
    for rows in workbook.values():
        for row in rows[1:]:
            source_label = _label(row.get(16) or row.get(9))
            species = _cell(row.get(13))
            if source_label and species:
                pairs[f"{source_label}.Species"].add(species.rstrip("@") + "@")
    return pairs


def _translated_segments(value: str, pairs: Mapping[str, set[str]]) -> str | None:
    """Translate a composite menu only when every prose segment is exact."""
    output: list[str] = []
    changed = False
    for part in _TOKEN_RE.split(value):
        if not part:
            continue
        if _TOKEN_RE.fullmatch(part):
            output.append(part)
            continue
        candidates = pairs.get(part, set())
        if len(candidates) == 1:
            output.append(next(iter(candidates)))
            changed = True
            continue
        if part.endswith("@"):
            candidates = pairs.get(part[:-1], set())
            if len(candidates) == 1:
                translated = next(iter(candidates))
                output.append(translated if translated.endswith("@") else translated + "@")
                changed = True
                continue
        # Formatting-only fragments do not need a translation source.
        if not part.strip() or all(character in " /:×0123456789?.!′″№─" for character in part):
            output.append(part)
            continue
        return None
    return "".join(output) if changed else None


def _qid_candidates(qid: str) -> tuple[str, ...]:
    unsuffixed = _VERSION_SUFFIX_RE.sub("", qid)
    suffix = unsuffixed.rsplit(".", 1)[-1].lstrip("_")
    candidates = [suffix]
    marker = ".dex_entries."
    if marker in unsuffixed:
        candidates.insert(0, unsuffixed.split(marker, 1)[1].lstrip("_"))
    return tuple(dict.fromkeys(candidates))


def _dynamic_family(token: str) -> str:
    match = re.match(r"\{(text_(?:ram|decimal|bcd))\b", token)
    return match.group(1) if match else ""


def _transplant_dynamic_tokens(source_text: str, target: str) -> str:
    """Retain the current corpus token arguments in an older human row.

    The fan projects and current PokeCorpus sometimes spell the same ROM
    buffer command differently (for example an old ``$c3`` flag versus the
    decoded decimal flags).  The prose is still reusable, but the generated
    target must preserve the current source contract exactly.
    """
    source_tokens = _DYNAMIC_RE.findall(source_text)
    target_tokens = _DYNAMIC_RE.findall(target)
    if len(source_tokens) != len(target_tokens):
        return target
    if [_dynamic_family(value) for value in source_tokens] != [
        _dynamic_family(value) for value in target_tokens
    ]:
        return target
    tokens = iter(source_tokens)
    return _DYNAMIC_RE.sub(lambda _match: next(tokens), target)


def _event_shape(value: str) -> str:
    """Normalize renamed ROM buffers while retaining visible event text."""
    shaped = _DYNAMIC_RE.sub(
        lambda match: "{" + _dynamic_family(match.group(0)) + "}",
        value,
    )
    # Current PokeCorpus removes a handful of padding spaces immediately
    # before line/page controls. They are not visible event prose.
    return re.sub(r"[ \t]+(?=<)", "", shaped)


def load_rby_dialogue_decisions(path: str | Path | None) -> dict[str, str]:
    """Load reviewed qid-to-human-source-label aliases."""
    if path is None or not Path(path).is_file():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != _DIALOGUE_DECISIONS_SCHEMA:
        raise ChineseSourceError("unsupported RBY Chinese dialogue decisions schema")
    if data.get("version") != 1 or not isinstance(data.get("entries"), dict):
        raise ChineseSourceError("invalid RBY Chinese dialogue decisions document")
    result: dict[str, str] = {}
    for qid, row in data["entries"].items():
        if not isinstance(qid, str) or not qid.startswith(("rb.", "y.")):
            raise ChineseSourceError(f"invalid RBY dialogue decision qid: {qid!r}")
        if not isinstance(row, dict) or not isinstance(row.get("source_label"), str):
            raise ChineseSourceError(f"invalid RBY dialogue decision: {qid!r}")
        if not str(row.get("reason", "")).strip():
            raise ChineseSourceError(f"RBY dialogue decision has no reason: {qid!r}")
        result[qid] = _label(row["source_label"])
    return result


def build_zh_hans_rby_parallel(
    corpus_dir: str | Path,
    *,
    source_root: str | Path,
    destination: str | Path | None = None,
    dialogue_decisions: str | Path | None = None,
) -> RbyChineseCorpusStats:
    """Materialize one RBY collection's human Simplified Chinese target."""
    corpus_dir = Path(corpus_dir)
    source_root = Path(source_root)
    qids = (corpus_dir / "qid_msg.txt").read_text(encoding="utf-8").splitlines()
    english = (corpus_dir / "en_msg.txt").read_text(encoding="utf-8").splitlines()
    if len(qids) != len(english):
        raise ChineseSourceError(f"{corpus_dir.name} qid/en files are not parallel")

    by_label: dict[str, set[str]] = defaultdict(set)
    by_english: dict[str, set[str]] = defaultdict(set)
    by_context_english: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_context_shape: dict[tuple[str, str], set[str]] = defaultdict(set)
    label_sources: dict[tuple[str, str], str] = {}
    for label, source_text, translation, source_kind, context in _text_blocks(source_root):
        if source_text and translation:
            by_english[source_text].add(translation)
            by_context_english[(context, source_text)].add(translation)
            by_context_shape[(context, _event_shape(source_text))].add(translation)
        if label and translation:
            by_label[label].add(translation)
            label_sources[(label, translation)] = source_kind
    for label, values in _species_pairs(source_root).items():
        by_label[label].update(values)
        for value in values:
            label_sources[(label, value)] = "human-pokedex-species"
    data_pairs = _data_pairs(source_root)
    decisions = load_rby_dialogue_decisions(dialogue_decisions)

    targets = [""] * len(qids)
    provenance = [""] * len(qids)
    for index, (qid, source_text) in enumerate(zip(qids, english)):
        exact = by_english.get(source_text, set())
        if len(exact) == 1:
            targets[index] = _transplant_dynamic_tokens(source_text, next(iter(exact)))
            provenance[index] = "human-block-exact-english"
            continue
        for candidate in _qid_candidates(qid):
            values = by_label.get(candidate, set())
            if len(values) == 1:
                targets[index] = _transplant_dynamic_tokens(source_text, next(iter(values)))
                provenance[index] = label_sources.get(
                    (candidate, targets[index]), "human-block-exact-label"
                )
                break
        if targets[index]:
            continue
        context = qid.split(".", 2)[1] if qid.count(".") >= 2 else ""
        contextual = by_context_english.get((context, source_text), set())
        if len(contextual) != 1:
            contextual = by_context_shape.get((context, _event_shape(source_text)), set())
        if len(contextual) == 1:
            targets[index] = _transplant_dynamic_tokens(source_text, next(iter(contextual)))
            provenance[index] = "human-block-context-and-event"
            continue
        reviewed_label = decisions.get(qid)
        reviewed = by_label.get(reviewed_label, set()) if reviewed_label else set()
        if len(reviewed) == 1:
            targets[index] = _transplant_dynamic_tokens(source_text, next(iter(reviewed)))
            provenance[index] = "reviewed-human-label-alias"
            continue
        normalized_source = re.sub(r"@+$", "@", source_text)
        values = data_pairs.get(normalized_source, set())
        if len(values) == 1:
            targets[index] = next(iter(values))
            provenance[index] = "human-data-exact"
            continue
        segmented = _translated_segments(source_text, data_pairs)
        if segmented is not None:
            targets[index] = segmented
            provenance[index] = "human-data-segments"

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
    return RbyChineseCorpusStats(
        translated=sum(bool(value) for value in targets),
        total=len(targets),
        by_source=dict(sorted(counts.items())),
    )


def prepare_zh_hans_rby_corpus(
    workspace: str | Path,
    config: Mapping,
    corpus_root: str | Path,
) -> dict[str, RbyChineseCorpusStats]:
    """Fetch pinned R/B and Yellow workbooks and build both target files."""
    from .dependencies import fetch_files

    workspace = Path(workspace)
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
        ) / "src" / "xlsx"

    corpus_root = Path(corpus_root) / "corpus"
    red_blue = fetch("current_red_blue")
    yellow = fetch("current_yellow")
    from .project import resource_root
    decisions = resource_root() / "config" / "rby" / "zh_hans_yellow_dialogue_decisions.json"
    return {
        "RedBlue": build_zh_hans_rby_parallel(
            corpus_root / "RedBlue", source_root=red_blue, dialogue_decisions=decisions
        ),
        "Yellow": build_zh_hans_rby_parallel(
            corpus_root / "Yellow",
            source_root=yellow,
            dialogue_decisions=decisions,
        ),
    }
