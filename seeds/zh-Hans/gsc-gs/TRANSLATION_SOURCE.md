# Simplified Chinese translation sources

This mod imports human fan translations from the following pinned revisions; it does not use machine translation:

- [pokegoldCHS](https://github.com/TomJinW/pokegoldCHS), commit `c6f310d7c08feb9582798138893173c290b91f1d`
- [PokeGSC_SharedXLSXCN](https://github.com/TomJinW/PokeGSC_SharedXLSXCN), commit `df11834308d89ce6473d4b76c73c3ad11fa2bcd8`
- [PKMN_GSCHS](https://github.com/TomJinW/PKMN_GSCHS), commit `c3947b83c6c66a015103e1bc08bbca7f2a862d3b`
- [pokecrystal_cn](https://github.com/SnDream/pokecrystal_cn), commit `dab54f14d49c578eec05e4c67ee8b7d5fb916e11`
- [pokecrystal_cn_build](https://github.com/SnDream/pokecrystal_cn_build), commit `868552150200b3086d64d1ec49959afd04b92da3`; `text.xlsx` SHA-256 `03fe83335bc8041cfe503cea3b9565110e7be30df5a32239c57f15084b36c0bd`
- [PokéCorpus](https://github.com/abcboy101/poke-corpus), corpus commit `aa2885972ce76d29bcc18a5179f6ee411a60c8f8`; official Ultra Sun/Ultra Moon Simplified Chinese move and item descriptions are imported by aligned QID.
- [pret/pokegold](https://github.com/pret/pokegold), commit `656583c939d30f920a316177311a502dd222b57c`; used only to bind the 251 cartridge move IDs to the official description rows.

No explicit license file was found in the fan-translation source repositories
when this importer was prepared. PokéCorpus's repository license does not
change the rights in the underlying official game text. The commit pins and
hashes make the import reproducible, but do not by themselves grant
redistribution rights. Obtain the appropriate permissions before publicly
redistributing a package that contains this text.

Unmatched or ambiguous text deliberately remains in English for later human review.

`tools/import_zh_hans_gsc_descriptions.py` imports the official description
rows and splits the existing reviewed compact Pokédex prose between the two
runtime pages. It does not translate Pokédex text or send source text to a
translation service.

`tools/import_crystal_zh_catalog.py` converts the workbook into source-labelled
English/Chinese rows. During a private build, the user's original Crystal ROM
is extracted and joined by normalized English text; only unique matches or
ambiguities with byte-identical Chinese results are emitted under current ROM
pointers. The workbook and ROM are never packaged.
