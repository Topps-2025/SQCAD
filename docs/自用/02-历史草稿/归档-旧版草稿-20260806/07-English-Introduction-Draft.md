---
type: manuscript-section
section: introduction
language: English
status: evidence-bounded-draft
paper_type: algorithmic
target_venue: generic
---

# Introduction

## One-sentence argument

In resource-constrained agents, we study whether forgetting can be made more reliable by converting trajectory-bound memories into evidence-grounded, manipulable factor and rule candidates, estimating their sequential effects under endogenous exposure, and translating stable conditional effects into reversible, risk-sensitive state transitions; controlled calibration supports the mechanism, whereas public end-to-end superiority remains to be established.

## Terminology ledger

| Canonical term | Definition at first use | Terms not used as synonyms |
| --- | --- | --- |
| Agent memory | External, addressable memory used by a language-model agent across interactions. | Model parameters; context window alone. |
| Memory governance | Lifecycle decisions that change future accessibility or influence. | Physical deletion only. |
| Evidence-grounded decomposition | Construction of factor and relation candidates with exact provenance. | Sentence splitting; causal discovery. |
| Scope-constrained abstraction | Construction of conditional rule candidates with support evidence and explicit applicability boundaries. | Unconditional generalization; summarization. |
| Component bundle | A factor or rule candidate together with supporting evidence, scope and version metadata. | Isolated token; unsupported natural-language rule. |
| Sequential causal governance | Estimation and control of memory exposure and state actions over time. | Success co-occurrence; an importance score. |
| Reversible forgetting | Downweighting, archiving, isolation and restoration under explicit risk and legality constraints. | Irreversible deletion by default. |

## Draft

External memory allows language-model agents to preserve task state, user constraints, environmental facts and reusable experience across interactions that exceed a single context window. This capability is necessary for long-horizon assistance, but it also creates a growing set of retrieval candidates, conflicting versions and prompt-time costs. Agent memory therefore requires lifecycle governance rather than unbounded accumulation. Recent approaches have moved beyond fixed windows by introducing differential decay, accessibility control, outcome feedback, decision-oriented compression and refinement of procedural experience [@Wei2026FadeMem; @Rana2026Oblivion; @Simsek2026MemoryWorth; @Zou2026DeMem; @Cao2026ReMe]. In this setting, forgetting is better defined as a resource-constrained decision over a memory's future accessibility and influence than as the physical deletion of old records.

Most existing governance signals are inexpensive proxies derived from the agent's own trajectory. Recency and access frequency approximate continued demand; semantic relevance controls query–memory matching; and task feedback propagates downstream success or failure to the memory state. These signals are attractive because they can be updated online and integrated with established retrieval stacks without repeatedly evaluating counterfactual outcomes. Decision-oriented compression further shows that a memory representation need not preserve every textual detail if it retains distinctions required for downstream decisions [@Zou2026DeMem]. However, a trajectory segment, summary or procedural trace can still bind a potentially operative condition to names, wording, time, co-occurring events and other surface features. Finer segmentation does not by itself resolve this problem: a governance unit must also be traceable, manipulable and scoped.

The first unresolved problem is **causal addressability under endogenous memory exposure**. A memory can co-occur with success or failure only after the current candidate generator, retriever and workspace policy have made it visible. Task difficulty, the candidate set, model and tool versions, prompt position and jointly exposed memories can affect both exposure and outcome. Consequently, an irrelevant memory may be reinforced because it frequently accompanies easy successes, whereas a protective memory may be suppressed because it reduces loss on difficult tasks without changing a binary failure into success. Potential-outcome methods, marginal structural models, doubly robust estimation and cross-fitting provide tools for selection bias and time-varying confounding [@Pearl2009Causality; @HernanRobins2020WhatIf; @Robins2000MSM; @BangRobins2005DoublyRobust; @Chernozhukov2018DML]. Causal representation learning, causal-model abstraction and off-policy evaluation address manipulable variables, cross-level mappings and policy value, respectively [@Scholkopf2021CausalRepresentation; @BeckersHalpern2019AbstractingCausalModels; @SwaminathanJoachims2015CRM; @JiangLi2016DROPE; @ThomasBrunskill2016OffPolicy]. Yet these strands have not been unified into an auditable Agent Memory formulation that jointly decomposes trajectory evidence, defines factor-level exposure, records adoption and action, and estimates the effects of sequential governance decisions.

The second unresolved problem is **evidence-preserving abstraction for safe out-of-distribution governance**. Even a well-estimated average or local effect does not by itself determine whether a memory should be abstracted, downweighted or forgotten. Memory effects may vary by task family, subject, time and tool version; a low-frequency safety constraint may have a near-zero average effect while carrying a high cost of erroneous removal; and an abstract rule learned from a narrow scope may be inappropriately inherited by an unseen entity or environment. Heterogeneous-effect estimation, invariance analysis, causal-model abstraction and data-fusion theory provide relevant concepts for conditional effects and transport boundaries [@WagerAthey2018CausalForest; @NieWager2021RLearner; @Peters2016InvariantPrediction; @BeckersHalpern2019AbstractingCausalModels; @BareinboimPearl2016DataFusion]. Agent-memory governance nevertheless lacks a unified decision interface that combines abstraction support, applicability scope, effect heterogeneity, cross-environment stability, estimation uncertainty, asymmetric forgetting costs and reversible state transitions while retaining access to the original evidence.

