# Agent Memory 基础理论空缺与下一阶段实验路线

> 日期：2026-08-13  
> 文档性质：研究定位、核心机制与下一阶段实验路线。  
> 关联文档：`00-ResearchGap到充分性与必要性的完整实验逻辑线-20260813.md`、`11-形式化定理陈述与证明.md`、`12-必要性证明与识别路线分类学-20260813.md`、`../实验证据链/00-实验报告与当前结论.md`

## 0. 先把问题说清楚

目前论文已经证明了一个重要的 Agent Memory 缺口：

> 当记忆治理动作会影响未来的候选生成、暴露、预算竞争和任务结果时，历史关联、query-local 因果效应和 source-scope 平均，不能自动授权 keep/archive 等持久访问动作；若识别集合跨过动作边界，强行 commit 有可计算的最坏情况 regret。

这足以形成一篇“持久访问生命周期价值的识别与治理授权”理论论文。

但如果要进一步声称“填补了 Agent Memory 的 fundamental theoretical gap”，还需要证明更强的一点：

> 这种困难不是任意序贯因果问题都存在的普通困难，而是由 Agent Memory 的特殊生命周期结构产生的不可约机制。

下一阶段不应继续扩大通用因果工具清单，而应集中检验：

\[
\text{治理动作}
\rightarrow
\text{未来候选/证据流}
\rightarrow
\text{未来可识别性}
\rightarrow
\text{后续治理动作}.
\]

如果这条闭环被严格证明并通过结构消融，就能把论文从“通用理论在 Agent Memory 上的应用”推进到“从 Agent Memory 结构中产生新理论”。

## 1. 相对于 Agent Memory 现有工作的缺口

这里的“基础理论缺口”首先是领域内的缺口，不要求因果推断或序贯决策领域从未讨论过相似数学。

现有 Agent Memory 工作分别研究过：

- 记忆写入、压缩、检索、衰减和遗忘；
- 当前 query 的记忆干预或事后归因；
- provenance、scope、版本、访问控制和共享记忆治理；
- 程序记忆、决策压缩和长期经验更新。

但已核对工作没有统一回答以下问题：

1. 持久访问动作到底是什么 treatment？
2. 它的目标是否是未来 rollout 下的 lifecycle value，而不是当前答案增益？
3. 该动作是否改变后续候选、暴露和反馈的数据生成机制？
4. 什么识别条件使证据有权修改持久访问状态？
5. 识别不足时，是否必须 probe、restore、defer 或改变治理粒度？

因此当前可以声称的领域缺口是：

> Agent Memory 缺少“持久访问生命周期价值—决策识别—治理授权”的统一形式化接口。

这不是说 Agent Memory 以前没有因果、审计或遗忘研究；而是说这些模块还没有被统一成同一个 treatment、estimand 和 authorization contract。

## 2. 已经完成的必要性证明是什么

### 2.1 Theorem 1：历史关联不足

两个世界的完整观测日志分布完全相同，但目标记忆的生命周期价值符号相反。因此，仅靠共现、成功率或历史分数，不能保证正确 keep/archive。

### 2.2 Theorem 2：query-local 因果效应不足

两条记忆对当前 query 的真 do-effect 完全相同，但一个长期应 archive，另一个长期应 keep。原因是持久动作还改变未来候选、预算、共暴露和 continuation value。

### 2.3 Theorem 4/5：未识别时强行提交有下界

若生命周期效应的识别集合为 \([L,U]\)，且 \(L\le 0\le U\)，则相容世界支持不同动作。任何不探测、不拒绝的 committing rule 都有 minimax regret：

\[
R^*(L,U)=\frac{U(-L)}{U-L}.
\]

所以当前已经证明：

> Qualification gate、额外证据或 defer/probe 不是任意工程偏好；在未识别类上，它们是突破强行提交下界所必需的决策机制。

## 3. 为什么仍要讨论“Agent Memory 独有的困难”

Theorem 4/5 的数学骨架可以迁移到医疗、推荐、广告或一般 OPE：只要存在观测等价世界和相反最优动作，就会有类似下界。

所以它们证明了“门控必要性”，但还没有单独证明：

