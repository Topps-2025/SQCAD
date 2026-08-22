# 三条基础定理与架构无关总括定理的 prior-art challenge 与 novelty 边界

> **目的。** 本文档不是扩大 novelty claim，而是从严格 ICLR reviewer 的角度划清三条基础定理和架构无关总括定理中哪些是标准数学工具、哪些是 SQCAD 必须独立承担的 Agent-specific 命题。所有文献判断均以本轮实际读取的 PDF 为依据；2026 年工作目前按 arXiv 预印本处理。

## 1. 结论先行

SQCAD 不能把下列内容单独声称为理论创新：belief-MDP Bellman recursion、动作同时影响 transition/emission、belief value 的凸性、Blackwell dominance、Jensen information value、Bretagnolle--Huber、adaptive KL chain rule、Lambert-$W$ 优化，或 decision-centric memory compression。这些内容分别属于既有 POMDP、controlled sensing、active perception、信息论/序贯检验和 decision-centric memory compression 工具。

仍可守住的理论增量是一个组合命题：

> 对具有持久外部记忆的 Agent，`keep/archive` 授权会内生地改变未来 candidate regeneration、workspace competition、evidence censoring 与 priced recoverability。将这些机制放入同一个 lifecycle action-value contrast 后，可以证明当前 score 对持久授权充分的必要充分条件，并在该条件失败时给出同 score fiber 上的严格 regret 下界；在共同 state kernel 下，可以把 recoverability 的信息价值与 access/crowding 价值严格分账，而在一般 action-dependent kernel 下，可以用授权 transcript 的 KL 预算下界任何序贯策略的错误授权 regret。

这里的原创对象不是 Bellman、Doob--Dynkin、Blackwell、Bretagnolle--Huber、Lambert-$W$ 优化或一般 control homomorphism/lumpability 工具本身，而是：

1. Agent memory 的 persistent authorization kernel；
2. 完整 lifecycle contrast 的三项分解；
3. score-only governance 对该 contrast 的可测性门槛；
4. action-dependent censoring 违反门槛时的 Agent-specific regret witness；
5. recoverability 与 candidate/workspace access 的严格分账；
6. self-censoring Agent transcript 的 KL 信息预算与 lifecycle-regret 下界。
7. 在该 self-censoring transcript contract 上，把 channel-opening action 的 KL cap 与显式 probe/restore 成本合并为 priced recoverability frontier；新意只在 Agent 授权决定哪些分支携带信息及其成本，闭式优化工具本身是标准的；
8. 用 intervention-defined complete future-transcript kernel 把 external、retrieval、prompt、cache、adapter 和可干预 parameterized memory 统一成 future-null / lifecycle-complete / future-lossy 三分，并导出最粗 task-relative statistic $T_{\rm LC}^*$ 与近似误差 $\varepsilon_{\rm LC}$。

第 8 点使用的 measure separation、regular quotient factorization 和二点 minimax 都是标准工具。可辩护的新意是把它们组织成跨 memory implementation 的 Agent lifecycle 命题，并明确给出框架后续应估计的对象。最强合法表述是：

> Every intervention-defined LLM-Agent memory architecture is future-null, lifecycle-complete under the chosen score, or admits a task/cost witness with positive score-only regret, provided the declared uniformly bounded utility class separates the omitted signed future-transcript kernels.

这不是“所有 LLM Agent 在所有自然任务和固定成本下必然失败”。Midpoint shift 证明的是 cost-uniform score claim 失败；固定成本失败必须由未平移 contrasts 已异号来建立。

第二轮理论审计进一步区分两个量：一般 continuation difference

$$
\operatorname{VoR}^{\mathrm{cont}}_{t,K:A}=\gamma(C_t^K-C_t^A)
$$

包含 access/crowding 与 conditional information，因此不保证非负；只有共同 next-state kernel 下的

$$
\operatorname{VoR}^{\mathrm{info}}_{t,K:A}=\gamma(I_t^K-I_t^A)
$$

才由 Blackwell/Jensen 定号。Score 的 horizon-wide 充分性则由逐时刻 quotient reward factorization 与 action-dependent belief-kernel push-forward equality 保证；其 universal converse只针对所有有界终端效用上的 action-value factorization，不声称单个固定任务的最优动作能够识别完整 kernel。

## 2. 跨工作比较

来源等级：`A` 表示同行评议正式论文，`B` 表示 arXiv 预印本或本轮未核实正式发表状态。等级只表示当前可主张的证据强度，不表示论文质量。

