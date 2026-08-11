# SQCAD external database

The GitHub working tree at `C:\Users\Lenovo\Desktop\Paper\SQCAD` contains only core research code, tests, lightweight protocols and documentation. Large datasets, model weights, generated results, raw downloads and historical archives belong in:

`D:\Engineering\SQCAD\database`

Expected database layout:

- `datasets/`: downloaded or locally prepared benchmark data;
- `models/`: local model weights and tokenizer caches;
- `results/`: generated experiment outputs and reports;
- `manifests/`: frozen metadata, hashes, provenance and protocol manifests;
- `tmp/`: temporary downloads and conversion outputs;
- `archive/`: superseded drafts and non-core artifacts.

Set `SQCAD_DATABASE_ROOT` when running experiments on another machine. Do not commit the external database to GitHub.
