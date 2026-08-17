---
type: manuscript-section
section: introduction
language: English
status: final
paper_type: algorithmic
target_venue: ICLR 2027 (author-year/natbib style)
design_status: defined-separately-after-introduction
notes: 当前唯一 Introduction 标准稿；按 2026-08-07 老师要求视为可定稿。本文只评估现有工作与 Research Gaps；完整方法与实验设计由杂项-草稿与实验记录中的 00 号规范稿和 02 号逐环节执行方案另行定义。
---

# Introduction

Agent Memory gives long-horizon agents a persistent external state in which task state, user constraints, environmental observations and reusable experience can remain available across interactions and changing conditions (Packer et al., 2023; Park et al., 2023). Unlike a transient context window, this state is repeatedly written, retrieved, updated and exposed to later decisions. Its accumulation therefore creates a governance problem: redundant descriptions, obsolete versions and conflicting evidence enlarge the retrieval space, increase inference cost and may continue to influence behavior after the conditions that produced them have changed. The central question is not how to store more history, but how to regulate the future accessibility and influence of information that has already entered memory. In this setting, forgetting includes changes in accessibility, priority or representation, rather than only physical deletion.

Existing approaches to memory governance use several complementary signals. MemoryBank combines temporal and importance cues for long-term retention; FadeMem applies differential decay from semantic relevance, access frequency and temporal patterns; Oblivion treats forgetting as a decay of accessibility modulated by uncertainty and response contribution; Memory Worth updates trust and suppression from success–failure co-occurrence; and DeMem frames compression around preserving distinctions that affect downstream decisions (Zhong et al., 2024; Wei et al., 2026; Rana et al., 2026; Simsek, 2026; Zou et al., 2026). Related systems improve memory formation, organization, revision and procedural refinement through novelty gates, structured links, evidence-aware consolidation and utility-based experience distillation (Wang et al., 2026; Cao et al., 2026). Together, these studies show that effective memory management requires more than a fixed recency rule and can reduce interference, storage cost or obsolete access. They also reveal a shared dependency: many governance signals are learned from the agent's own interaction trajectory, in which memory exposure and the resulting task outcome are jointly shaped by task conditions, retrieval decisions and the current policy.

Recent preprints have introduced explicit causal or counterfactual analyses into agent memory. Causal Memory Intervention (CMI) evaluates candidate memories under controlled perturbations for query-time selection; MemAudit uses replay-based attribution to diagnose memories associated with harmful behavior; ActMem builds a causal–semantic memory graph for reasoning about implicit constraints and conflicts; and Trivium studies persistent causal evidence and explicit probing in long-horizon causal-memory controllers (Srivastava, 2026; Tan et al., 2026; Zhang et al., 2026; Chang, 2026). These contributions rule out an overly broad claim that agent memory lacks causal analysis: local causal usefulness can be tested, harmful memories can be audited retrospectively, structured causal relations can support memory-dependent action, and causal-model revision can be studied across repeated episodes. GateMem further demonstrates that utility, access control and active forgetting remain difficult to satisfy simultaneously in multi-principal shared-memory settings (Ren et al., 2026).

The main unresolved issue is therefore not whether a causal effect can be estimated for a particular query or episode, but whether a memory's apparent value can be separated from the trajectory conditions under which it was exposed and followed by success. Memory Worth explicitly characterizes its success signal as associational rather than causal (Simsek, 2026). An irrelevant memory may therefore be reinforced because it accompanies easy successes, while a protective memory may be undervalued when it reduces loss without reversing a binary outcome. Candidate generation, retrieval, workspace composition, prompt position, model and tool versions, task difficulty and jointly exposed memories can all affect both whether a memory is visible and what the agent does next. We refer to this failure mode as trajectory-conditioned associational overfitting: lifecycle states adapt to policy- and task-dependent co-occurrence instead of to a memory component's transferable contribution. Retention, suppression or archiving then changes future candidate streams, making the problem sequential as well as endogenous. **Research** **Gap 1 is the lack of an auditable, lifecycle-level formulation that attributes downstream action or outcome changes to memory components under policy-generated, time-varying exposure, rather than to their raw co-occurrence with task results.**

