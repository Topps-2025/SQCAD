---
type: manuscript-section
section: method
language: English
status: evidence-bounded-draft
paper_type: algorithmic
target_venue: generic
---

# Method

## 1. Problem formulation

### 1.1 Sequential Agent Memory process

We consider an agent that interacts with an environment for $T$ decision steps. At step $t$, the pre-treatment history $H_t$ contains the task and environment state, previous observations, actions and outcomes, current memory states, candidate-generation and retrieval configuration, model and tool versions, resource budgets and all variables recorded before the memory decision. A raw event $E_t$ is appended to an immutable evidence ledger. The persistent memory store supplies a candidate set $\mathcal C_t$, from which a workspace composer constructs the budget-constrained runtime context.

We distinguish the following variables:

- $G_t$: a governance action, such as reinforce, keep, downweight, archive, isolate or restore;
- $Z_t$: the vector of memory-component exposures in the agent workspace;
- $U_t$: observable evidence that the agent adopted or used an exposed component;
- $A_t$: the agent's plan, tool call or answer action;
- $Y_t$: proximal outcomes, including continuous reward or loss, constraint violations, action changes and resource cost;
- $R_T=\sum_{t=1}^{T}\gamma^{t-1}r_t$: episode-level discounted utility.

We treat $B_t=(G_t,Z_t)$ as the time-varying treatment. The behaviour policy $\pi_b(B_t\mid H_t)$ generates the logged trajectory, whereas an evaluation policy $\pi_e(B_t\mid H_t)$ specifies an alternative memory-governance strategy. This formulation covers factual, episodic, procedural and constraint memories without requiring separate physical stores. Memory type, subject, time, permission, version and lifecycle state are orthogonal metadata; the physical backend may use a unified table or specialised services.

### 1.2 Causal estimands

For an evidence-supported component bundle $c_k$, the proximal exposure effect compares visibility and masking while holding the pre-treatment history and workspace policy fixed:

$$
\tau_{t,k}(h)=
\mathbb E\!\left[
Y_t\left(Z_{t,k}=1\right)-Y_t\left(Z_{t,k}=0\right)
\mid H_t=h
\right].
$$

This estimand asks whether making a component and its required evidence visible changes the current plan, tool use, answer or loss. It is conditional on the candidate generator, context composer and treatment version; it is not interpreted as a permanent intrinsic value of the memory.

The primary long-horizon estimand is the value of a governance policy:

$$
V(\pi_e)=\mathbb E_{\pi_e}\!\left[
\sum_{t=1}^{T}\gamma^{t-1}
\left(r_t-\lambda c_t-\eta q_t\right)
\right],
$$

where $c_t$ includes storage, prompt-token, latency and model-call costs, and $q_t$ includes false forgetting, scope violations and irrecoverability risk. Proximal conditional effects are diagnostic inputs to governance; the main claim concerns policy value under a fixed resource and safety protocol.

## 2. System overview

The framework is inserted into a complete Agent Memory workflow rather than replacing the writer, retriever or agent. Figure 1 contains a data plane and a governance plane. On the data plane, user inputs, environment observations and tool results enter an immutable event ledger; candidate memories are written, indexed, retrieved, filtered and composed into a finite workspace; the agent then plans, invokes tools or answers, and an evaluator records outcomes and costs. On the governance plane, the framework constructs addressable component candidates, logs their sequential exposure and use, estimates conditional and policy effects, and changes future accessibility through reversible state transitions.

~~~mermaid
flowchart TB
  O["User input / observation / tool result"] --> EL["Immutable evidence ledger"]
  EL --> D["Evidence-grounded decomposition"]
  D --> X["Scope-constrained rule candidates"]
  EL --> W["Writer: deduplication, conflict and version links"]
  D --> W
  X --> W
  W --> S["Configurable persistent memory and archives"]
  S --> I["Sparse, dense, temporal and scope indices"]
  Q["Current task state"] --> R["Retrieval router and eligibility filter"]
  I --> R
  R --> C["Budgeted workspace composer"]
  Q --> C
  C --> A["Planning / tool-use / answer agent"]
  A --> Y["Outcome, constraint and resource evaluation"]
  Y --> L["Atomic sequential decision log"]
  L --> E["Static DR, MSM and sequential DR-OPE"]
  E --> H["Heterogeneity, stability and uncertainty"]
  H --> G["Risk-sensitive reversible governance"]
  G -. "state transition" .-> S
  G -. "safe intervention" .-> C
  D -. "factor provenance" .-> L
  X -. "rule support and scope" .-> L