> Agent Memory 的生命周期结构本身，会产生一般 bandit/OPE 没有的下界。

这不是否定现有结果，而是区分两个问题：

- **领域缺口**：Agent Memory 文献没有建立持久访问决策的识别—授权理论。当前已基本证明。
- **基础理论原创性**：Agent Memory 的结构导致新的、不可由通用理论直接推出的现象。当前还需补证。

最有希望的独有机制不是“有混杂”，而是“治理动作改变未来还能否获得证据”：

\[
\text{archive/downweight}
\rightarrow
\text{候选支持下降}
\rightarrow
\text{暴露与结果反馈减少}
\rightarrow
\text{错误治理无法被发现}
\rightarrow
\text{错误治理持续存在}.
\]

这可称为 **self-obscuring / self-confirming memory governance**。

## 4. 你提出的两条直觉：哪些准确，如何形式化

### 4.1 直觉一：Memory 参与认知，形成自我强化和自我实现

你的直觉是有研究价值的，但需要把“认知科学启发”转换为可检验的 Agent 机制。

可以保留的部分：

1. Agent 的后续推理、计划和工具调用依赖它暴露到上下文中的 memory；
2. 当前 memory 会影响注意力分配、候选排序和下一步行为；
3. 下一步行为和结果又会反过来更新 memory 的资格或访问权；
4. 因此 memory 不是被动数据库，而是会参与未来状态生成。

适合形式化为：

\[
M_t \rightarrow E_t \rightarrow X_{t+1},Y_t
\rightarrow M_{t+1},
\]

并显式加入有限上下文/注意力预算 \(B_t\)。

不能直接写成的部分：

- “LLM 天然遵循自由能最小化”；
- “Agent 必然追求最省 token 的生成路径”；
- “人类可以逆人性思考，因此 Agent 天然不能”。

这些目前只能作为待检验假设。LLM 的 token、计算和检索偏好可能来自训练目标、上下文长度、解码、工具策略和系统成本，而不是已被证明的自由能定律。

可检验假设 H1：

> 在固定任务效用下，Agent 会偏好降低检索、上下文和推理成本的路径；当 memory 访问策略被奖励为低成本时，该偏好会放大早期治理信号，使错误的 memory qualification 产生 self-reinforcing trajectory。

实验上必须直接改变成本权重、上下文预算和反事实 memory，不能只观察自然轨迹后宣称“自由能最小化”。

### 4.2 直觉二：任务漂移使 Agent Memory 不完全是传统序贯决策

这条直觉也有价值，但“任务不是序贯的”需要改成更精确的说法。

Agent 可能面对：

- task distribution drift；
- user intent drift；
- tool/model/evaluator version drift；
- 任务之间目标不连续，但共享同一 memory store；
- 未来任务类型取决于当前 memory 诱导的计划和行动。

因此，记忆价值不一定是同一固定 reward process 上的简单累积。更合适的形式是：

\[
S_{t+1}\sim P(\cdot\mid S_t,A_t,M_t,\xi_t),
\qquad
\xi_{t+1}\sim P_\mathrm{task}(\cdot\mid \xi_t,M_t,A_t),
\]

其中 \(\xi_t\) 表示任务/用户/工具作用域，可能随 agent 行为和 memory 状态改变。

可检验假设 H2：

> 在任务漂移和共享 memory 条件下，source-scope 的 memory value 不能安全迁移到 target-scope；而 scope-aware qualification 与 fresh probe 可以降低 negative transfer 和 false forgetting。

“任务并不是序贯的”不宜直接作为理论结论。只要系统有状态、动作、转移和回报，许多漂移任务仍可嵌入 POMDP、非平稳 MDP、contextual bandit 或 meta-RL。真正需要证明的是：

> memory policy 会改变任务分布、任务可见性或任务反馈，使固定任务分布假设失效。

这才是 Agent Memory 特有的 policy–task–memory feedback。

## 5. 当前研究过程还缺什么

### 缺口 A：特殊结构还是人为例子？

当前 hitchhiker、crowding、rare-critical 和 candidate feedback 已经是合理机制，但还没有证明它们在一个统一模型类中不可约。

