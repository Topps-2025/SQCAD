# SQCAD external database

The GitHub working tree at `C:\Users\Lenovo\Desktop\Paper\SQCAD` contains only core research code, tests, lightweight protocols and documentation. Large datasets, model weights, generated results, raw downloads and historical archives belong in:

`D:\Engineering\SQCAD\database`

Expected database layout:

- `datasets/`: downloaded or locally prepared benchmark data;
- `models/`: local model weights and tokenizer caches;
- `results/`: generated experiment outputs and reports;
- `manifests/`: frozen metadata, hashes, provenance and protocol manifests;
- `tmp/`: temporary downloads and conversion outputs;
- `archive/`: superseded data snapshots and non-core artifacts. Chinese research drafts are versioned in `docs/docs_zn/`, grouped by research philosophy, prior work and pain points, core questions and framework design, data and experiments, writing, progress, and miscellaneous drafts.
- `upstream/benchmarks/`: commit-frozen official benchmark repositories;
- `upstream/baselines/`: commit-frozen paper baseline repositories, including rejected identity collisions;
- `papers/`: official paper PDFs and source metadata when redistribution permits;
- `envs/`: isolated reproduction environments and dependency locks;
- `logs/`: clone, download, install and execution logs.

Set `SQCAD_DATABASE_ROOT` when running experiments on another machine. Do not commit the external database to GitHub.

Generate and validate the machine-readable reproduction inventory with:

```powershell
python .\src\sqcad\reproduction_registry.py --strict
```

The command writes `manifests/reproduction_registry_v2.json` under the external database. A repository is not considered frozen merely because its directory exists: origin, commit, clean worktree and paper identity must all pass.