| 工作 | 来源 | 数学/机制已覆盖 | 未覆盖或未在所读版本中建立 | 对 SQCAD 的约束 |
|---|---|---|---|---|
| DeMem (Zou et al., 2026) | B, arXiv:2605.10870 | decision-centric rate--distortion；exact forgetting boundary；固定预算下的 memory--distortion frontier；在线 refinement regret | 持久授权对后续 candidate/state/observation kernel 的内生改变；score sufficiency iff lifecycle-value measurability；recoverability 的 Blackwell 分账 | 不能再把“memory 应由 decision value 而非描述相似度决定”作为独占 novelty |
| Memory Worth (Simsek, 2026) | B, arXiv:2604.12007 | `Pr(success | memory retrieved)` 的在线估计与收敛；不确定性计数；failure modes | causal lifecycle value；反事实 keep/archive kernel；同 score fiber regret；recoverability option value | 必须准确称其为 association-based governance signal，而不是说它没有理论 |
| OBLIVION (Rana et al., 2026) | B, arXiv:2604.00131 | memory as control；uncertainty-gated read；decay accessibility；reactivation；read/write decoupling | belief-state lifecycle objective；score 充分性的充要条件；Blackwell/VoR 定理；action-value regret 下界 | “可恢复而非硬删除”已经不是新的工程叙事，SQCAD 必须给出可证伪的价值定理 |
| FadeMem (Wei et al., 2026) | B, arXiv:2601.18642 | relevance/frequency/recency 驱动的自适应衰减；双层 memory；冲突处理与融合 | belief-state control；action-dependent observation kernel；causal lifecycle objective；score insufficiency theorem | 可作为典型 heuristic score baseline，而不是理论稻草人 |
| Shi et al. (2025) | B, arXiv:2504.13288 | POMDP 中动作同时影响 dynamics 与 emission；联合 control/active perception；信息获取目标 | persistent Agent-memory authorization 的候选、工作区、证据与恢复结构 | 不能声称“首次让动作改变 transition 和 observation” |
| Satsangi et al. (2018) | A, *Autonomous Robots*, DOI:10.1007/s10514-017-9666-5 | active perception；belief reward；Bellman operator；belief value 凸性与近似界 | Agent memory lifecycle score 的充分性、删失 regret 和 recoverability 分账 | 凸性和 belief-space value 只能作为引理债务引用 |
| Krishnamurthy (2017) | B, arXiv:1701.00179 | controlled-sensing POMDP；Bellman structural results；Blackwell dominance；Jensen 路线；myopic policy bound | SQCAD 的 persistent-memory state contract、score-fiber impossibility 与 action-dependent recoverability ledger | Blackwell monotonicity不是本文原创，必须明确共同 state-kernel 条件 |

## 3. 最危险近邻：DeMem

### 3.1 它已经解决了什么

DeMem 明确反对仅按 relevance、salience 或 summary quality 组织 Agent memory，并将 memory quality 定义为压缩引起的可达 decision quality 损失。其摘要给出 exact forgetting boundary、memory--distortion frontier 和 online memory learner；引言还报告描述相似度对 evidence compatibility 的预测很弱。原文定位：PDF p.1，Abstract；PDF p.2，Introduction。

其 Theorem 1 允许同一 query fiber 内的 histories 共享 memory state，当且仅当存在共同的近似最优 action；随后定义 pairwise decision distance 和 cluster decision radius。原文定位：PDF p.5，§3.3--3.4。

### 3.2 为什么仍不等价于 SQCAD

DeMem 的理论入口是 memory-constrained contextual decision model，并在解析上实例化为 contextual bandit：每轮 context $X_t=(H_t,Q_t)$ 从固定分布独立抽取，memory encoder 将 context/history 压入固定数量的 runtime states，再由 policy 选择 downstream action。原文定位：PDF p.4，§3.1。

SQCAD 要研究的不是“给定 context 时应该保留哪些 decision distinctions”，而是当前持久动作本身如何改变未来可出现的 context、candidate pool、workspace occupancy、evidence experiment 和 restore channel。两者的差异必须写成 kernel 差异，而不能只写成叙事差异：

$$
\text{DeMem: }X_t\sim\mathcal D,\quad M_t=g(H_t),\quad A_t\sim\pi(\cdot\mid M_t,Q_t),
$$

$$
\text{SQCAD: }(s_{t+1},o_{t+1})\sim\mathsf K_{a_t}(\cdot\mid s_t,\theta),
\quad a_t\in\{K,A,P,D\}.
$$

