---
type: manuscript-section
section: experiments
language: English
status: preliminary-evidence-bounded
paper_type: algorithmic
target_venue: generic
---

# Experiments

## One-sentence argument

Across controlled representation, causal-estimation and sequential-policy environments, evidence-grounded decomposition and scope-constrained abstraction improved governance only when their semantic grouping was sufficiently accurate, while experiments on LongMemEval-S showed that lexical and local predicate–argument sidecars did not yet improve the multi-metric retrieval frontier; the present evidence therefore supports a conditional continuation of the framework, not an end-to-end or state-of-the-art claim.

## 1. Evaluation questions

We organized the evaluation around four questions that correspond directly to the two gaps in the Introduction.

**Q1: Does decomposition–abstraction create a more transferable governance unit than a trajectory-bound memory?** We tested whether a rule supported by decomposed factors transferred across changes in surface identity, preserved a low-frequency high-impact category, and failed predictably as decomposition accuracy declined.

**Q2: Can the proposed logging and estimation interface recover memory effects under endogenous exposure?** We calibrated static outcome-regression, inverse-propensity and doubly robust estimators against a known average treatment effect, and then evaluated finite-horizon policy values when previous exposure changed subsequent task state and treatment propensity.

**Q3: Does mechanism-level governance outperform item-level and heuristic controls under a fixed retention budget?** We compared recency, frequency, decay-like, outcome-feedback-like, item-level causal and decomposition–abstraction causal policies under environment shift and increasing mechanism-group noise.

**Q4: Do the current representation modules improve a real long-term-memory benchmark under strong retrieval controls?** We evaluated raw sessions, lexical factor and rule proxies, an auditable predicate–argument sidecar, BM25, dense retrieval and development-tuned reciprocal-rank fusion on LongMemEval-S [@Wu2024LongMemEval]. This question separates a useful mechanism in a controlled environment from external validity on natural dialogue histories.

## 2. Experimental environments

### 2.1 Controlled representation environment

The representation simulator contained 24 latent categories. Each category had an opaque identity during training and a different opaque identity at test time, while its operative latent conditions were held fixed. One rare but critical category contributed only two training observations, causing a median-frequency retention rule to discard it. We compared exact surface matching, frequency-based retention, factor-level matching without abstraction, the proposed factor-to-rule representation and an oracle that observed the true latent factor. Unless otherwise stated, the decomposition operator measured the latent factor correctly with probability 0.90. We ran 30 independent seeds.

This environment is a mechanism check rather than a natural-language benchmark. It isolates the proposition that abstraction can transfer an evidence-supported condition across a surface shift, but it does not test whether a language model can recover that condition from unrestricted trajectories.

### 2.2 Static causal calibration

The static data-generating process included an observed task condition that affected both memory exposure and outcome. A rare high-impact stratum represented 20% of observations and had a treatment effect of 1.0; the common stratum represented 80% and had a treatment effect of 0.2, giving a true average treatment effect of 0.36. Exposure probabilities were 0.15 and 0.85 in the two strata. For each of 50 seeds, we generated 4,000 observations. The doubly robust estimator deliberately used a misspecified outcome model but the correct propensity, testing one side of the double-robustness property [@BangRobins2005DoublyRobust].

### 2.3 Sequential off-policy calibration

The sequential environment had a horizon of five and discount factor 0.95. Previous memory exposure changed the next difficulty state, which in turn affected later exposure probabilities and rewards. Each of 20 seeds contained 5,000 logged trajectories. We evaluated three target policies—never expose, expose only in the high-difficulty state and always expose—using trajectory importance sampling and stepwise doubly robust off-policy evaluation [@JiangLi2016DROPE; @ThomasBrunskill2016OffPolicy]. Independent Monte Carlo rollouts supplied the reference policy values.

### 2.4 Memory-governance stress test

The governance simulator contained 120 memory items: 12 rare-critical, 24 common-useful, 24 stale and 60 noise items. Every method retained 36 items. Effect estimates were learned from two environments and evaluated in a third, with 12,000 samples per environment and 50 seeds. The proposed policy received a candidate mechanism grouping whose error rate was varied over 0.0, 0.1, 0.2 and 0.4. Group noise represents decomposition or abstraction error; it is not an estimate of a real semantic parser’s accuracy.

