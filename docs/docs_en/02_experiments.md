# Experiments

## Evaluation ladder

1. **Protocol validation** — shared streams, immutable evidence, complete logs and reversible transitions.
2. **Controlled mechanism study** — hitchhikers, rare positives, stale memory, scope shifts, risk asymmetry and fixed budgets with enumerated potential outcomes.
3. **Baseline comparison** — 18-policy unified-contract main table: keep-all, recency, fixed decay, BM25, dense, RRF, association-only access, governance-proxy rows and the qualification-gated framework row.
4. **Ablation and mechanism analysis** — qualification, scope transport, competitive normalization, positive protection, negative attenuation, fallback and restoration (W0–W3 self-obscuring ablations).
5. **External validation** — LongMemEval-S and LoCoMo under fixed chronological protocols (`docs/研究逻辑与理论证明/17-…`); retrieval protocol run locally, end-to-end QA pending LLM endpoints.
6. **Stress and failure analysis** — unseen scopes, version shifts, scope-label permutation, boundary adversaries, budget extremes, evaluator drift and high qualification noise.

## Executed evidence (controlled, hash-frozen)

- **Gap construction (Theorems 1–2, Corollary 1)** — observationally equivalent worlds with opposite optimal lifecycle actions; exactly equal query-local causal effects with opposite lifecycle values; source-average transport failure. Baselines are given the *correct* answers and still fail — the gap is at the estimand layer.
- **Identification recovery (Theorem 3)** — under conditions C1–C8, the protocol route recovers known lifecycle values (bias ≈ 0, honest CIs, zero confident errors); all five tested condition violations are caught by the qualification gate as `unresolved`/`mismatch`.
- **Necessity (Lemma A–D, Theorems 4–5)** — alternatives for C2/C3/C6/C7/C8; committing rules on unidentified classes carry regret bounds and error probability ≥ 1/2; `R*(L,U) = U(−L)/(U−L)`.
- **Self-obscuring lifecycle (T1)** — committed no-recovery policies: regret Θ(T) (exact slope reproduced, e.g. 5.85); qualified recovery: O(1/qρ), independent of T; W0–W3 structural ablations.
- **Reduction separation (T2)** — every faithful feedback-preserving reduction without an evidence-availability state keeps Θ(T) worst-case regret; paired identity `regret_K + regret_A ≡ τp(T−n_early)` verified bit-exact for all four policies.
- **Minimax probing (P4)** — detection lower bound `E[probes] ≥ log(1/δ)/KL` and regret decomposition hold on the full grid; order-matching upper bounds; `U/L` strong-signal regime scales as 1/N*.
- **Unified-contract main table** — 18 policies on one candidate stream (stream SHA-256 identical across policies), 30 seeds, paired seed bootstrap CIs. SQCAD row: +0.100 [0.052, 0.156] utility vs best transportable baseline; rare recall 0.833 vs RRF 0.967 (reported honestly — the gain is stale control, not rare protection).
- **Cost contract** — lifecycle net benefit V over four price regimes; break-even probe price 110× default; probe-budget sweep; the retained negative result: forced restore in unidentified-harm worlds pushes V 38.62 → 8.73.

## Primary metrics

- future utility and future regret;
- false-forgetting regret;
- harmful-retention regret;
- scope transport error and negative transfer;
- matched-utility active tokens;
- qualification Brier score, ECE, sign error and interval coverage;
- recovery latency, probe count and cost.

Retrieval metrics (Recall-any, Recall-all, NDCG and MRR) are process metrics. They cannot alone establish memory-governance causality.

## Scope overfitting test

The decisive test is not performance on already-seen scopes. The protocol must compare seen scopes, held-out users/tasks, tool or model-version shifts, return-to-old-scope episodes, multiple scope granularities and shuffled scope labels. A scoped method is supported as conditional denoising only if it improves unseen or shifted scopes without a proportional increase in false forgetting, rule complexity or audit cost.

## Decision gates

A method enters the public main claim only if it passes: data measurability, fair baseline comparability, qualification necessity, unseen-scope transport, low-frequency protection, fixed-budget efficiency, calibration and at least one public future-split plus one randomized micro-intervention slice. Otherwise the claim is reduced to the passing mechanism boundary.