若实验不能证明 $\mathsf K_K\neq\mathsf K_A$ 在真实 Agent trace 中存在，则 reviewer 可以合理地把 SQCAD 降格为 DeMem 的 sequential reformulation。因此 transition/observation audit 是 novelty claim 的组成部分，而不是普通补充实验。

## 4. Agent-memory 直接近邻

### 4.1 Memory Worth

Memory Worth 定义每条 memory 在被检索时与成功/失败共同出现的加权计数，并证明在 stationarity、minimum exploration、conditional independence 和 minimum weight 等条件下收敛到 $p_+(m)=\Pr(Y=1\mid m\in M_t)$。作者明确声明该量是 associational 而非 causal。原文定位：PDF p.2，Abstract；PDF p.4，§3；PDF p.5，Theorem 4.1。

该论文还实证展示 co-retrieval hitchhiker pathology，因此 SQCAD 不应只重复“association 不等于 causation”。需要推进到更强结论：即使 association score 被无偏估计，只要同一 score fiber 内的 future-kernel gap 改变，score-only rule 仍不能统一最优，并承担严格正 regret。

### 4.2 OBLIVION

OBLIVION 将 forgetting 表述为 accessibility decay 而不是 hard deletion，并以 read/write decoupling、uncertainty-gated access、reinforcement 和 reactivation 组织 Agent memory control。原文定位：PDF p.1，Abstract；PDF p.2，Introduction；PDF p.4，§2.3--2.4。

因此“archive 后仍可恢复”本身不是足够 novelty。SQCAD 必须证明恢复通道何时有正 option value、何时不足以推翻 crowding/storage cost，以及为什么该信息项不能与 candidate access 项混写。

### 4.3 FadeMem

FadeMem 以 semantic relevance、access frequency 和 recency 形成 importance score，并据此决定双层 memory 的提升、降级和衰减；冲突关系由 LLM 分类并触发合并或抑制。原文定位：PDF p.1，Abstract；PDF p.2，§2.1--2.2；PDF p.3，§2.3--2.4。

它适合作为定理 2 的 empirical target：在相近 score bins 内进行 forced keep/archive paired rollout，测量真实 lifecycle contrast 是否异质。不能未经实验就声称它必然失败；定理只说明它若不能编码完整 contrast，就不具备统一充分性。

## 5. 一般 POMDP 理论债务

Shi et al. 已明确建模动作同时影响 system dynamics 与 emission function。原文定位：PDF p.1，Abstract。Satsangi et al. 已在 active perception POMDP 中使用 belief reward、Bellman operator 和 convex belief value，并给出相应近似界。原文定位：PDF p.2--4，§1；PDF p.23--24，§10.4。Krishnamurthy 已系统使用 Blackwell dominance、convexity/Jensen 和 Bellman structural arguments；本轮定位为 PDF p.2、p.8--11。

因此投稿中的正确知识债务表述应为：

> Standard POMDP and Blackwell theory supply the control and information-ordering tools. Our contribution is the Agent-memory specialization in which persistent authorization changes future access states and evidence experiments, yielding a falsifiable sufficiency condition and a regret consequence for score-only governance.

## 6. Reviewer 可能提出的五个致命 challenge

### Challenge 1：定理 1 只是 Bellman 恒等式

**承认部分。** 三项相加是 Bellman recursion 与 tower property 的直接结果。

**必须守住的部分。** 贡献不在代数难度，而在 canonical Agent filtration 和可审计的分账 contract：candidate/workspace transition 属于 access term，给定 next state 的 evidence experiment 属于 information term。若不固定这一执行顺序，所谓 VoR 可以通过重命名状态和观测任意漂移。

### Challenge 2：定理 2 只是 Doob--Dynkin

**承认部分。** 可测函数分解使用标准 Doob--Dynkin 引理。

**必须守住的部分。** 被要求可测的对象不是当前 reward 或 retrieval success，而是由 Agent persistent kernel 诱导的完整 lifecycle contrast。固定任务上的 iff 之外，动态 score quotient 命题要求每个 future stage 的即时效用因子化和受控 push-forward kernel 闭合，明确列出一个 score state 必须保留哪些 Agent 变量。一般 MDP homomorphism/lumpability 不是本文原创；增量是将 candidate/workspace/scope/recoverability 的遗漏变成可执行 kernel audit，并与 score-fiber regret 连接。

### Challenge 3：定理 3 只是 Blackwell/Jensen

**承认部分。** 信息更充分不会降低最优期望效用是标准 Blackwell 结论。