~~~

**Figure 1 | Evidence-preserving sequential causal governance within a general Agent Memory workflow.** The evidence ledger, writer, persistent store, retrieval router, workspace, agent and evaluator form the reusable system substrate. Evidence, factors and rules are logical lineage objects rather than mandatory physical layers. The proposed contribution is restricted to the representation interface, causal logging and intervention protocol, effect estimation and reversible governance plane.

## 3. Evidence-preserving memory representation

Although decomposition and abstraction are implemented as separate operators, we treat them as a joint representational capability:

$$
\mathcal R_{\phi,\psi}(E_{1:t},\mathcal L_{1:t-1})
=
\mathcal A_\psi\!\left(
\mathcal D_\phi(E_{1:t}),\mathcal L_{1:t-1}
\right)
=
\left(\mathcal C_t,\mathcal P_t,\mathcal Q_t\right).
$$

Here, $\mathcal C_t$ denotes candidate component bundles, $\mathcal P_t$ their evidence lineage and $\mathcal Q_t$ their scope, version and uncertainty metadata. The two operators are complementary rather than interchangeable. Decomposition without abstraction creates addressable but context-local candidates; abstraction without decomposition creates general statements that cannot be traced or manipulated as treatments. Their composition creates transferable but still falsifiable treatment candidates. Causal estimation remains a downstream qualification stage and does not follow from either operator. We therefore isolate the interaction through raw-trajectory, decomposition-only, unsupported-rule and evidence-supported decomposition–abstraction controls.

### 3.1 Evidence-grounded decomposition

Trajectory fragments are unsuitable treatment units when a useful condition is entangled with names, wording, time and co-occurring events. We therefore define a decomposition operator

$$
\mathcal D_{\phi}(E_t)=\left(F_t,\mathcal R_t,P_t,\rho_t\right),
$$

where $F_t=\{f_k\}$ contains entity, attribute, condition, action, outcome, preference, time, constraint, tool and version candidates; $\mathcal R_t$ contains typed relations; $P_t$ maps every candidate to exact source spans or tool outputs; and $\rho_t$ records the extractor version and confidence. A factor may become a treatment unit only if it is traceable to evidence, operationally maskable or replaceable, and accompanied by explicit subject, task and temporal boundaries. An extraction without these properties remains a retrieval feature and cannot authorise a strong governance action.

Decomposition provides interventional addressability, not causal discovery. A generated explanation, attention weight or predicate–argument tuple is stored as a candidate measurement. Its causal status is assessed only after a treatment definition, overlap diagnostics and intervention-based or explicitly assumption-dependent estimation. This separation follows the distinction between a learned representation and a verified causal variable emphasised in causal representation learning [@Scholkopf2021CausalRepresentation].

### 3.2 Scope-constrained abstraction

The abstraction operator groups candidates only when their relation template, support evidence and applicability boundaries are compatible:

$$
\mathcal A_{\psi}\!\left(
\{f_k,\mathcal R_k,P_k\}_{k\in\mathcal I},\mathcal L
\right)
=\left(r_j,\mathcal S_j,\Gamma_j,\nu_j,\omega_j\right).
$$

Here, $r_j$ is a conditional rule candidate, $\mathcal S_j$ is the non-discardable support set, $\Gamma_j$ specifies subject, task, time, tool-version and permission scope, $\nu_j$ is the rule version, and $\omega_j$ records support count, conflicts and uncertainty. The rule takes the scoped form $X\rightarrow Y\mid\Gamma_j$, not an unconditional $X\rightarrow Y$. Scope mismatch, counterevidence or cross-environment sign conflict prevents promotion. This design uses causal-model abstraction as a guide to cross-level consistency without claiming that a language model has recovered the true structural model [@BeckersHalpern2019AbstractingCausalModels].