必须做结构消融：

| 世界 | 候选受治理影响 | 持久访问动作 | restore | 预期 |
|---|---:|---:|---:|---|
| W0 | 否 | 否 | 否 | 可退化为局部检索/静态 bandit |
| W1 | 否 | 是 | 是 | 长期动作，但无证据自遮蔽 |
| W2 | 是 | 是 | 否 | archive 造成 self-confirming non-identifiability |
| W3 | 是 | 是 | 是 | restore/probe 打破自遮蔽，但有恢复成本 |

要证明只有 W2/W3 具有新的生命周期边界，而不是四个世界都同样困难。

### 缺口 B：未来证据流是否真的受治理动作控制？

要分别记录并建模：

- candidate support；
- exposure probability；
- adoption/usage；
- outcome feedback；
- restore/revalidation opportunities。

如果 action 只改变当前 query 排序而不改变这些变量，就不应宣称 self-obscuring。

### 缺口 C：动态探索尚缺严格上下界

当前无探测线性 regret、探测后平台化和 KL 同阶结果仍主要是计算验证。需要严格证明：

\[
R_T^{\mathrm{no\ restore/probe}}\ge cT,
\]

以及某种 restore/probe 策略的显式上界，并把探测、延迟、token 和恢复成本纳入同一决策目标。

### 缺口 D：LLM/Agent 的成本偏好不能只靠口头假设

“最小自由能”“最省 token”可以作为机制假设，但不能直接当作事实。需要把它转成：

- context budget；
- retrieval cost；
- token/latency penalty；
- action-selection prior；
- entropy/novelty penalty。

然后做成本权重和预算的干预实验。

### 缺口 E：任务漂移不能只用“非序贯”描述

需要区分：

- 普通非平稳任务分布；
- memory-induced task drift；
- scope/version transport failure；
- shared-store cross-task interference。

只有当任务漂移由 memory policy 或 agent action 反馈产生时，才构成更强的 memory-originated 机制。

## 6. 下一阶段应优先证明的理论结果

### T1：Self-obscuring lifecycle theorem（最高优先级）

在 archive 会降低未来候选支持、错误归档后只能以概率 \(q\) restore 的模型类中，证明：

1. 任意无 restore/probe 的 committing policy 在相反最优动作世界上具有 \(\Omega(T)\) regret；
2. 具有 \(q>0\) 的恢复探测策略具有显式有限或次线性 regret 上界；
3. 当候选支持与证据流独立于 action 时，上述线性下界消失或退化为普通 bandit/OPE 下界。

### T2：Reduction separation theorem

证明去掉“持久 action 改变候选支持和证据流”后，问题可化约到 contextual bandit/OPE；保留该结构后，任何保持即时 reward 和动作集合不变的 reduction 必须额外加入 evidence-availability state、restore channel 或 lineage state。

目标不是声称所有通用理论都失效，而是证明：

> 如果不把未来证据可得性作为状态，普通 reduction 无法保持原问题的反馈语义。

### T3：Interference granularity theorem

在给定 interference graph 的条件下，刻画 item-level、component-level 和 bundle-level 的可识别性，证明何时 bundle 是最细安全治理粒度。

### T4：Evidence-preserving restore theorem

证明 source preservation、derived access 和 restore channel 是三个不同治理变量；保留 source 不等于当前可访问，禁止 restore 会使某些错误治理不可恢复，允许低概率 restore 则能恢复未来支持但产生明确成本。

### T5：Scope/version transport boundary theorem

在 task/user/tool/model/evaluator 漂移下，给出 candidate transition invariance、support overlap 和 outcome measurement stability 等 memory-policy transport 条件，并构造缺失条件时的 target-discordant 世界。

### T6：Authorization certificate theorem

定义证书：

\[
Z=(\text{estimand},\text{scope},\text{support},\text{measurement},\text{bound},\text{action}).
\]

证明：

- soundness：证书通过意味着动作在识别集合内安全；
- verifiability：第三方可由日志和假设复核；
- non-triviality：在满足条件时能授权非空 commit 动作。

## 7. 实验设计：证明结构不是例子

