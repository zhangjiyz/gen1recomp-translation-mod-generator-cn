# Simplified Chinese translation sources

This mod imports human fan translations from the following pinned revisions; it does not use machine translation:

- [pokegoldCHS](https://github.com/TomJinW/pokegoldCHS), commit `c6f310d7c08feb9582798138893173c290b91f1d`
- [PokeGSC_SharedXLSXCN](https://github.com/TomJinW/PokeGSC_SharedXLSXCN), commit `df11834308d89ce6473d4b76c73c3ad11fa2bcd8`
- [PKMN_GSCHS](https://github.com/TomJinW/PKMN_GSCHS), commit `c3947b83c6c66a015103e1bc08bbca7f2a862d3b`
- [pokecrystal_cn](https://github.com/SnDream/pokecrystal_cn), commit `dab54f14d49c578eec05e4c67ee8b7d5fb916e11`
- [pokecrystal_cn_build](https://github.com/SnDream/pokecrystal_cn_build), commit `868552150200b3086d64d1ec49959afd04b92da3`; `text.xlsx` SHA-256 `03fe83335bc8041cfe503cea3b9565110e7be30df5a32239c57f15084b36c0bd`

No explicit license file was found in these source repositories when this importer was prepared. The commit pins and hashes make the imported text reproducible, but do not grant redistribution rights. Obtain permission from the respective translation authors before publicly redistributing a package that contains their text.

Unmatched or ambiguous text deliberately remains in English for later human review.

`tools/import_crystal_zh_catalog.py` converts the workbook into source-labelled
English/Chinese rows. During a private build, the user's original Crystal ROM
is extracted and joined by normalized English text; only unique matches or
ambiguities with byte-identical Chinese results are emitted under current ROM
pointers. The workbook and ROM are never packaged.