The minimum governance unit is an evidence-supported component bundle

$$
c_k=\left(x_k,\mathcal S_k,\Gamma_k,\rho_k\right),
\qquad x_k\in F\cup\{r_j\}.
$$

Raw evidence remains the primary index and recovery path. Factor and rule representations form a sidecar index that may expand candidates, enforce scope eligibility or provide governance features. A rule hit can re-rank or retrieve its supporting evidence, but cannot replace the evidence before semantic fidelity and task contribution have been validated. This constraint is tested through raw-evidence, relation-only, rule-only, raw-plus-sidecar and rule-plus-evidence ablations.

### 3.3 Representation qualification

A component progresses through four statuses:

$$
\text{proposed}
\rightarrow\text{auditable}
\rightarrow\text{estimable}
\rightarrow\text{governable}.
$$

The first transition requires complete provenance and scope; the second requires a consistent treatment definition, logged propensity and adequate overlap; the third requires effect, stability, uncertainty and risk diagnostics. Passing a semantic annotation gate does not by itself pass the causal-identification gate, and a non-zero causal estimate cannot override scope, permission or retention constraints.

### 3.4 Joint-capability error propagation and admission

The two operators are jointly necessary also because abstraction propagates decomposition error. Let $\epsilon_D$ denote errors in factor boundaries, types, provenance or relations, and let $\epsilon_A$ denote erroneous merges, omitted scopes or over-generalised rules. We use the following design audit rather than an unqualified statistical bound:

$$
\epsilon_R \lesssim \epsilon_A(\mathcal D_\phi(E),\Gamma,P)+L_A\epsilon_D,
$$

where $L_A$ measures abstraction sensitivity to candidate perturbations. A rule candidate is admitted only when provenance, scope, independent support and conflict checks pass:

$$
\operatorname{Admit}(r_j)=\mathbf 1\{\mathrm{Prov}_j\geq\theta_P,\;\mathrm{Scope}_j\geq\theta_\Gamma,\;\mathrm{Support}_j\geq\theta_S,\;\mathrm{Conflict}_j\leq\theta_C\}.
$$

Candidates that fail remain proposed or fall back to raw evidence. Thus, decomposition--abstraction enters the causal architecture as an auditable candidate interface for treatment definition and intervention addressability, rather than as a mandatory cognitive layer or an implicit causal-discovery module.

## 4. Sequential logging and safe interventions

### 4.1 Atomic decision log

Every decision is recorded under a unique decision identifier. The transaction stores: (i) $H_t$ before treatment; (ii) evidence–factor–rule lineage and extractor versions; (iii) the candidate-generation process and candidate probabilities when stochastic; (iv) the behaviour-policy version, realised $B_t$ and $\pi_b(B_t\mid H_t)$; (v) workspace position, token count and jointly exposed components; (vi) adoption diagnostics, plan, tool call or answer; (vii) proximal and terminal outcomes, evaluator version and resource cost; and (viii) $H_{t+1}$ and the subsequent lifecycle state. The propensity is recorded by the executing policy when the action is sampled. A post-hoc exposure classifier is not treated as a known propensity.

### 4.2 Intervention family

Exploration is restricted to simulators, deterministic replay tasks and automatically scored low-risk sandboxes. We use four principal interventions:

1. **Component-bundle masking:** compare exposure and masking while fixing candidates, prompt template, budget and controllable randomness.
2. **Version replacement:** switch between two legally exposable versions to estimate time and update effects.
3. **Cluster-level masking:** jointly treat near-duplicate or substitutable memories to reduce interference-induced underestimation.
4. **Rule–evidence comparison:** compare rule-plus-support, support-only and rule-only conditions under equal token and position budgets.