### 7.1 结构消融矩阵

每个实验同时报告 lifecycle value、future regret、证据流覆盖率、纠正时间、probe/restore cost 和是否可由标准 bandit/OPE 解释。

| 消融 | 保留结构 | 去掉结构 | 关键判据 |
|---|---|---|---|
| A | archive 改变候选生成 | candidate 与 action 独立 | 去掉后 self-obscuring 下界消失 |
| B | 持久 access action | 只做 query-local exposure | 去掉后长期证据自遮蔽消失 |
| C | restore/probe 重新打开证据流 | 不可恢复 archive | 恢复成本与 regret 出现可预测关系 |
| D | finite budget 与共同暴露 | 无限 budget/单记忆暴露 | 去掉后 item-level gap 消失或变为可加 |
| E | source/derived 双层 lineage | 单一 memory object | 删除、archive、restore 的识别与恢复边界分离 |
| F | task/scope/version drift | 稳定 scope | 只有漂移时出现 transport boundary |

### 7.2 与通用 bandit/OPE 的控制

设置三个控制组：

1. 静态 bandit：action 不改变候选支持和未来证据；
2. contextual bandit：加入即时任务上下文，但无 lineage、restore 和 evidence censoring；
3. 标准 OPE：日志有 overlap，候选流不由治理 action 改变。

预期结果：控制组可由标准方法处理；只有加入“治理动作改变未来证据流”后出现新的永久性错误或复杂度增长。

### 7.3 Self-confirming 实验

构造两个观测等价世界：

- K 世界：目标记忆长期有益；
- A 世界：目标记忆长期有害；
- 错误 archive 后目标记忆不再进入候选集；
- 只有 restore/probe 才能恢复证据流。

比较：无探测 commit、固定概率 restore、uncertainty-triggered restore、cost-aware commit/defer/probe。

必须报告：

- regret 随 horizon 的斜率；
- 纠正时间；
- candidate support 恢复率；
- 新证据到达率；
- false forgetting、harmful retention；
- probe/restore token 与延迟成本。

### 7.4 LLM/Agent 成本偏好实验

把“最小自由能/最省 token”降为可检验假设，而不是理论前提。控制：

- context budget；
- retrieval token cost；
- latency penalty；
- exploration/probe cost；
- novelty/uncertainty bonus。

测试 H1：成本惩罚越强，Agent 越倾向使用已有 memory 和低成本路径，错误 qualification 的自我强化越强；增加反事实 probe 或恢复预算后，该效应是否减弱。

不能从这些实验直接推出“LLM 遵循自由能原理”；最多能得到：

> 在指定成本函数和解码/工具策略下，Agent 表现出可重复的低成本路径偏好，并且该偏好会改变 memory qualification dynamics。

### 7.5 任务漂移与 memory-induced drift 实验

区分三种情况：

1. 外生 task drift：任务分布自行变化；
2. memory-induced drift：memory 访问改变计划、工具使用和后续任务分布；
3. scope/version drift：用户、工具、模型或 evaluator 改变。

比较：无门控 transport、scope-aware gate、fresh probe、restore-enabled policy。

关键判据：只有在 memory policy 参与改变未来任务或反馈机制时，才把它称为 memory-originated drift；普通 covariate shift 不足以支持这一表述。

### 7.6 干扰粒度实验

构造独立、pairwise、clique 和非可加效应的 interference graph，比较 item-level、connected-component-level 和 bundle-level 治理。

目标是验证：

\[
\text{interference structure}
\rightarrow
\text{identifiable coalition}
\rightarrow
\text{最细安全治理粒度}.
\]

### 7.7 Source/derived/restore 实验

比较：

1. 删除 source 与 derived；
2. 保留 source、archive derived；
3. 保留 derived、删除 source；
4. 保留 source 但禁止 restore；
5. 保留 source 且低概率 restore。

指标：future support、re-identification time、recovery regret、false forgetting、privacy/storage cost。

## 8. 理论—系统—真实轨迹闭环

### 8.1 理论层

第一优先级是 T1 + T2；第二优先级是 T3 或 T6；T4/T5 作为扩展。

### 8.2 系统层