**必须守住的部分。** SQCAD 只在共同 state kernel 或共同 state-level posterior 下比较 conditional experiments，并把 candidate/workspace 差异留在 access term。严格正性应写成存在正概率的严格 Jensen gap，或有限 policy-tree 情况下不存在一个 continuation policy 在条件 posterior support 上同时最优。共同 state kernel 不是整条定理的普适限制：一般 action-dependent kernel 由授权 transcript 的 KL chain rule 统一处理，Bretagnolle--Huber 只提供标准两点工具，Agent-specific 增量是哪些持久动作使 conditional KL 归零、哪些 probe/restore 动作重新提供信息预算。

### Challenge 4：Agent-specific 只是换变量名

只有真实 paired rollout 能回答这一点。论文至少需要观测到下列一个非退化机制，并证明它改变 action value：

1. keep/archive 改变未来 candidate exposure；
2. workspace occupancy 产生 crowding externality；
3. archive 使某类 evidence 不再生成或只能付费 probe；
4. scope/version/persistence commitment 使动作不能下一步无成本撤销。

若这些机制在系统中都不存在，则问题确实退化为一般 retrieval/control，SQCAD 不应声称新的 Agent-specific 理论。

### Challenge 5：架构无关三分只是逻辑排中，且第三分支偷换成“所有任务必然失败”

**承认部分。** 三分的穷尽与互斥来自 null/non-null 与 fiber-constant/non-constant 的逻辑二分；measure separation、quotient factorization 和二点 minimax 也是标准工具。

**必须守住的部分。** 总括定理的贡献在于把跨架构的 keep/archive 干预压缩为 signed future-transcript kernel，并把各分支的治理后果、cost-uniform regret witness、task drift 条件和最小 estimand 放进同一可审计命题。第三分支必须保留 utility separation、score-visible immediate cost、$0<\gamma\le1$ 和 regular quotient；自然任务不分离 kernel 时不得推出失败。$\mathcal U_z$ 必须统一有界并包含零效用，否则 $\varepsilon_{\rm LC}$ 可因缩放发散，且 $T_{\rm LC}^*$ 的即时项最小性论证不完整。

最小性必须表述为 partition order；抽象 quotient 不自动是 standard Borel。只有 smooth equivalence relation 或可数 determining family 才保证可实现的 standard-Borel controller state。同时不能把“score-only failure”误解为“标量维数不足”：standard-Borel sufficient state 理论上可单射编码为一个实数，问题是现有 relevance/importance score 是否保留了 lifecycle 信息。

## 7. 可主张与禁止主张

### 可主张

- We formulate persistent memory authorization as an Agent lifecycle control problem whose actions alter future access states and conditional evidence experiments.
- We characterize when a current score is sufficient for all cost-shifted keep/archive decisions and give a strict score-fiber regret lower bound when the characterization fails.
- We isolate the conditional value of recoverability under Blackwell dominance from candidate/workspace access effects.
- We lower-bound persistent-authorization regret by the KL information preserved by the Agent's action-dependent transcript; censored archive periods contribute no distinguishing information until a probe, restore, or exposure action reopens the channel.
- We prove that every intervention-defined memory architecture is future-null, lifecycle-complete, or future-lossy relative to a declared task class, and identify $T_{\rm LC}^*$ or small $\varepsilon_{\rm LC}$ as the governance estimand.

### 禁止主张

- We introduce action-dependent transition or observation in POMDPs.
- We prove the first decision-centric theory of Agent memory.
- We invent the Bellman, Doob--Dynkin, Blackwell, or Jensen argument.
- We invent Bretagnolle--Huber, adaptive KL chain rules, or sequential-testing lower bounds.
- Any association/relevance score is always insufficient.
- More recoverability always implies keep is globally optimal.
- Every LLM Agent, every natural task, and the current fixed-cost contract necessarily lies in the future-lossy failure branch.
- Immutable base-model parameters without a retain/suppress/update intervention are automatically covered by keep/archive.
- A scalar score is intrinsically incapable of representing lifecycle-sufficient information.

## 8. 引用门禁状态

本轮只完成离线 BibTeX 解析和静态冲突检查，未设置 `CONTACT_EMAIL`，因此没有执行 Crossref、DBLP、Semantic Scholar 或 arXiv 的在线 round trip。机器输出必须原样保留：

`VERDICT-LINE: PASS: 0/7 verified, 0 errors, 0 warnings (0 checks skipped)`

这不是“7 条引用已经验证”。在这些引用进入最终 `.bib` 前，仍需使用真实联系邮箱执行完整在线 gate，并根据 canonical record 决定 arXiv 与正式版本。