Selected pairs additionally receive a $2\times2$ factorial intervention to diagnose complementarity or suppression. Production-critical constraints, permissions and irreversible tool actions are placed on a non-explorable list. If a required treatment has no support in the logged policy, the framework reports a positivity violation and defaults to conservative retention or isolation rather than extrapolating a causal value.

### 4.3 Identification assumptions

The proximal and policy estimands require versioned treatment consistency, sequential exchangeability conditional on $H_t$, positivity over the target policy, measurable outcomes and a candidate or cluster definition that limits interference. These assumptions are diagnosed rather than asserted: we report overlap, effective sample size, weight tails, missingness, evaluator drift, treatment-version variation and sensitivity to cluster definitions. Environment transfer is evaluated by held-out time, task, subject or tool-version slices; stability on observed environments is not presented as a guarantee for arbitrary deployment environments.

## 5. Effect and policy-value estimation

### 5.1 Static doubly robust diagnostic

For a binary component exposure $Z_{t,k}$, outcome models $\mu_z(H_t)$ and propensity $e(H_t)$, the cross-fitted doubly robust pseudo-outcome is

$$
\widehat\phi_{t,k}=
\widehat\mu_1(H_t)-\widehat\mu_0(H_t)
+\frac{Z_{t,k}\left(Y_t-\widehat\mu_1(H_t)\right)}{\widehat e(H_t)}
-\frac{(1-Z_{t,k})\left(Y_t-\widehat\mu_0(H_t)\right)}{1-\widehat e(H_t)}.
$$

Cross-fitting limits overfitting bias from flexible nuisance models [@BangRobins2005DoublyRobust; @Chernozhukov2018DML]. Outcome regression, inverse propensity weighting and naive exposed–unexposed differences are retained as diagnostics and baselines. Propensity clipping is reported as a sensitivity analysis together with unclipped weight distributions; it does not convert unsupported histories into identifiable comparisons.

### 5.2 Time-varying treatment

Past exposure changes later agent state and therefore future retrieval. A marginal structural model uses stabilised weights

$$
SW_T=\prod_{t=1}^{T}
\frac{P(B_t\mid\bar B_{t-1},X_0)}{P(B_t\mid H_t)},
$$

where $X_0$ contains episode-start covariates [@Robins2000MSM]. We report the weight distribution, truncation level, effective sample size and horizon-stratified estimates. For target-policy evaluation, sequential doubly robust off-policy estimators combine stepwise importance ratios with action-value models [@JiangLi2016DROPE; @ThomasBrunskill2016OffPolicy]. An estimator is admitted to public experiments only after it recovers enumerated policy values and policy rankings in controlled environments.

### 5.3 Heterogeneity and stability

We estimate conditional effects across task difficulty, subject, component type, time and tool version using cross-fitted pseudo-outcomes with causal forests or R-learners [@WagerAthey2018CausalForest; @NieWager2021RLearner]. For component $i$ in an observed context $x$, the stability score is

$$
S_i(x)=
\operatorname{mean}_{e}\widehat\tau_i^{(e)}(x)
-\kappa\operatorname{sd}_{e}\widehat\tau_i^{(e)}(x)
-\xi\operatorname{SignConflict}_i(x).
$$

An abstraction candidate is eligible for activation only if its evidence coverage, independent support count and scope are adequate and its conditional effect is stable across predeclared observed environments. Invariance and data-fusion results motivate these diagnostics [@Peters2016InvariantPrediction; @BareinboimPearl2016DataFusion], but the score is an empirical robustness criterion rather than a proof of transportability.

## 6. Risk-sensitive reversible governance

To prevent an erroneous abstraction from propagating to every member of a mechanism group, we introduce a cross-granularity fallback gate. Let $q_i$ be calibrated representation confidence, $S_i^{\mathrm{group}}$ the stable group-level causal score and $S_i^{\mathrm{item}}$ the item-level score when estimable. The abstraction is eligible only when

$$
g_i=\mathbf 1\left\{q_i\geq\theta_q,\;
I_i=0\;\lor\;\left[
\operatorname{sign}(S_i^{\mathrm{group}})=\operatorname{sign}(S_i^{\mathrm{item}}),\;
\operatorname{LCB}(S_i^{\mathrm{item}})>\theta_{-}
\right]\right\},
$$

