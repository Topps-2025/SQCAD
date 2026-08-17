---
type: manuscript-section
section: introduction
language: English
status: revised-20260811
paper_type: algorithmic
target_venue: ICLR 2027 (author-year/natbib style)
design_status: defined-separately-after-introduction
notes: This revision narrows Research Gap 1 to lifecycle effect identification under policy-dependent sequential exposure. It explicitly distinguishes query-local intervention effects from persistent-access policy effects and does not claim that causal memory analysis or evidence governance is absent from prior work. The accompanying coverage audit is in 08-Gap1覆盖审计与框架设计重点-20260811.md.
---

# Introduction

Agent Memory gives long-horizon agents a persistent external state in which task state, user constraints, environmental observations and reusable experience can remain available across interactions and changing conditions (Packer et al., 2023; Park et al., 2023). Unlike a transient context window, this state is repeatedly written, retrieved, updated and exposed to later decisions. Its accumulation therefore creates a governance problem: redundant descriptions, obsolete versions and conflicting evidence enlarge the retrieval space, increase inference cost and may continue to influence behaviour after the conditions that produced them have changed. The central question is not how to store more history, but how to regulate the future accessibility and influence of information that has already entered memory. In this setting, forgetting includes changes in accessibility, priority or representation, rather than only physical deletion.

Existing memory systems use several kinds of evidence to govern retention and access. MemoryBank combines temporal and importance cues; FadeMem and Oblivion implement accessibility decay; Memory Worth updates a memory score from success–failure co-occurrence; and DeMem compresses memories while preserving distinctions that affect downstream decisions (Zhong et al., 2024; Wei et al., 2026; Rana et al., 2026; Simsek, 2026; Zou et al., 2026). Other systems regulate memory formation, provenance, organization, revision or procedural refinement through novelty gates, dependency-aware support, structured links and experience distillation (Wang et al., 2026; Cao et al., 2026; Qi et al., 2026). These studies establish that memory governance is a substantive problem rather than a fixed recency heuristic. They also expose a common statistical difficulty: when a system learns from outcomes observed after its own retrieval and exposure decisions, the resulting signal is conditional on the policy that generated the data.

Recent work has also moved beyond purely associative signals, but it addresses different estimands. Causal Memory Intervention (CMI) forces a candidate memory into or out of a fixed query context and measures the change in the current answer; MemAudit uses replay-based attribution to diagnose memories associated with harmful behaviour; ActMem uses causal–semantic structure to support memory-dependent reasoning; and Trivium studies explicit probes, persistent causal logs and cross-episode revision of a causal model (Srivastava, 2026; Tan et al., 2026; Zhang et al., 2026; Chang, 2026). GovMem independently highlights that repeated trace observations can be copied, prompt-correlated, stale or out of scope, and routes write proposals to promote, reject or review using provenance and dependency evidence (Qi et al., 2026). GateMem further shows that utility, access control and active forgetting remain difficult to satisfy simultaneously in shared-memory agents (Ren et al., 2026). These contributions rule out two overly broad claims: agent memory does not lack causal analysis, and memory governance does not lack provenance- or scope-aware safety mechanisms.

The unresolved problem lies in the level of the intervention. A query-local effect can be written as the change in an answer when a candidate memory is inserted into a fixed prompt. That quantity can be useful for the current task, but it is not the same as the value of changing the memory's persistent accessibility. A persistent action such as protect, downweight, isolate, archive or restore changes which candidates can be exposed in later tasks. It can therefore alter the future candidate stream, workspace composition, co-exposed memories, agent actions, task outcomes and the observations available for subsequent updates. The policy both acts on the data-generating process and is later updated from that process. Historical co-occurrence is consequently insufficient, while a local intervention estimate does not by itself identify the value of a lifecycle policy intervention. This is a sequential policy-feedback problem, not only a distinction between correlation and causation. **Research Gap 1 is the lack of an auditable lifecycle-level formulation for identifying the effect of persistent memory-access interventions under policy-dependent, time-varying exposure and feedback, with explicit treatment definitions, overlap conditions, co-memory interference and outcome-measurement assumptions.**