统一记录 candidate generation、exposure、position、budget、adoption、persistent action、archive/restore、source/derived lineage、scope/version、outcome、cost 和 risk。

核心指标必须包括 lifecycle value、future regret、false forgetting、harmful retention、active-token cost 和 recovery latency，不能只报告 QA 或 Recall。

### 8.3 真实轨迹层

在 LongMemEval-S、LoCoMo 或其他可复现长期轨迹上完成 chronological future split、受控 persistent-access action、trace-grounded 半合成反事实、统一 reader/evaluator/budget 和强基线比较。

真实实验不能替代理论证明，但用于确认 T1/T2 的机制在 Agent Memory 轨迹中存在对应物。

## 9. 验收标准

### 可以升级为“Agent Memory 独立基础理论问题”的最低条件

至少满足以下三项中的两项，最好三项全部满足：

1. 一个明确依赖 archive-induced candidate/evidence censoring 的定理，且去掉该结构后定理失效；
2. 一个 reduction-separation 结果，说明保留该结构后不能用不增加 evidence-availability/lineage/restore 状态的普通 bandit/OPE 表达；
3. 一个动态探索下界与匹配上界；
4. 一个 interference granularity 或 source/derived/restore 的新识别边界；
5. authorization certificate 的 soundness、verifiability、non-triviality；
6. trace-grounded chronological 实验与理论方向一致；
7. 统一候选流、budget、reader、evaluator 和 future split 下的强基线比较。

### 当前可用的论文主张

> 本文填补了 Agent Memory 中持久访问生命周期价值的决策识别与治理授权缺口，并证明在未识别世界上直接 committing 存在形式化 regret 下界。

### 未来可用的更强主张

> Agent Memory 的持久、可恢复、竞争性和证据依赖生命周期产生了独立的 self-obscuring identification dynamics；该动力学不能被普通 query-local retrieval、静态 bandit 或标准 OPE 在不增加关键状态的情况下等价表达。

## 10. 近期执行顺序

1. 冻结最小 self-obscuring 模型，完成 T1 的严格 \(\Omega(T)\) 下界；
2. 完成 restore/probe 的显式上界，并加入 token、延迟和风险成本；
3. 做 W0–W3 结构消融，证明现象在去掉关键结构后消失；
4. 做静态 bandit、contextual bandit、标准 OPE 的 reduction control；
5. 将 bundle fallback 升级为 interference granularity theorem；
6. 形式化 authorization certificate；
7. 完成 trace-grounded chronological 实验，再决定是否升级论文主张。

## 11. 最终定位

目前论文应定位为：

> 一篇围绕 Agent Memory 持久访问生命周期价值的 memory-specific identification 与 governance-authorization 理论论文。

下一阶段要证明的不是“因果推断可以用于 memory”，而是：

> Agent Memory 的持久、可恢复、竞争性、任务漂移和证据依赖结构，会产生一般 query-local retrieval、静态 bandit 和标准 OPE 不具备的 self-obscuring identification dynamics。

完成这一步后，论文才有充分依据从“Agent Memory 领域的理论缺口”升级为“从 Agent Memory 特殊结构中推出的新基础理论”。

## 12. 上升到“基础理论空缺”需要证明什么

这里必须把“需要的证据”拆成四个层次。每一层回答不同问题，不能用后一层替代前一层。

### 12.1 第一层：领域覆盖证据——现有 Agent Memory 工作确实没有回答这个问题

这一步不是证明数学新颖性，而是证明研究问题在目标领域内尚未被系统回答。对每个最接近工作，必须逐字段审计：

| 字段 | 要核对的问题 |
|---|---|
| action semantics | 是 hard delete、archive、soft decay、compression，还是仅仅改变当前 query 的排序？ |
| treatment window | 动作只影响当前 query，还是在未来一段生命周期内保持有效？ |
| candidate transition | 治理动作是否改变未来候选集的生成分布或支持集？ |
| feedback channel | 动作之后是否继续记录暴露、采纳、结果和恢复反馈？ |
| estimand | 目标是当前答案增益、检索分数、压缩损失，还是未来 rollout 的 lifecycle value？ |
| authorization | 是否区分 point、bound、unresolved、mismatch，并要求证据资格后才能 commit？ |
| recovery | 是否保留 source、lineage、restore 或重新验证通道？ |
| evaluation | 是否使用 chronological future split、任务漂移和 false-forgetting/harmful-retention 指标？ |

