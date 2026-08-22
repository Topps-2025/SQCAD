# SQCAD — Overview

SQCAD (**S**cope-qualified, **Q**uasi-causal **C**onditioning for **A**gent memory **D**ecisions) asks: **what evidence is qualified to change a memory's persistent access state, and how should a fixed workspace budget allocate access per task?**

The central problem is not relevance ranking. When the long-term value of a persistent `keep/archive` action is not identifiable from current observations, a relevance score must not be treated as authorization. SQCAD separates:

- **Evidence** — immutable source records and provenance, with censoring awareness (silence caused by archive is not evidence of low value); proposes candidates.
- **Qualification** — scope- and version-specific states $\{\text{positive},\ \text{negative},\ \text{unresolved},\ \text{mismatch}\}$ that authorize — or refuse — persistent change.
- **Access** — per-task competitive allocation under a fixed workspace budget, with keep / downweight / archive / restore / probe as formal, reversible actions.
- **Decision** — a persistent commit requires provable qualification: the identification set must not cross the action boundary, or $\min\{R^*(L,U),\ C_{\text{defer}},\ C_{\text{probe}} + R^*_{\text{after}}\}$ selects commit / defer / probe.

Qualification is conditional, not global: the same memory can be positive in one scope and unresolved or mismatched in another. Scope is a falsifiable conditional-denoising assumption, not a proven guarantee.

## Evidence status (2026-08-17)

| Layer | Content | Key results |
|---|---|---|
| L1 Theory | T1/T2/P4 formalization: regret $\Theta(T)$ without a recovery channel; restricted reduction separation; fixed-sample probing lower bounds; a finite-horizon `Safe(H,delta)` certificate pair with explicit false-restore cost; and the Certificate–Censoring Bridge to `QualificationAccess` | Frozen as sufficient, auditable contract-level conditions; no universal constant-regret recovery claim and no automatic raw-LLM coverage claim |
| L2 Public | LongMemEval-S + LoCoMo under a unified contract, chronological stream, AutoDL GPU re-check | Original SQCAD's shortcoming was evidence never entering the one-shot exposure pool, not qualification-layer ranking; minimal fix Guard-1 (≤1 BM25 candidate into the read pool; persistent-write authorization unchanged) raises LoCoMo official token-F1 0.0344 → 0.0455 |
| L3 Self-built | SQCAD-LifecycleBench: 1,380 keep/archive same-source counterfactual episodes, public/hidden truth separation, remote rebuild hash-identical | Directly measures lifecycle value, regret, false-commit, probe, restore; oracle upper bound +0.964, probe-willing +0.865; three framework changes quantified |
| Audit | R1–R5, R7 complete (truth independently checkable / failures possible / generalization challengeable / evaluation not guessable); R2 fragile parameters relocated; R6 human anchoring pending external judges | All 13 preregistered verdicts hit |

Framework-change verdicts: lineage conflict → archive (paired bootstrap +8.62 significant); hitchhiker association-only should not default to keep; scope lookahead deferred to Phase B end-to-end validation.

## Current boundaries

- The anytime/stitched Qualification guarantee is conditional on a certificate contract: predictable probing, a fixed lifecycle contrast, and conditional sub-Gaussian successful-probe observations. The implementation maps to the theorem under that contract; raw LLM certificates still require independent coverage/calibration evidence.
- Guard-1 is a minimal coverage fix that does not relax persistent authorization; it is **not** a claim of systematic SOTA superiority; dense/RRF reproduction is blocked by unavailable official weights.
- In the LifecycleBench rule world, the reference certificate is a full proxy of the visible-event rule; end-to-end (Phase B) is not yet run — rule-world results must not be written as end-to-end conclusions.
- R6 human anchoring and Phase B are the next work packages.

## Documents

- Chinese pages: [`docs_cn/00-研究总图.md`](../docs_cn/00-研究总图.md), `docs_cn/01-研究理念/`, `docs_cn/02-现有工作与痛点/`, `docs_cn/03-核心问题与框架设计/`, [`docs_cn/04-数据与实验/`](../docs_cn/04-数据与实验/README.md).
- English set: [01 Method](01_method.md), [02 Experiments](02_experiments.md), [03 Data and Baselines](03_data_and_baselines.md), [04 Reproducibility and Status](04_reproducibility_and_status.md), [05 Publication Checklist](05_publication_checklist.md).
- Full evidence chain (reports 00–21), formal proofs and experiment plans live under `docs/自用/` (internal).