A related governance gap follows even when local attribution is available. An estimated effect is conditional on a task distribution, subject, time period, tool configuration and exposure policy; it does not by itself determine whether a memory remains valid after those conditions shift. Average utility also fails to encode the asymmetric cost of suppressing a rare but safety-critical constraint. Existing work offers useful pieces—decay, auditing, access control, compression and causal intervention—but does not provide a unified decision formulation that maps conditional evidence and uncertainty to reversible lifecycle actions under scope change, distribution shift and asymmetric forgetting risk. This does not imply that associative information is uniformly expendable: repeated, independent and high-quality evidence may make an association highly useful, just as a nominally causal relation may be unsafe outside its scope. **Research Gap 2 is thus the absence of a common, risk-sensitive account of how evidence about memory-dependent effects should govern accessibility over time while preserving provenance and recovery paths.**

Taken together, the literature positions the open problem at the intersection of causal credit assignment and selective memory governance. A satisfactory account must distinguish transferable contributions from trajectory-specific co-occurrence, make the relevant exposure and scope conditions auditable, and explain how uncertainty and asymmetric error costs should affect the future accessibility of stored memory. Establishing such an account is necessary before claims about causal memory value can be translated into reliable forgetting, decay or retention decisions.

---

## References

Cao, Z., Deng, J., Yu, L., Zhou, W., Liu, Z., Ding, B., & Zhao, H. (2026). *Remember me, refine me: A dynamic procedural memory framework for experience-driven agent evolution*. Findings of ACL 2026.

Chang, E. Y. (2026). *Trivium: Temporal regret as a first-class objective for causal-memory controllers*. arXiv:2606.04421.

Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). *MemGPT: Towards LLMs as operating systems*. arXiv:2310.08560.

Rana, A., Hung, C.-C., Sun, Q., Kunkel, J. M., & Lawrence, C. (2026). *Oblivion: Self-adaptive agentic memory control through decay-driven activation*. arXiv:2604.00131.

Park, J. S., O'Brien, J., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). *Generative agents: Interactive simulacra of human behavior*. Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology.

Ren, Z., Yang, Y., Chen, Y., Zhao, Z., Fu, B., Shu, Z., Zhang, B., Xu, Y., Guo, D., & Yan, S. (2026). *GateMem: Benchmarking memory governance in multi-principal shared-memory agents*. arXiv:2606.18829.

Wang, S., et al. (2026). *SAGE: A novelty gate for efficient memory evolution in agentic LLMs*. arXiv:2605.30711.

Simsek, B. (2026). *When to forget: A memory governance primitive*. arXiv:2604.12007.

Srivastava, S. S. (2026). *Causal intervention-based memory selection for long-horizon LLM agents*. arXiv:2605.17641.

Tan, Z., et al. (2026). *MemAudit: Post-hoc auditing of poisoned agent memory via causal attribution and structural anomaly detection*. arXiv:2605.23723.

Wei, L., Peng, X., Dong, X., Xie, N., & Wang, B. (2026). *FadeMem: Biologically-inspired forgetting for efficient agent memory*. arXiv:2601.18642.

Zhang, X., Sun, Z., Yang, C., Jin, Y., Zhang, Y., & Hu, W. (2026). *ActMem: Bridging the gap between memory retrieval and reasoning in LLM agents*. arXiv:2603.00026.

Zhong, W., Guo, L., Gao, Q., Ye, H., & Wang, Y. (2024). *MemoryBank: Enhancing large language models with long-term memory*. Proceedings of the AAAI Conference on Artificial Intelligence, 38.

Zou, M., Guo, Z., Liang, L., Wang, Z., Wang, Q., Wen, Q., King, I., Qu, L., & Xu, Z. (2026). *Remember the decision, not the description: A rate-distortion framework for agent memory*. arXiv:2605.10870.

---