只有当审计确认“已有工作分别覆盖局部模块，但没有覆盖 treatment–estimand–feedback–authorization 的完整组合”时，才能提出领域缺口。这里的结论应写成“在已核对范围内未发现”，而不是“整个领域都没有”。

### 12.2 第二层：机制证据——缺口由 Agent Memory 的生命周期结构产生

这一层是从“领域没有做”走向“为什么这个问题具有基础性”的关键。需要证明以下闭环真实存在且可被干预：

\[
 A_t^{\mathrm{access}}
 \rightarrow C_{t+1}
 \rightarrow E_{t+1}
 \rightarrow Y_{t+1}
 \rightarrow O_{t+1}^{\mathrm{evidence}}
 \rightarrow A_{t+1}^{\mathrm{access}}.
\]

其中治理动作不仅影响回报，还影响未来证据能否出现。至少需要逐项显示：

1. **支持集变化**：archive/downweight 后，目标记忆或其 lineage 在未来候选中的概率实际下降；
2. **反馈缺失**：候选支持下降导致暴露、采纳和结果反馈减少；
3. **纠错受阻**：没有 restore/probe 时，错误治理不会自然被未来数据纠正；
4. **动作自我强化**：早期错误 qualification 会提高未来继续错误治理的概率；
5. **可逆性产生信息价值**：restore/probe 能重新打开证据流，但需付出 token、延迟、风险或任务干扰成本。

仅展示一个“删掉后表现变差”的例子不够；必须做结构消融，证明去掉候选反馈、持久性或恢复通道后，self-obscuring 现象消失或退化为普通探索问题。

### 12.3 第三层：理论证据——得到一般下界、识别边界和匹配上界

基础理论不能只给一个反例数字，需要至少形成一个可量词化的结果族：

- **不可识别性定理**：在某个明确定义的 persistent-memory model class 上，存在观测等价且最优动作相反的世界；
- **动态下界**：无 restore/probe 或无最小探索率时，累计 regret 至少为 \(\Omega(T)\) 或给出与恢复概率、证据间隔和支持覆盖有关的下界；
- **结构分离定理**：去掉 archive-induced candidate/evidence censoring 后，问题可以化约为标准 bandit/OPE；保留它后，任何保持原有反馈语义的 reduction 必须显式加入 evidence availability、lineage 或 restore 状态；
- **恢复上界**：在给定 restore 概率、可观测反馈和 overlap 条件下，给出 probe/restore 策略的显式 regret 或 sample-complexity 上界；
- **治理粒度边界**：在非可加 interference 下，刻画 item-level 与 bundle-level 的最细可识别治理粒度；
- **授权证书定理**：证明 qualification certificate 的 soundness、verifiability 和 non-triviality。

其中最重要的是上下界配对：只证明“无探测很差”仍可能只是难度说明；如果同时证明“某种恢复策略达到同阶上界”，才开始形成完整理论。

### 12.4 第四层：系统与真实轨迹证据——理论确实描述 Agent Memory

理论不能被真实系统实验替代，但需要现实接地来证明模型不是纯抽象 SCM。最低要求是：

- 在统一 candidate stream、reader、evaluator、budget 和 chronological future split 下运行；
- 实现真正的 persistent action，而非只改当前 query 的 prompt；
- 记录候选、暴露、位置、采纳、动作、restore、lineage、结果和成本；
- 报告 lifecycle value、future regret、false forgetting、harmful retention、active tokens、probe/restore cost；
- 使用至少一个公开长期轨迹集，并与强基线进行同合同比较。

这一层用于检验机制的现实发生率和方法的外部效度，不用于替代理论证明。

## 13. 根据理论结果设计“更好的框架”实验

框架实验的目标不能简单设为“SQCAD 总分超过所有基线”。应分成三个问题：