### 2.5 LongMemEval-S and semantic Gate A

We used the cleaned LongMemEval-S file from upstream commit 9e0b455f4ef0e2ab8f2e582289761153549043fc. The file SHA-256 was D6F21EA9D60A0D56F34A05B609C79C88A451D2AE03597821EA3D5A9678C3A442. Following the benchmark protocol, we excluded 30 abstention questions and evaluated 470 questions at session granularity. This experiment assessed retrieval of annotated evidence sessions; it did not invoke a common answer model and therefore did not measure final question-answering accuracy.

LongMemEval-S does not label latent causal factors. We therefore prepared, but have not yet completed, a semantic-decomposition qualification set. The set contains 200 question packets—70 multi-session, 50 temporal-reasoning, 50 knowledge-update and 30 preference packets—covering 418 evidence sessions and 4,930 turns. Forty packets form a blinded double-annotation pilot and 160 form the main set. Pre-registered acceptance criteria use conservative bootstrap bounds: factor micro-F1 lower bound at least 0.80, relation F1 lower bound at least 0.70, provenance coverage lower bound at least 0.95, scope completeness lower bound at least 0.90, and upper bounds of 0.10 for negation/temporal/update error and rule overgeneralization. The annotation assets are ready, but no human agreement, adjudication or parser score is reported here. Gate A is therefore not passed.

As a reproducibility and leakage-control check, we also implemented a query-independent POS/regex lower-bound parser (`semantic_decomposition_pos_baseline.py`). It emits sentence-level evidence spans, conservative entity/attribute/action/preference/time candidates and a small set of typed local relations, while emitting no abstract rules. The parser does not read questions, reference answers, answer-session IDs or annotations; its output removes the adjudication-only field and is checked for packet identity, exact span provenance and closed factor--relation references. The resulting 200-packet artifact passes two structural tests. Because the current Gate A file is still an unannotated template, a scorer run would have zero gold components and would not be a meaningful representation score. We therefore report this artifact only as a structural negative control, not as a Gate A result, semantic-parser score or causal benchmark.

### 2.6 Controlled natural-language surface-shift test

To bridge the fully abstract representation simulator and the still-unlabelled Gate A, we generated natural-language evidence records with known latent factors and outcomes. Training and OOD records used different entity names, attribute terms and sentence templates. We compared exact raw-surface memory, an attribute-word lexical map, decomposition without cross-context abstraction, evidence-supported factor-rule abstraction and an oracle joint representation. The parser-accuracy parameter explicitly corrupted latent-factor measurements and must not be interpreted as the accuracy of an LLM parser. We used 50 seeds at parser accuracies 0.90, 0.60 and 0.50.

### 2.7 Unified workflow smoke runner

We connected immutable evidence writes, factor sidecars, a shared candidate stream, fixed-budget workspace exposure, controlled agent decisions, outcome evaluation, atomic propensity/exposure/adoption logs and reversible state transitions in one runner. Six policies received identical stream hashes, task sequences, 12-item workspace budgets and evaluators over 30 seeds and 100 steps per seed. This environment verifies the system interface and comparison discipline; its synthetic candidate features and controlled agent do not constitute a public benchmark.

## 3. Baselines and reproduction status

We distinguished a reproduced control from a behavioural proxy and from a published system that remains to be reproduced. This distinction prevents simulator results from being presented as comparisons with external systems.

