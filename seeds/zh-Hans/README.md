# Simplified Chinese seed catalogs

These catalogs preserve reviewed translations from the user's existing RBY
and Gold/Silver packages. They are inputs to a fresh build, not packages to
ship unchanged: manifests, executable entry points, fonts and validation
claims are intentionally excluded by `tools/import_zh_seed.py`.

`gsc-gs` contains only the Gold/Silver layer. Crystal dialogue must be added
as a separate, provenance-pinned layer before a GSC release can pass.

The imported source notices report that the fan-translation repositories did
not contain explicit license grants. Keep public redistribution blocked until
permission or a compatible license is documented.
