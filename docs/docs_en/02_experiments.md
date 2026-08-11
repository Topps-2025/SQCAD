# Experiments

## Evaluation ladder

1. **Protocol validation** — shared streams, immutable evidence, complete logs and reversible transitions.
2. **Controlled mechanism study** — hitchhikers, rare positives, stale memory, scope shifts, risk asymmetry and fixed budgets with enumerated potential outcomes.
3. **Baseline comparison** — keep-all, recency, fixed decay, BM25, dense, RRF, association-only access, v3 qualification gate and item-level causal control.
4. **Ablation and mechanism analysis** — qualification, scope transport, competitive normalization, positive protection, negative attenuation, fallback and restoration.
5. **External validation** — LongMemEval-S and LoCoMo under fixed chronological protocols; GoodAI-LTM only after the agent adapter and evaluator are reproducible.
6. **Stress and failure analysis** — unseen scopes, version shifts, scope-label permutation, boundary adversaries, budget extremes, evaluator drift and high qualification noise.

## Primary metrics

- future utility and future regret;
- false-forgetting regret;
- harmful-retention regret;
- scope transport error and negative transfer;
- matched-utility active tokens;
- qualification Brier score, ECE, sign error and interval coverage.

Retrieval metrics (Recall-any, Recall-all, NDCG and MRR) are process metrics. They cannot alone establish memory-governance causality.

## Scope overfitting test

The decisive test is not performance on already-seen scopes. The protocol must compare seen scopes, held-out users/tasks, tool or model-version shifts, return-to-old-scope episodes, multiple scope granularities and shuffled scope labels. A scoped method is supported as conditional denoising only if it improves unseen or shifted scopes without a proportional increase in false forgetting, rule complexity or audit cost.

## Decision gates

A method enters the public main claim only if it passes: data measurability, fair baseline comparability, qualification necessity, unseen-scope transport, low-frequency protection, fixed-budget efficiency, calibration and at least one public future-split plus one randomized micro-intervention slice. Otherwise the claim is reduced to the passing mechanism boundary.