| Baseline family | Implementation in this study | Evaluation scope | Status |
| --- | --- | --- | --- |
| Recency and frequency | Deterministic retention and retrieval rules | Controlled governance and LongMemEval-S | Implemented |
| Decay-like policy | Time/access-based simulator policy | Controlled governance only | Behavioural proxy; not a FadeMem reproduction |
| Outcome-feedback-like policy | Success/value proxy in the simulator | Controlled governance only | Behavioural proxy; not a Memory Worth reproduction |
| Item-level causal stable | Per-item effect and stability ranking without mechanism abstraction | Controlled governance | Implemented strong mechanism control |
| Risk-gated decomposition--abstraction causal | Group-level stable effect with calibrated confidence, cross-level sign check and item-level negative-effect fallback | Controlled governance | Implemented controlled method variant; not a public-system reproduction |
| BM25 | Session-level lexical retrieval | LongMemEval-S | Implemented |
| MiniLM dense | all-MiniLM-L6-v2, 256-token session truncation | LongMemEval-S | Implemented |
| BM25+dense RRF | Development-tuned dense rank weight | LongMemEval-S | Implemented strong retrieval control |
| Chunked MiniLM dense/RRF | 220-token chunks with 32-token overlap and max session pooling | LongMemEval-S | Smoke-tested only; full CPU run not completed, excluded from results |
| FadeMem, Oblivion, Memory Worth, DeMem and ReMe | Authors’ published methods [@Wei2026FadeMem; @Rana2026Oblivion; @Simsek2026MemoryWorth; @Zou2026DeMem; @Cao2026ReMe] | Planned end-to-end evaluation | Not yet reproduced |

Consequently, the controlled comparisons test mechanism hypotheses, whereas the public-data experiments currently test retrieval and representation controls. They are not pooled into one leaderboard, and the proxy rows are never labelled with the names of published systems.

## 4. Metrics and statistical protocol

Representation quality was measured by out-of-distribution accuracy, rule precision, rule false-positive rate and rare-critical retention. Static causal calibration used estimator bias against the known average treatment effect and interval coverage. Sequential calibration used policy-ranking accuracy and mean absolute policy-value error. Governance quality used normalized test utility, rare-critical recall, stale-memory retention and precision among retained positive memories.

For LongMemEval-S, Recall-any@1 measured whether at least one relevant session appeared first, whereas Recall-all at 5 and 10 measured whether all annotated evidence sessions were recovered. We additionally reported NDCG-any, mean reciprocal rank, representation-token ratio and preprocessing cost. This multi-metric protocol prevents an increase in broad evidence coverage from hiding a deterioration in top-rank quality.

Unless explicitly stated otherwise, reported uncertainty is the mean plus or minus the 95% normal-approximation confidence-interval half-width across independent seeds or deterministic data splits. Public retrieval comparisons used ten stable 20/80 development–test splits. Hyperparameters were selected on the development portion and evaluated once on the corresponding held-out portion. Paired method differences were computed within the same seed or split.

## 5. Controlled results

### 5.1 Decomposition–abstraction transferred across surface shift

Exact surface matching achieved perfect in-distribution accuracy but only 0.667 out-of-distribution accuracy after category identities changed. Frequency retention and factor matching without abstraction also achieved 0.667. At decomposition accuracy 0.90, the proposed representation reached 0.898 ± 0.011, compared with the oracle-factor upper reference of 1.000. Rule precision was 0.823 ± 0.020, and the rule false-positive rate was 0.099 ± 0.015. The frequency and factor-only controls both failed to preserve the low-frequency critical category, whereas the proposed rule recalled it in every seed.

| Representation or policy | OOD accuracy | Rare-critical recall |
| --- | ---: | ---: |
| Surface identity | 0.667 ± 0.000 | 0.000 |
| Frequency retention | 0.667 ± 0.000 | 0.000 |
| Factor without abstraction | 0.667 ± 0.000 | 0.000 |
| Decomposition–abstraction | 0.898 ± 0.011 | 1.000 |
| Oracle latent factor | 1.000 ± 0.000 | 1.000 |

The gain was not unconditional. When decomposition accuracy fell to 0.60, proposed OOD accuracy fell to 0.609 ± 0.022, below the surface baseline of 0.667, and rule precision fell to 0.439 ± 0.025. At decomposition accuracies of 0.75, 0.90 and 1.00, OOD accuracy was 0.760 ± 0.016, 0.898 ± 0.011 and 1.000, respectively. Abstraction therefore amplified useful structure only after the candidate representation was sufficiently accurate; below that regime, it amplified measurement error.

### 5.2 Controlled textual evidence reproduced the surface-shift mechanism