We address these problems with an evidence-preserving framework for sequential causal memory governance. Raw events are first written to an immutable evidence ledger. A decomposition operator constructs entity, attribute, condition, action, outcome, time and constraint candidates with exact source spans; a separate abstraction operator proposes conditional rules only with explicit support sets, versions and scopes. These outputs remain hypotheses rather than causal facts. During agent execution, the system atomically logs the pre-treatment history, candidate set, behaviour-policy probability, actual exposure, adoption evidence, action, outcome and subsequent state. Safe replay environments permit low-probability masking, version replacement, cluster-level intervention and rule–evidence comparisons. Static doubly robust estimators diagnose proximal exposure effects, whereas marginal structural models and sequential doubly robust off-policy evaluation estimate longer-horizon governance value. A risk-sensitive state machine then selects among reinforcement, retention, downweighting, archiving, isolation and restoration; physical deletion remains governed by independent withdrawal, permission and retention policies.

This study makes four bounded contributions. First, it formulates Agent Memory forgetting as a sequential treatment-and-policy problem over evidence-supported component bundles rather than as a single importance score. Second, it separates evidence-grounded decomposition, scope-constrained abstraction and causal validation, preventing generated explanations or compressed rules from acquiring causal status without intervention evidence. Third, it specifies an auditable logging, estimation and reversible-governance protocol that exposes overlap violations, uncertainty and asymmetric error costs. Fourth, it defines a staged evaluation programme combining causal-ground-truth simulators, a manually auditable semantic-decomposition gate and public long-term-memory benchmarks. The final manuscript will claim end-to-end or state-of-the-art gains only if the same implementation improves the preregistered utility–risk–cost frontier against fixed BM25, dense/hybrid retrieval and reproducible forgetting baselines across multiple seeds.

## Reviewer-facing gap formulations

### Gap 1 — causal addressability and sequential effect identification

> Existing Agent Memory forgetting methods use recency, frequency, semantic relevance, task feedback and decision distortion, but they commonly govern trajectory fragments, summaries or experiences whose internal conditions are not separately addressable; the opportunities to observe these units are also generated by the current retrieval and governance policy. Existing causal-inference, causal-representation and off-policy-evaluation tools have not yet been integrated into an auditable Agent Memory problem that links evidence-grounded decomposition, factor exposure, adoption, action, outcome and state transition over time.

### Gap 2 — scope-constrained abstraction and evidence-preserving governance

> Historical average relevance or a local causal effect is insufficient for safe forgetting under distribution shift. Agent Memory governance still lacks a unified mechanism that combines evidence-supported abstraction, explicit applicability scope, heterogeneous effects, cross-environment stability, uncertainty, asymmetric false-forgetting costs and reversible lifecycle actions without discarding the source evidence.

## Section outline

1. Agent memory creates both long-horizon capability and a lifecycle-governance problem.
2. Existing trajectory proxies are useful and efficient, but their representation unit remains surface-bound.
3. Gap 1: endogenous exposure and non-addressable units obstruct causal attribution.
4. Gap 2: local effects do not determine safe abstraction or out-of-distribution governance.
5. Method overview: evidence ledger, decomposition–abstraction interface, sequential logging and estimation, reversible state machine.
6. Bounded contributions and the condition under which performance claims may be added.

## Claim–evidence map

| Claim | Current evidence | Status |
| --- | --- | --- |
| Trajectory-derived exposure can confound success-based memory value. | Causal theory; 50-seed static calibration recovered ATE with adjusted/DR estimators while naive estimates were strongly biased. | Supported in controlled settings; real-agent overlap remains unverified. |
| Evidence-grounded decomposition and abstraction can improve surface-shift generalization when representation quality is high. | Thirty-seed surface-transformation simulator and decomposition-quality sweep. | Mechanistically supported; externally unverified. |
| Low-quality decomposition can erase the proposed advantage. | Accuracy and group-noise sensitivity; at high noise the proposed utility was not better than the item-level causal baseline. | Supported in controlled settings. |
| Sentence, keyword and local predicate–argument proxies are insufficient substitutes for semantic decomposition. | LongMemEval-S lexical and POS-v2 sidecar experiments over 470 questions and ten splits. | Supported for tested proxies. |
| BM25+dense RRF is a stronger public retrieval control than BM25 alone for multi-evidence coverage. | Ten-split LongMemEval-S retrieval experiment, Recall-all@5 0.8607 versus 0.8273. | Supported for the fixed MiniLM/256-token protocol. |
| The full framework improves public end-to-end utility or reaches SOTA. | No endpoint experiment with a Gate-A-qualified semantic parser and common reader is complete. | Needs evidence; deliberately excluded from the draft claim. |

## Assumptions or missing inputs

- No target venue or word limit has been selected; this draft uses a generic method-heavy introduction structure.
- The verified literature set may not exhaust concurrent or unpublished Agent Memory systems; “has not been unified” is bounded to the reviewed literature and common evaluation protocols.
- The manually auditable Gate A is annotation-ready but not yet double-annotated or adjudicated.
- Final result language, numerical gains and any SOTA statement must be added only after a fixed end-to-end protocol passes Gate A, Gate B and strong-baseline comparisons.

## 中文结构说明

- 第一段直接从 Agent Memory 的系统作用切入，没有从 LLM 历史或一般智能展开。
- 第二段先承认时间、频率、相关性与结果反馈的工程价值，再限定其表示粒度问题，避免把相关工作写成“完全无效”。
- 第三、四段分别收口到识别缺口和治理缺口，对应论文的两个方法模块。
- 第五段只概览机制，不混入尚未完成的 benchmark 数字。
- 第六段使用有边界的贡献表述，并明确 SOTA 主张的实验前置条件。

## Related documents

[[01-核心研究问题与具体设想|Chinese problem formulation and system architecture]]、[[03-因果推断驱动的Agent Memory遗忘框架论文方案|Method and experiment blueprint]]、[[05-解构抽象因果遗忘框架阶段性可行性判断|Conditional-GO assessment]]、[[experiments/semantic_gate_a/LongMemEval语义解构Gate-A标注规范|Semantic Gate A]]
