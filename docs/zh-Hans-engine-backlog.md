# Simplified Chinese Gold/Silver engine backlog

## Shared port menus

The shared title, Gen 1 options, start, Mod Manager entry, and shader-picker
menus are also carried by the Red/Blue/Yellow Chinese engine override. This
prevents common port-only rows from existing only in the Gold/Silver artifact.
The reviewed group includes `EXIT GAME`, battle/UI layout rows, audio and
display rows, per-category speed rows, Mod Manager count and return prompt,
input/date/time rows, shader actions, and the raw color/video option values.

This audit additionally scanned direct `Strings(...)` keys in
`OptionsMenu.lua`, `StartMenu.lua`, `ShaderFXScreen.lua`, and `TitleState.lua`;
the generated Red/Blue/Yellow package currently has no empty direct-menu key
in those surfaces.

The pinned human fan-translation sources and reviewed Chinese UI adaptations
now cover all 302 Gold/Silver-related Gen1Recomp engine strings. There is no
remaining engine backlog. The final 29 keys were translated contextually from
their pinned Gen1Recomp callsites and require an in-game layout review.

## Completed contextual translations: diagnostics and file operations (7)

- `%s is missing.\nRe-import the Gold ROM.`
- `Could not save.`
- `Failed to boot %s:\n%s`
- `Font load failed:\n%s`
- `Gold cache incomplete:\n%s`
- `Printed %s's\ndata!\fSaved as\n%s\vin the save\nfolder.`
- `Printer error!\n%s`

## Completed contextual translations: port-only settings and controls (20)

- `BATTLE BG`
- `COLOR`
- `CONTROLS`
- `GAME SPEED`
- `MAX FPS`
- `MUSIC FILTER`
- `MUSIC VOL`
- `NO SAVE FILE`
- `PERFORMANCE`
- `SCREEN POS`
- `SFX VOL`
- `SHADER FX`
- `SHADER FX 2`
- `TILT`
- `TOUCH LAYOUT`
- `TOUCH PAD`
- `VIBRATION`
- `VIDEO MODE`
- `VOID FILL`
- `ZOOM`

## Completed contextual translations: source-shape gaps (2)

- `Fly to %s?`
- `TEXT SPEED`

The Chinese ROM source deliberately leaves `TEXT SPEED` blank. `Fly to %s?`
is a headless-only fallback invented by the port rather than a cartridge line.
Their reviewed Chinese values and callsite provenance are recorded in
`overrides/zh-Hans/gs/engine.json`.