In the controlled natural-language generator, exact surface memory, attribute-word lookup and decomposition without cross-context abstraction each achieved OOD accuracy 0.667. At parser accuracy 0.90, evidence-supported factor-rule abstraction achieved 0.946 ± 0.007 OOD accuracy, rule precision 0.917 ± 0.012 and rare-critical recall 0.900 ± 0.050 over 50 seeds. At parser accuracies 0.60 and 0.50, OOD accuracy declined to 0.791 ± 0.013 and 0.725 ± 0.012; rule precision declined to 0.697 ± 0.022 and 0.617 ± 0.024, and rare-critical recall declined to 0.680 ± 0.072 and 0.467 ± 0.097. The oracle joint representation achieved 1.000.

This test strengthens only the controlled mechanism claim: natural-language surface changes defeat exact and lexical memory, while a sufficiently accurate canonical factor can support rule reuse. Because the parser receives simulator-generated factor measurements with injected noise, these values do not estimate the performance of an LLM semantic parser and do not replace Gate A.

### 5.3 Propensity-aware estimators removed induced selection bias

The unadjusted exposed–unexposed difference estimated the average treatment effect as 1.048 and had bias +0.688 ± 0.012 relative to the true value of 0.36. A misspecified outcome regression that ignored the confounder had the same bias. Stratified outcome regression, inverse-propensity weighting and doubly robust estimation reduced mean bias to −0.001 ± 0.011, −0.006 ± 0.019 and −0.001 ± 0.014, respectively.

| Estimator | Mean ATE estimate | Bias ± 95% CI half-width |
| --- | ---: | ---: |
| Naive exposed–unexposed difference | 1.048 | +0.688 ± 0.012 |
| Misspecified outcome regression | 1.048 | +0.688 ± 0.012 |
| Adjusted outcome regression | 0.359 | −0.001 ± 0.011 |
| Inverse-propensity weighting | 0.354 | −0.006 ± 0.019 |
| Doubly robust estimator | 0.359 | −0.001 ± 0.014 |

The doubly robust interval covered the known effect in all 50 toy datasets, with an average within-dataset half-width of 0.108. This coverage was conservative and should not be interpreted as evidence of calibration in a real agent. The result supports a narrower engineering conclusion: behaviour propensities and pre-exposure state must be recorded if outcome feedback is to be interpreted causally.

### 5.4 Sequential estimators recovered the policy ordering

The expose-only-at-high-difficulty policy had the largest reference value in every seed. Both trajectory importance sampling and stepwise doubly robust evaluation ranked the three policies correctly in all 20 seeds. Mean absolute value error was 0.086 ± 0.022 for importance sampling and 0.081 ± 0.020 for the doubly robust estimator. For the high-difficulty-only policy, their mean biases were −0.002 ± 0.010 and approximately 0.000 ± 0.008, respectively.

These results verify the software interface between logged propensities and finite-horizon evaluation in a small discrete environment. They do not show that doubly robust evaluation universally dominates importance sampling: the error difference was modest, and the policy and state spaces were intentionally small.

### 5.5 Mechanism grouping helped only while decomposition noise remained controlled

With correct mechanism groups, the decomposition–abstraction causal policy obtained normalized utility 1.000, rare-critical recall 1.000, stale retention 0.000 and retained-positive precision 1.000. Under group noise 0.1, 0.2 and 0.4, normalized utility declined to 0.867 ± 0.010, 0.720 ± 0.020 and 0.482 ± 0.028. Rare-critical recall declined to 0.945, 0.872 and 0.690, while stale retention increased to 0.063, 0.146 and 0.254.

| Group noise | Normalized utility | Rare-critical recall | Stale retention | Positive precision |
| ---: | ---: | ---: | ---: | ---: |
| 0.0 | 1.000 ± 0.000 | 1.000 | 0.000 | 1.000 |
| 0.1 | 0.867 ± 0.010 | 0.945 | 0.063 | 0.849 |
| 0.2 | 0.720 ± 0.020 | 0.872 | 0.146 | 0.696 |
| 0.4 | 0.482 ± 0.028 | 0.690 | 0.254 | 0.474 |

