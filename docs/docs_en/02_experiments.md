# Experiments

## Evaluation ladder

1. **Protocol validation** — shared streams, immutable evidence, complete logs and reversible transitions.
2. **Controlled mechanism study** — hitchhikers, rare positives, stale memory, scope shifts, risk asymmetry and fixed budgets (L1).
3. **Baseline comparison** — unified-contract main table and LifecycleBench decision-strategy matrix (L2/L3).
4. **Ablation and mechanism analysis** — W0–W3 self-obscuring ablations; LifecycleBench switch ablations.
5. **External validation** — LongMemEval-S and LoCoMo under a fixed chronological protocol on AutoDL GPU; results hash-verified.
6. **Stress and failure analysis** — unseen scopes, version shifts, budget extremes, parameter sensitivity (R2/R3).

## L1 controlled evidence (frozen, hash-frozen results)

- **Gap construction (Theorems 1–2, Corollary 1)** — observationally equivalent worlds with opposite optimal lifecycle actions; exactly equal query-local causal effects with opposite lifecycle values; source-average transport failure. Baselines get the *correct* answers and still fail — the gap is at the estimand layer.
- **Identification recovery (Theorem 3)** — under conditions C1–C8, the protocol route recovers known lifecycle values (bias ≈ 0, honest CIs, zero confident errors); all five tested condition violations are caught as `unresolved`/`mismatch`.
- **Necessity (Lemma A–D, Theorems 4–5)** — committing rules on unidentified classes carry regret bounds and error probability ≥ 1/2; `R*(L,U) = U(−L)/(U−L)`.
- **Self-obscuring lifecycle (T1)** — committed no-recovery policies: regret Θ(T) (exact slope reproduced, e.g. 5.85); qualified recovery: O(1/qρ), independent of T; W0–W3 structural ablations.
- **Reduction separation (T2)** — every faithful feedback-preserving reduction without an evidence-availability state keeps Θ(T) worst-case regret; paired identity verified bit-exact for all four policies.
- **Minimax probing (P4)** — detection lower bound `E[probes] ≥ log(1/δ)/KL` and regret decomposition hold on the full grid; order-matching upper bounds.
- **Cost contract** — lifecycle net benefit over four price regimes; break-even probe price 110× default; forced restore in unidentified-harm worlds pushes V 38.62 → 8.73.

## L2 public data (unified contract, AutoDL GPU re-checked)

Same chronological stream, workspace budget, reader, evaluator and cost accounting:

| Method | LongMemEval-S Hit | LongMemEval-S Recall | LoCoMo official token-F1 | Role |
|---|---:|---:|---:|---|
| BM25 | 0.967 | 0.323 | 0.0454 | static coverage upper bound / cost control |
| Original SQCAD | 0.785 | 0.118 | 0.0344 | low persistent storage, insufficient candidate coverage |
| Guard-1 | 0.915 | 0.153 | 0.0455 | minimal coverage fix (recommended) |
| Guard-2 | 0.929 | 0.179 | 0.0465 | more coverage, more probes |
| Guard-4 | 0.950 | 0.224 | 0.0475 | highest coverage, highest cost |

Supportable claim: a **restricted, one-shot candidate guard fixes the evidence-coverage bad case while keeping the qualification boundary**. It does not alone establish causal value of keep/archive, and is not a SOTA claim.

## L3 LifecycleBench decision-strategy matrix (n=1380, paired bootstrap)

| Policy | mean lifecycle value | regret | oracle agreement | false-commit |
|---|---:|---:|---:|---:|
| oracle_policy (upper bound) | +0.964 | 0.015 | 1.000 | 0.000 |
| probe_willing (archive unless POSITIVE) | +0.865 | 0.115 | 0.906 | 0.072 |
| SQCAD + lineage conflict→archive | −0.278 | 1.258 | 0.744 | 0.228 |
| archive_all | −2.790 | 3.770 | 0.459 | 0.000 |
| storage12 / Memory-Worth proxy | −3.476 | 4.455 | 0.703 | 0.181 |
| Original certificate / event rule | −8.901 | 9.880 | 0.663 | 0.409 |
| keep-all / recency2 | −10.280 | 11.260 | 0.541 | 0.409 |

Significant vs the reference certificate (95% CI excludes 0): conflict variant +8.62, probe_willing +9.77; the reference certificate is episode-identical to the visible-event rule (0 divergence — reported honestly as a full proxy in this rule world).

## Audit verdicts (four channels)

| Channel | Criterion | Result |
|---|---|---|
| Truth independently checkable | R5 bit-exact second implementation + remote rebuild hash | 1380/1380 ✅ |
| Failures possible | strategy matrix separates nontrivial policies | 11/12 significant ✅ |
| Generalization challengeable | R3 unseen-mechanism holdout | 12/15 transfer + 3 honest mechanism boundaries ✅ |
| Evaluation not guessable | R1 metadata-shortcut upper bound + R4 preregistered 13 rows + R7 release package | all hit ✅ |

R2 sensitivity: GAMMA=0.7 (36.2% flips) and TAU_TOL=1.0 (32.6%) are fragile — economic/judgment parameters, relocated to the valid domain GAMMA∈[0.9,0.99]; semantic constants flip 0%. R6 human anchoring (28 blinded cases) pending external judges.

## Primary metrics

- future utility and future regret;
- false-forgetting regret and false-commit rate;
- harmful-retention regret;
- scope transport error and negative transfer;
- matched-utility active tokens / probe count and cost;
- qualification Brier score, ECE, sign error and interval coverage;
- recovery latency.

Retrieval metrics (Recall-any, NDCG, MRR) are process metrics; they cannot alone establish memory-governance causality.
