# SQCAD

## Scope-Qualified Competitive Access Decay for evidence-governed Agent Memory

SQCAD is a research prototype for governing the future access of Agent Memory under a fixed workspace budget. It separates three states that are often conflated:

1. **Evidence** — immutable source records and provenance;
2. **Qualification** — scoped evidence-backed permission to change persistent access policy;
3. **Access** — per-task allocation of limited retrieval and workspace mass.

The core design is:

> **Propose broadly. Qualify cautiously. Focus competitively.**

Associational signals may propose candidates and support bounded low-risk fallback. They do not, by themselves, grant persistent permission. A positive, negative or unresolved qualification is scoped to task, user, tool, model/version, risk and policy conditions. Competitive access projection then reallocates a fixed budget instead of treating accessibility decay as irreversible evidence deletion.

## Research boundary

This repository is an experimental research artifact, not a claim of state-of-the-art performance. Current controlled experiments support only bounded mechanism findings. LongMemEval retrieval and LoCoMo data assets are available outside the repository; public end-to-end Agent Memory comparisons and strong-baseline reproduction remain separate verification stages.

## Repository layout

```text
SQCAD/
├── README.md
├── DATA_STORAGE.md
├── pyproject.toml
├── src/sqcad/          # core store, runner and controlled benchmarks
├── tests/              # deterministic unit and protocol checks
├── tools/              # validation utilities
└── docs/
    ├── docs_en/        # English research and presentation documents
    └── docs_zn/        # Chinese research notes and evidence records
```

## Quick start

```powershell
cd C:\Users\Lenovo\Desktop\Paper\SQCAD
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Run a controlled smoke experiment:

```powershell
python -m sqcad.governance_baseline_simulator --seeds 5 --samples-per-environment 1000
```

The controlled simulators use shared candidate streams and potential outcomes. They are not public benchmark results and must not be reported as SOTA evidence.

## External database

Large assets are stored under `D:\Engineering\SQCAD\database`; see [DATA_STORAGE.md](DATA_STORAGE.md). The repository intentionally excludes raw corpora, model weights, generated results and caches.

## Documentation

- English overview: [docs/docs_en/00_overview.md](docs/docs_en/00_overview.md)
- English method: [docs/docs_en/01_method.md](docs/docs_en/01_method.md)
- English experiments: [docs/docs_en/02_experiments.md](docs/docs_en/02_experiments.md)
- English data and baselines: [docs/docs_en/03_data_and_baselines.md](docs/docs_en/03_data_and_baselines.md)
- Chinese research overview: [docs/docs_zn/00_研究总览.md](docs/docs_zn/00_研究总览.md)
- Chinese experiment plan: [docs/docs_zn/01_实验与基线方案.md](docs/docs_zn/01_实验与基线方案.md)

## Status

As of 2026-08-11:

- core store, workflow runner and controlled benchmark tests are present;
- 55 existing project tests passed before repository extraction;
- LongMemEval and LoCoMo data are externally frozen with provenance records;
- no claim is made that SQCAD outperforms FadeMem, Oblivion, Memory Worth, DeMem, SimpleMem or other SOTA systems.

## License

Research code is released under the MIT License. See [LICENSE](LICENSE).