At noise 0.4, the ungated item-group policy achieved normalized utility 0.482 versus 0.493 for the item-level causal control, with a paired difference of −0.011 ± 0.033. We therefore added a pre-specified risk-gated variant: calibrated representation confidence, cross-level effect-sign consistency and an item-level negative-effect veto trigger fallback to the item-level score. The gated policy achieved utility 0.815, rare-critical recall 0.690, stale retention 0.007 and positive precision 0.896 at the same noise level. Across noise 0.0, 0.1, 0.2 and 0.4, its paired utility win rate against the item-level causal control was 1.00 in every condition; at noise 0.4, the paired utility delta was +0.322 ± 0.022 and the rare-critical delta was +0.552 ± 0.038. Stale retention was not strictly improved over a baseline whose rate is already zero. Thus, the gate mitigates error propagation in the controlled model but does not establish universal Pareto dominance or public-benchmark validity.

At group noise 0.4, removing individual gates produced the following ablation results: confidence-only 0.788 utility / 0.028 stale retention, sign-consistency-only 0.862 / 0.044, negative-veto-only 0.801 / 0.058, and the combined gate 0.815 / 0.007. The modules therefore target different failure modes; the combined policy trades a small amount of rare-critical recall for substantially lower stale retention and higher positive precision. These are controlled mechanism results, not evidence that the real semantic parser is calibrated.

### 5.6 The unified runner preserved comparison invariants

In the 30-seed workflow smoke test, item-level causal governance achieved task success and utility 0.891 ± 0.053, stale exposure 0.000, rare-critical recall 0.217 ± 0.073 and retained-positive precision 0.739. Risk-gated decomposition--abstraction achieved 0.991 ± 0.018 task success and utility, stale exposure 0.000, rare-critical recall 0.833 ± 0.079 and positive precision 0.939 at a comparable average workspace cost (359.7 versus 360.8 tokens). Recency, frequency, fade-like and outcome-feedback proxies retained stale evidence in every seed and failed to retain rare-critical items. All policies had decision-log completeness 1.0 and identical candidate-stream hashes within seed. These results show that the full workflow and logging contract are executable under a common substrate; they do not add external-validity evidence beyond the controlled generator.

## 6. Public-benchmark retrieval controls

### 6.1 Strong raw-evidence retrieval baselines

Across ten held-out splits, BM25 achieved Recall-all@5 of 0.8273 ± 0.0042 and MRR of 0.9085 ± 0.0031. MiniLM dense retrieval was lower overall under the fixed 256-token encoding budget, with Recall-all@5 of 0.7707 ± 0.0021 and MRR of 0.8379 ± 0.0035. Development-tuned BM25+dense RRF increased Recall-all@5 to 0.8607 ± 0.0044 and Recall-all@10 to 0.9275 ± 0.0061, but reduced Recall-any@1 and MRR relative to BM25.

| Retriever | Recall-any@1 | Recall-all@5 | NDCG-any@5 | Recall-all@10 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.8663 ± 0.0038 | 0.8273 ± 0.0042 | 0.8823 ± 0.0026 | 0.9001 ± 0.0025 | 0.9085 ± 0.0031 |
| MiniLM dense | 0.7693 ± 0.0053 | 0.7707 ± 0.0021 | 0.8037 ± 0.0030 | 0.8789 ± 0.0034 | 0.8379 ± 0.0035 |
| BM25+dense RRF | 0.8419 ± 0.0086 | 0.8607 ± 0.0044 | 0.8923 ± 0.0042 | 0.9275 ± 0.0061 | 0.8997 ± 0.0055 |

The hybrid is therefore the strongest current control for multi-evidence coverage, whereas BM25 remains stronger on the first-rank and reciprocal-rank metrics. Any end-to-end governance claim must be evaluated against both operating points rather than selecting one favourable metric.

We also audited stronger dense configurations. A BGE-small-en-v1.5 run could not download its model files under the current Hugging Face proxy, and a full chunked MiniLM run was stopped after approximately one hour and nearly 2 GB of CPU working memory without producing a result file. A five-question smoke test verified the implementation but is not a benchmark result. These attempts are documented in the [[experiments/LongMemEval-S强检索基线扩展审计|strong-retrieval audit]]; they do not alter the completed BM25, MiniLM and RRF numbers above.