A second gap begins after an effect has been identified. Any estimate is conditional on a task distribution, subject, time period, tool configuration, model version and exposure policy. It does not automatically transport to a shifted scope, and average utility does not encode the asymmetric cost of suppressing a rare but safety-critical constraint. Prior work provides important pieces, including decay, abstention or review, access control, provenance, intervention and compression, but the remaining design question is how qualified evidence and uncertainty should authorize reversible lifecycle actions while preserving source records and recovery paths. **Research Gap 2 is therefore the absence of a risk-sensitive decision interface that maps scope-conditional evidence to reversible access actions without conflating source evidence, relation belief and current access policy.**

SQCAD studies these two gaps as a single lifecycle problem. It separates immutable evidence, scope- and version-specific qualification, and competitive access under a fixed workspace budget. Associative signals propose candidates and provide bounded low-risk fallback access; they do not receive authority to change persistent access states. Persistent governance changes require auditable qualification, and unresolved evidence remains an abstaining permission state rather than a negative value estimate. The framework records candidate generation, exposure, adoption, action, outcome and cost so that lifecycle effects can be tested under chronological splits, scope shifts and randomized micro-interventions. The intended contribution is not a new causal estimator, decay curve or memory representation in isolation, but a falsifiable protocol and governance interface for deciding when evidence has earned permission to change future memory accessibility.

The paper therefore makes a deliberately bounded claim. It does not claim that causal memory selection, evidence governance, accessibility decay, scope awareness or recoverability are individually new. It asks whether persistent-access interventions can be defined and evaluated without treating policy-generated success as transferable memory value, and whether qualification-gated actions reduce false forgetting under explicit asymmetric costs. Controlled mechanism experiments are used to test this permission rule and its failure modes; public end-to-end superiority remains an empirical question that requires a shared reader, candidate stream, model, evaluator, budget and chronological protocol.

## References

Cao, Z., Deng, J., Yu, L., Zhou, W., Liu, Z., Ding, B., & Zhao, H. (2026). *Remember me, refine me: A dynamic procedural memory framework for experience-driven agent evolution*. Findings of ACL 2026.

Chang, E. Y. (2026). *Trivium: Temporal regret as a first-class objective for causal-memory controllers*. arXiv:2606.04421.

Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). *MemGPT: Towards LLMs as operating systems*. arXiv:2310.08560.

Park, J. S., O'Brien, J., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). *Generative agents: Interactive simulacra of human behavior*. Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology.

Qi, Y., Xu, X., & Li, Y. (2026). *When not to write memory: Governing false promotion from correlated agent traces*. arXiv:2607.02579.

Rana, A., Hung, C.-C., Sun, Q., Kunkel, J. M., & Lawrence, C. (2026). *Oblivion: Self-adaptive agentic memory control through decay-driven activation*. arXiv:2604.00131.

Ren, Z., Yang, Y., Chen, Y., Zhao, Z., Fu, B., Shu, Z., Zhang, B., Xu, Y., Guo, D., & Yan, S. (2026). *GateMem: Benchmarking memory governance in multi-principal shared-memory agents*. arXiv:2606.18829.

Simsek, B. (2026). *When to forget: A memory governance primitive*. arXiv:2604.12007.

Srivastava, S. S. (2026). *Causal intervention-based memory selection for long-horizon LLM agents*. arXiv:2605.17641.

Tan, Z., et al. (2026). *MemAudit: Post-hoc auditing of poisoned agent memory via causal attribution and structural anomaly detection*. arXiv:2605.23723.

Wang, S., et al. (2026). *SAGE: A novelty gate for efficient memory evolution in agentic LLMs*. arXiv:2605.30711.

Wei, L., Peng, X., Dong, X., Xie, N., & Wang, B. (2026). *FadeMem: Biologically-inspired forgetting for efficient agent memory*. arXiv:2601.18642.

Zhang, X., Sun, Z., Yang, C., Jin, Y., Zhang, Y., & Hu, W. (2026). *ActMem: Bridging the gap between memory retrieval and reasoning in LLM agents*. arXiv:2603.00026.

Zhong, W., Guo, L., Gao, Q., Ye, H., & Wang, Y. (2024). *MemoryBank: Enhancing large language models with long-term memory*. Proceedings of the AAAI Conference on Artificial Intelligence, 38.

Zou, M., Guo, Z., Liang, L., Wang, Z., Wang, Q., Wen, Q., King, I., Qu, L., & Xu, Z. (2026). *Remember the decision, not the description: A rate-distortion framework for agent memory*. arXiv:2605.10870.

---