1. 框架是否真的实现了理论要求的 treatment 和 feedback？
2. 框架是否在理论机制出现时减少错误治理？
3. 框架的探测、恢复和审计成本是否值得？

### 13.1 先冻结统一实验合同

所有方法共享：

- 同一基础 LLM、retriever、reader 和 evaluator；
- 同一候选生成器与候选数量；
- 同一 workspace budget、token 预算和延迟预算；
- 同一 memory source、derived representation 和 lineage；
- 同一时间顺序，禁止未来任务泄漏；
- 同一 task/user/tool/model scope 划分；
- 同一 cost contract。

否则“框架优于基线”无法归因于治理机制，可能只是 reader、检索器或预算不同。

### 13.2 基线分层

至少保留三层基线：

| 基线层 | 方法 | 作用 |
|---|---|---|
| 低成本代理 | recency、frequency、semantic、fixed decay、association-only | 检验常用启发式在 gap 世界中的失败 |
| 局部因果/决策 | CMI-style local intervention、item-level causal control、DeMem/decision proxy | 检验 local effect 或压缩目标是否足够 |
| 识别/治理控制 | random rollout、oracle lifecycle、probe-enabled baseline、bundle-level control | 区分识别问题、估计问题与治理粒度问题 |

官方完整系统若无法复现，必须把结果标成 proxy、结构级或机制级，不得写成系统级全面优于。

### 13.3 四组核心机制实验

#### 实验 A：自我遮蔽与恢复

构造两个观测等价世界：一个目标记忆长期有益，一个长期有害。早期日志不足以区分，错误 archive 后目标记忆不再进入候选集。

比较：

- association-only commit；
- local-causal commit；
- 无探测 SQCAD；
- 固定概率 restore；
- uncertainty-triggered restore；
- cost-aware commit/defer/probe。

指标：累计 regret 斜率、纠正时间、候选支持恢复率、证据到达率、false forgetting、harmful retention 和恢复成本。

关键判据：无 restore 的规则出现线性 regret，而带恢复的规则出现可预测的平台或次线性增长；去掉候选支持反馈后，该差异消失。

#### 实验 B：任务漂移与 memory-induced drift

分开三种环境：

1. 外生任务漂移：任务分布自行变化；
2. memory-induced drift：memory 访问改变计划、工具使用和后续任务分布；
3. scope/version drift：用户、工具、模型或 evaluator 改变。

比较无门控 transport、scope-aware qualification、fresh probe 和 restore-enabled policy。

指标：target-scope value、negative transfer、false forgetting、harmful retention、scope calibration 和重新识别时间。

关键判据：只有在 memory policy 参与改变未来任务/反馈机制时，才把结果归因于 memory-originated drift；普通 covariate shift 只能作为外部对照。

#### 实验 C：有限注意力/成本偏好

“LLM 天然最小自由能”不能作为前提，必须转成可操纵变量：

- context budget；
- retrieval token cost；
- latency penalty；
- probe cost；
- uncertainty/novelty bonus；
- reader 的上下文压缩策略。

比较不同成本权重下 Agent 是否越来越依赖已有 memory、减少探索、加剧错误 qualification 的自我强化。只能表述为“在给定成本合同下观察到低成本路径偏好”，不能直接宣称证明了自由能原理。

#### 实验 D：干扰与治理粒度

构造独立、pairwise、clique 和非可加 interference graph，比较 item-level、connected-component-level 和 bundle-level 治理。

指标：item-level sign error、bundle value bias、safe-action coverage、unresolved rate、false forgetting 和 active-token cost。

关键判据：在 item-level 不可识别时，bundle-level 是否成为最细可安全治理粒度；若不是，应报告反例并修正理论主张。

### 13.4 真实轨迹实验

在 LongMemEval-S、LoCoMo 或其他可复现长期轨迹上，进行 trace-grounded chronological future split：

1. 固定 reader、retriever、evaluator 和 workspace budget；
2. 对真实候选流施加可审计的 keep/archive/downweight/restore；
3. 记录候选支持、暴露、位置、采纳、动作、lineage、结果和成本；
4. 使用受控半合成注入构造可知道真值的 rare-positive、hitchhiker、scope-shift 和 stale-memory 场景；
5. 与低成本、局部因果、probe-enabled 和 bundle-level 基线比较。