### 6.2 Lexical decomposition and abstraction were insufficient

Using the complete data without development tuning, a two-sentence lexical factor proxy achieved Recall-all@5 of 0.253, a keyword rule proxy achieved 0.491, and a rule-plus-evidence proxy achieved 0.385, compared with 0.830 for raw sessions. Development-tuned sidecar fusion did not recover the loss: the selected sidecar weights were usually zero, and none of the three sidecars produced a stable held-out gain over raw BM25.

These negative results changed the engineering design. Decomposed candidates and abstract rules are maintained as sidecars, while the raw evidence ledger remains the primary recoverable store. Compression ratio alone is not treated as success, and a rule is not permitted to replace its source before provenance, scope and utility gates are satisfied.

### 6.3 An auditable relation sidecar traded coverage for rank quality

The POS-v2 relation extractor produced at least one relation for 18,233 of 18,239 unique sessions and used approximately 10.9% of the raw token count. Relation-only retrieval nevertheless achieved Recall-all@5 of only 0.5159 ± 0.0094. Development-tuned raw-plus-relation fusion increased Recall-all@5 from 0.8273 to 0.8295, a paired change of +0.0021 ± 0.0020. This small coverage increase was accompanied by changes of −0.0717 ± 0.0222 in Recall-any@1, −0.0155 ± 0.0094 in NDCG-any@5 and −0.0389 ± 0.0138 in MRR. It also remained below the BM25+dense RRF Recall-all@5 of 0.8607.

The relation sidecar therefore did not form a Pareto improvement. High extraction coverage did not imply semantic sufficiency, and local predicate–argument structure did not preserve cross-session reference, time, update or applicability scope. This negative result justifies the manually auditable semantic Gate A before further full-corpus experiments.

## 7. Ablations and completion status

| Ablation or control | Claim isolated | Current status |
| --- | --- | --- |
| Remove abstraction while keeping factors | Cross-surface transfer requires scoped rules rather than factor extraction alone | Completed in the representation simulator |
| Sweep decomposition or group noise | Benefits depend on semantic qualification | Completed in two controlled environments |
| Replace grouped governance with item-level causal ranking | Gain is not caused by effect estimation alone | Completed in the governance simulator |
| Replace semantic candidates with lexical and POS relations | Finer granularity alone is insufficient | Completed on LongMemEval-S |
| Remove provenance pointers | Evidence preservation limits unsupported abstraction | Planned after Gate A |
| Remove scope and version constraints | Scope limits rule overgeneralization | Planned after Gate A |
| Delete raw evidence after abstraction | Sidecars cannot safely replace recoverable evidence | Planned risk ablation |
| Replace reversible transitions with hard deletion | Reversibility controls false-forgetting cost | Planned end-to-end ablation |
| Symmetric versus asymmetric governance loss | Rare high-impact memories require risk-sensitive control | Planned end-to-end ablation |
| Remove or replace the optional free-energy regularizer | The cognitive prior must contribute beyond ordinary complexity control | Planned; not part of the core claim |
| BM25, dense and hybrid candidate generators | Retrieval changes must not be attributed to governance | Public retrieval controls completed; end-to-end governance pending |

## 8. Interim decision and claim boundary

The current evidence supports **Conditional GO**. The controlled results establish three necessary conditions: a sufficiently accurate factor-to-rule interface can transfer across surface identity; propensity-aware estimators can remove induced selection bias; and finite-horizon logged evaluation can recover the correct policy ordering in a small environment. The same experiments also expose a concrete failure mode: noisy decomposition can erase the utility advantage over item-level causal governance.

External validity is not yet established. The public benchmark results show that inexpensive lexical and local-relation sidecars are inadequate and that the strongest available retrieval control is already competitive. We therefore do not claim that the full framework improves final task accuracy, outperforms a reproduced forgetting system or reaches a state of the art. Such language becomes admissible only after double-annotated Gate A qualification, a common reader and evaluator, reproduced forgetting baselines, fixed resource budgets, multiple seeds and an improvement on the utility–risk–cost frontier.