where $I_i$ indicates item-level estimability, and the governance score becomes $S_i^{\mathrm{gate}}=g_iS_i^{\mathrm{group}}+(1-g_i)S_i^{\mathrm{item}}$. If the item-level effect is not estimable because the memory is rare, the system does not treat a sentinel or a wide interval as evidence of harm; it instead relies on provenance, group support and the asymmetric false-forgetting cost. This gate converts representation quality into an explicit coverage--risk trade-off and is ablated into confidence-only, sign-consistency-only and negative-effect-veto variants.

The governance policy does not collapse all evidence into a scalar importance score. For each component and candidate action $g$, it evaluates

$$
Q_i(g\mid x)=
\widehat V_i(g\mid x)
-\lambda C_{\mathrm{resource}}(g)
-C_{\mathrm{FF}}(x)\,p_{\mathrm{FF}}(g\mid x)
-C_{\mathrm{FR}}(x)\,p_{\mathrm{FR}}(g\mid x)
-C_{\mathrm{scope}}\,p_{\mathrm{scope}}(g\mid x),
$$

and selects $g_i^*(x)=\arg\max_{g\in\mathcal G_i(x)}Q_i(g\mid x)$. Here, $\mathcal G_i(x)$ is the set of legally and statistically admissible actions, and $p_{\mathrm{FF}}$, $p_{\mathrm{FR}}$ and $p_{\mathrm{scope}}$ denote estimated false-forgetting, false-retention and scope-violation risks, respectively. The maximisation is subject to permission, withdrawal, retention-period and overlap constraints. $C_{\mathrm{FF}}$ may substantially exceed $C_{\mathrm{FR}}$ for rare safety rules, one-time exceptions and high-loss conditions. Uncertain estimates therefore lead to retention, light downweighting or additional data collection rather than deletion.

Stable positive components are reinforced or retained. Components that are beneficial only within an identifiable scope are isolated to that scope and restored when its trigger is present. Stable non-positive, high-cost components move through downweighted to archived, preserving a recovery pointer. Drift-induced sign reversal creates a version branch rather than overwriting history. Physical deletion is outside the learned policy and can be triggered only by independent withdrawal, permission, legal-retention or expiry rules; deletion must propagate to indices, caches and derived representations.

An optional structural-complexity regulariser may break ties between components with statistically indistinguishable value and legality. It is retained only if an ablation improves the utility–risk–cost frontier beyond an ordinary complexity penalty; it does not replace treatment definition or causal estimation.

## 7. Online algorithm

~~~text
for each episode:
    initialise immutable event ledger and memory state
    for t = 1 ... T:
        H_t <- snapshot(task, environment, memory states, budgets, versions)
        E_t <- append raw event and provenance
        F_t, relation_t, P_t <- decompose(E_t)       # candidates, not causal facts
        rules_t <- propose_scoped_rules(F_t, relation_t, prior evidence)
        C_t <- retrieve eligible evidence-supported component bundles
        B_t, p_t <- logging_policy(H_t, C_t, safety_constraints)
        atomically log(H_t, C_t, B_t, p_t)
        W_t <- compose_workspace(H_t, C_t, B_t)
        A_t, U_t <- agent_act(W_t)
        Y_t <- evaluate(A_t, environment, constraints, resource_cost)
        append(H_t, B_t, W_t, U_t, A_t, Y_t, H_{t+1})

periodically:
    audit provenance, overlap, missingness, evaluator drift and index consistency
    fit static DR diagnostics and sequential MSM / DR-OPE estimators
    estimate heterogeneous effects, stability and uncertainty
    qualify or demote rule candidates using evidence, scope and effect gates
    choose risk-sensitive reversible transitions
    apply transitions transactionally and retain rollback tokens
~~~

## 8. Implementation and reproducibility

