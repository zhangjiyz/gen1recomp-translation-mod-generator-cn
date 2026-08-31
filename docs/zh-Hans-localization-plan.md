# Simplified Chinese localization adaptation plan

Status date: 2026-08-28. This document separates implemented code and imported
translation assets from ROM-dependent release acceptance.

## Target deliverables

1. `translation-zh-hans-<version>.zip`: one mod for Red, Blue and Yellow.
2. `translation-zh-hans-gen2-<version>.zip`: one mod for Gold, Silver and
   Crystal, with a Crystal-only dialogue layer selected at runtime.
3. Built-in `zh_CN` application strings in Gen1Recomp for launcher, options,
   import, update, link and other engine UI that can appear outside ROM text.
4. Optional-mod overlays, starting with PotatoVoxel, merged into the same
   engine string catalog with reviewed conflict decisions.

## Current inventory

### Main engine

The current v0.2.32-aligned checkout has 2,276 `Strings` callsites, 60 direct
render-literal callsites and six `RomText` fallbacks. These reduce to 1,771
unique engine keys. The built-in `zh_CN` catalog contains 1,332 keys and the
reviewed RBY seed contains 1,319; their union covers all 1,771 current keys.
The direct-render scanner is part of the audit, so strings passed directly to
`Chrome.print*`, `Font.draw*`, `love.graphics.print/printf` and `TextBox.new`
are no longer invisible to coverage checks.

Current unique-key categories are: core 40, Gen 2 519, import 483, link 86,
mixed 127, modern 80, RBY 239, UI 168 and unknown 29.

### RBY seed

| Catalog | Entries |
| --- | ---: |
| Red/Blue dialogue | 2,592 |
| Yellow dialogue layer | 434 |
| Engine strings | 1,319 |
| Species names / kinds | 151 / 151 |
| Move names | 165 |
| Item names | 152 |
| Trainer names, common / Yellow | 47 / 2 |
| Type names / status labels / demo names | 15 / 5 / 2 |
| Raw catalog entries | 5,035 |

The normal seed build packages these reviewed entries directly. An optional
ROM-backed audit can recalculate the effective denominator from current
extractions and a Modkit worksheet, reporting stale keys separately.

### Gold/Silver seed

| Catalog | Entries |
| --- | ---: |
| Dialogue pointers | 3,045 |
| Engine strings | 466 |
| Species names / kinds / Pokédex text | 251 / 251 / 251 |
| Move names / item names | 251 / 250 |
| Trainer class names / landmarks | 66 / 95 |
| Oak speech / UI labels | 6 / 40 |
| Raw Gold/Silver catalog entries | 4,972 |

The normal seed build preserves all reviewed pointer and registry entries.
The optional ROM-backed audit filters them through a current private Gold
extraction; missing or changed keys then remain English and are listed in
`coverage.json`.

### Crystal seed

Pinned sources:

- `SnDream/pokecrystal_cn` commit
  `dab54f14d49c578eec05e4c67ee8b7d5fb916e11`;
- `SnDream/pokecrystal_cn_build` commit
  `868552150200b3086d64d1ec49959afd04b92da3`;
- `text.xlsx` SHA-256
  `03fe83335bc8041cfe503cea3b9565110e7be30df5a32239c57f15084b36c0bd`.

The workbook contains 5,169 mapped rows. Twelve are empty or cannot become a
visible translated row, leaving 5,157 imported Chinese rows. The no-ROM build
resolves labels against pret/pokecrystal's pinned public linker symbol table
(commit `cc6fc04f19c645f5c40f64f8d88b2ab42c7bdde8`, SHA-256
`697fe20b3c659273a3ab8aa85db2eb78dcf674a3dd17c98b52fc1dddd37783f2`).
It safely emits 5,130 Crystal pointers. Seventeen rows have no usable symbol
and ten placeholder-incompatible translations are rejected; those 27 lines
fall back to English. A headless gate proves the Crystal layer applies on a
Crystal run and does not leak into Gold.

Runtime controls are converted without flattening semantics:

| Workbook/disassembly form | Runtime form |
| --- | --- |
| line / next | `\n` |
| paragraph | `\f` |
| scroll / cont | `\v` |
| `text_ram ...` | `{STRBUF}` |
| `text_decimal ...` | `{NUM}` |
| player/rival/user/target/enemy slots | corresponding named token |

### PotatoVoxel overlay

The reviewed overlay has 66 central string entries. It covers all 12 unique
explicit `Strings(...)` keys used by the inspected mod version. Two collisions
are intentional and documented: `MEDIUM` means graphics quality `中`, not the
trainer class `神婆`; `WATER` is rendered as `水面效果`, not the generic element
name. The mod also declares 73 unique settings-help descriptions, but its
current code does not render those descriptions, so they are tracked as schema
content rather than claimed visible translations.

## Build and release gates

The following gates pass for the normal no-ROM seed archives:

1. Seed file SHA-256 and source-provenance validation.
2. Pinned Crystal symbol-file SHA-256 validation.
3. Dynamic placeholder identity/count audit.
4. Headless Gen 2 dialogue, named-registry and Crystal/Gold isolation gates.
5. Strict Modkit fixture validation and Gen 2 compatibility scan.
6. ZIP inspection: no ROM, generated ROM data, worksheets, unsafe paths or
   symlinks.
7. Reproducible archive comparison.

The optional stronger extraction audit additionally verifies ROM SHA-1s,
re-extracts current pointer/id inventories and runs MK103 against imported
data. Remaining acceptance work is:

8. One-process LÖVE smoke test to avoid the earlier repeated Dock-icon flash.
9. Manual in-game smoke matrix: new game, naming, battle, bag, Pokédex,
   options, save/load, link UI, Gold/Silver intro and Crystal-exclusive scenes.

## Execution phases

| Phase | Work | State |
| --- | --- | --- |
| A | Sync both forks to their upstream baselines with backup branches | Complete locally |
| B | Pin Gen1Recomp v0.2.32 and expand engine/direct-render auditing | Complete |
| C | Add `zh-Hans`, Fusion Chinese font and reviewed RBY/GS seed import | Complete |
| D | Refresh main `zh_CN` gaps and prove 1,771/1,771 engine-key coverage | Complete statically |
| E | Add PotatoVoxel overlay and conflict decisions | Complete statically |
| F | Import Crystal workbook and add pinned no-ROM symbol join | Complete |
| G | Build both no-ROM ZIPs and run strict/runtime gates | Complete locally |
| G2 | Optional re-extraction audit against verified user ROMs | Not required for normal repack |
| H | Manual play-through acceptance and author redistribution permission | Required before public release |

## Release policy

Local personal builds may proceed from the user's own ROM dumps. Public
distribution of archives containing the imported fan-translation prose stays
blocked until the relevant translation authors grant permission or provide a
compatible license. Commit pins and hashes provide provenance and
reproducibility; they do not grant redistribution rights.