## Section outline

1. Questions link each paper claim to a falsifiable evaluation.
2. Four controlled environments isolate representation, static estimation, sequential estimation and governance.
3. LongMemEval-S supplies external retrieval controls; Gate A supplies the missing semantic qualification protocol.
4. Controlled results establish necessary feasibility and an explicit noise-dependent failure regime.
5. Public-data lexical and relation sidecars provide negative evidence that changes the architecture.
6. Completed and planned ablations distinguish current evidence from the remaining paper claims.
7. The section closes with a Conditional-GO decision and a strict boundary against SOTA language.

## Claim–evidence map

| Claim | Evidence | Status |
| --- | --- | --- |
| Decomposition–abstraction can transfer across a surface shift when the operative factor is recovered accurately. | Thirty-seed representation simulator; OOD accuracy 0.898 ± 0.011 at decomposition accuracy 0.90. | Supported in a controlled environment |
| The representation can be worse than surface matching when decomposition is inaccurate. | Accuracy sweep; OOD accuracy 0.609 ± 0.022 at decomposition accuracy 0.60 versus 0.667 for surface matching. | Supported in a controlled environment |
| Outcome co-occurrence can severely misestimate memory value under endogenous exposure. | Fifty-seed static calibration; naive bias +0.688 ± 0.012 versus doubly robust bias −0.001 ± 0.014. | Supported for the specified data-generating process |
| Logged sequential evaluation can rank simple governance policies. | Twenty-seed finite-horizon experiment; correct ordering in all seeds. | Supported for a small discrete environment |
| Correct mechanism groups can preserve rare-critical memories under a fixed budget. | Fifty-seed governance simulator at zero group noise. | Supported only with known or accurate grouping |
| Lexical and local relation sidecars improve real long-term-memory retrieval. | LongMemEval-S experiments showed no multi-metric Pareto improvement. | Not supported; current evidence is negative |
| The complete framework improves end-to-end Agent Memory utility or exceeds SOTA. | No Gate-A-qualified parser, common answer model or reproduced forgetting leaderboard is complete. | Needs evidence |

## Assumptions or missing inputs

- A target venue, paper length and mandatory reporting format have not been selected.
- Human Gate A annotation, adjudication and semantic-parser evaluation remain incomplete.
- Published forgetting systems have not yet been reproduced under a common candidate stream, reader, evaluator and resource budget.
- LongMemEval-S results currently measure evidence retrieval, not final answer correctness or long-horizon governance.
- The controlled environments expose known factors and interventions; they do not resolve unmeasured confounding or interference among arbitrary real memories.

## 中文结构说明

- 本节把“解构与抽象”拆成可单独否证的表示命题，不把它写成已经成立的因果发现能力。
- 四组模拟实验分别校验表示、静态识别、序贯策略值和治理；它们不与公开 benchmark 数字混成一张 SOTA 表。
- baseline 表明确区分“真实实现”“行为代理”和“尚待复现的论文方法”，避免把 fade-like 或 outcome-feedback-like 代理冒充 FadeMem、Memory Worth。
- LongMemEval-S 的负结果被写入主论证：原始证据必须作为主存储，因子与规则只能先作为可回退 sidecar。
- 当前结论固定为 Conditional GO。论文只能主张“机制具有受条件支持的可行性”，不能主张真实 Agent Memory 端到端提升。

## Related documents

[[07-English-Introduction-Draft|English Introduction]]、[[08-English-Method-Draft|English Method]]、[[03-因果推断驱动的Agent Memory遗忘框架论文方案|Method and experiment blueprint]]、[[05-解构抽象因果遗忘框架阶段性可行性判断|Conditional-GO assessment]]、[[experiments/LongMemEval-S初步检索基线报告|LongMemEval-S retrieval controls]]、[[experiments/LongMemEval-S可审计关系Sidecar实验报告|Relation-sidecar negative result]]、[[experiments/semantic_gate_a/LongMemEval语义解构Gate-A标注规范|Semantic Gate A]]、[[experiments/semantic_gate_a/规则语义解构baseline报告|POS/Regex lower-bound parser report]]