The minimum implementation contains an immutable evidence table; versioned factor, rule and support-lineage tables; sparse, dense, temporal and scope indices; a budgeted workspace composer; an atomic decision log with behaviour propensities; an offline estimator service; and an outbox-backed state machine for active, downweighted, archived, isolated and restored states. Main-table eligibility filters remain authoritative while asynchronous indices update. Extractor, ontology, evaluator, prompt, model and tool versions are stored with every replayable decision.

Semantic representation quality is evaluated before full deployment. The preregistered Gate A uses 200 stratified LongMemEval-S evidence packets, with a 40-packet double-annotated pilot and a 160-packet main set. A parser passes only if bootstrap confidence bounds meet the preregistered factor, relation, provenance, scope, negation, temporal and update thresholds. Passing Gate A establishes representation fidelity, not causal validity. Gate B separately requires overlap and estimator calibration; public endpoint claims additionally require fixed-reader comparisons against BM25, dense/hybrid retrieval and reproducible forgetting baselines under common token, storage and latency budgets.

## 9. Assumptions and method boundaries

The framework governs external, addressable Agent Memory and does not implement unlearning of model parameters. Decomposition and abstraction outputs remain fallible measurements. Unobserved confounding, interference among many memories and limited overlap may prevent causal identification; in such regions the framework abstains from strong state changes. Cross-environment stability is empirical and does not guarantee arbitrary-domain transport. Finally, the full system architecture is an experimental substrate: unless separately ablated, the writer, retriever, workspace and reader are controls rather than claimed contributions.

## Section outline

1. Sequential task and estimands.
2. Complete Agent Memory workflow and contribution boundary.
3. Evidence-grounded decomposition, scope-constrained abstraction and representation qualification.
4. Atomic logging, safe interventions and identification assumptions.
5. Static and sequential estimation with heterogeneity and stability.
6. Risk-sensitive reversible governance.
7. Online algorithm, implementation and limitations.

## Claim–evidence map

| Method claim | Direct validation hook | Current status |
| --- | --- | --- |
| Component bundles are traceable and state transitions are reversible. | SQLite lineage/state prototype and unit tests. | Implemented at architectural-prototype level. |
| Behaviour propensity and decision tuples can be stored atomically. | Decision-log schema and round-trip/invalid-propensity tests. | Implemented at architectural-prototype level. |
| Static adjustment can correct observed exposure confounding. | Controlled ATE calibration over 50 seeds. | Supported for the specified synthetic DGP. |
| Sequential DR-OPE can rank governance policies. | Horizon-5 simulator over 20 seeds. | Supported for the specified finite DGP. |
| Abstraction can preserve rare critical mechanisms under surface shift. | Representation and group-noise simulators. | Conditional on sufficiently accurate decomposition. |
| A semantic parser satisfies the representation interface. | LongMemEval Gate A. | Not yet established; annotation-ready only. |
| The complete policy improves public endpoint utility or SOTA. | Fixed-reader LongMemEval/GoodAI-LTM/LoCoMo experiments. | Missing; excluded from current claims. |

## 中文结构说明

- 先定义处理、结果和两个 estimands，再介绍模块，避免“先画架构、后补问题定义”。
- 通用 Agent Memory 的写入、存储、检索、工作区、Agent、评估与反馈均保留；论文贡献只限定在表示接口、因果日志/估计与治理平面。
- 每个模块均包含动机、可复现机制和直接消融入口。
- “解构/抽象输出不是因果事实”“无 overlap 时保守退出”“物理删除不由算法授权”被写为方法约束，而非讨论中的软性提醒。
- Gate A、Gate B 与公开端点结果分开，防止用语义标注准确率替代因果识别或任务效用。

## Related documents

[[07-English-Introduction-Draft|English Introduction]]、[[09-English-Experiments-Draft|English Experiments]]、[[03-因果推断驱动的Agent Memory遗忘框架论文方案|Chinese method and experiment blueprint]]、[[01-核心研究问题与具体设想#5. 完整 Agent Memory 工程架构|Full engineering architecture]]、[[experiments/semantic_gate_a/LongMemEval语义解构Gate-A标注规范|Semantic Gate A]]