真实轨迹结果主要回答“机制是否在真实 Agent Memory 接口中出现”，不能单独证明一般定理。

## 14. 如果框架不如基线：到底否定了什么

这是必须事先写入研究计划的判决树。框架表现不佳，不会自动推翻理论空缺。

### 14.1 理论定理与框架性能是两件事

理论定理通常是条件命题：

\[
\text{在模型类 }\mathcal M\text{ 和观测合同 }\mathcal O\text{ 下，某性质成立}.
\]

框架性能则是：

\[
\text{在某个任务分布、LLM、reader、budget 和成本合同下，平均表现如何}.
\]

因此，SQCAD 在一个真实 benchmark 上不如 RRF，并不能直接否定 Theorem 1/2/4/5。

### 14.2 四种失败分别意味着什么

| 观察结果 | 更可能否定的对象 | 不直接否定的对象 |
|---|---|---|
| 反例世界中 baseline 也能正确识别 lifecycle value | 反例构造或 gap 命题 | 其他世界、其他定理 |
| gap 世界中 SQCAD 没有减少 regret | SQCAD 的实现、gate、估计器或恢复策略 | gap 是否存在 |
| 统一真实 benchmark 上 SQCAD 不如强基线 | 方法的经验优势、成本合同或外部效度 | 识别不可行性定理 |
| 去掉 candidate/evidence feedback 后仍有同样下界 | “该下界是 Agent Memory 特有”的主张 | 一般未识别决策下界 |

### 14.3 什么时候才会真正推翻理论缺口

只有出现以下证据，才会实质性削弱“持久访问识别—授权缺口”：

1. 在同一 treatment、estimand 和观测合同下，现有基线能够普遍识别 lifecycle value，而非只在某个合成世界中碰巧成功；
2. 存在一种不需要 qualification、probe、defer 或额外识别假设的 committing rule，在整个声称模型类上达到零 worst-case regret；
3. 去掉或加入 memory-specific 生命周期结构，定理和下界都不发生变化，说明所谓特殊性只是命名差异；
4. 现有 Agent Memory 文献已明确给出同一 treatment–estimand–feedback–authorization 理论，并覆盖相同的边界和证明。

普通 benchmark 上的平均性能落后，不满足上述任一条件，不能推翻理论 gap。

### 14.4 如果理论成立但框架不如基线，正确结论是什么

应区分四种结果：

- **Theory true, framework weak**：gap 和定理成立，但 SQCAD 没有把可识别性转化为有效算法；需要修复方法。
- **Theory true, framework costly**：框架降低了错误治理，却在 token、延迟或 probe 成本下净收益不占优；需要改成本合同或限定适用场景。
- **Theory true, benchmark benign**：真实 benchmark 中没有足够的 hitchhiker、rare-positive、crowding 或 drift；说明任务不激发该 gap，不说明 gap 不存在。
- **Theory false**：反例在统一合同下被反驳，或者基线在整个模型类上普遍识别 lifecycle value；这才是否定理论命题。

因此实验结果的正确问题不是“SQCAD 是否总分第一”，而是：

> 当理论机制被激活时，框架是否减少理论预测的错误；当机制不存在时，框架是否愿意退化为简单基线而不付出不必要成本。

## 15. 最终研究判决

当前论文已经足以声称：

> Agent Memory 领域缺少持久访问生命周期价值的决策识别与治理授权理论；本文用观测等价、local-effect insufficiency、transport failure 和 minimax regret 证明了该缺口的必要性。

要进一步声称“Agent Memory 的 fundamental theoretical gap”，还需证明：

> 持久、可恢复、竞争性、任务漂移和证据依赖的生命周期结构，会产生 self-obscuring identification dynamics；该动力学在去掉关键结构后消失，并且不能在不增加关键状态的情况下化约为普通 bandit/OPE。

如果最终框架不如基线，优先解释为方法、成本或外部效度问题；只有当理论反例、定理量词或结构不可约性本身被反驳时，才应撤回理论主张。
