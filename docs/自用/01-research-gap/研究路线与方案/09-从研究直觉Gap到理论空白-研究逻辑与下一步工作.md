# 从研究假设到理论空白：SQCAD 研究推进路线图

> 用途：规定从文献直觉 → 研究假设 → 反例构造 → 识别条件 → 框架推导 → 验证闭环的完整逻辑。
>
> **当前状态（2026-08-12）**：不可识别性一侧已通过三个构造性反例基本立住；可识别性一侧：Theorem 3 v2 已写出（决策期模型 + 双路估计器 + Qualification 门控），**Stage 1 识别恢复实验通过**（协议路径估计器恢复已知生命周期值，bias=−0.47、CI 覆盖 12/12、自信错误 0），**Stage 2 五种条件违反全部被 gate 捕获**（见 `实验证据链/03-识别恢复实验报告-20260812.md`）。观测路径（g-formula/DR）与部分识别界尚未实现验证。Gap 当前定位为 **counterexample-grounded memory-specific identification gap** 且**识别协议的协议路径已有合成环境验证**，但尚未到 "identification theory complete"。
>
> 与相关文件的关系：
> - `07-Introduction规范稿.md` — 对外叙事，本文为其提供理论支撑
> - `08-Gap1覆盖审计与框架设计重点-20260811.md` — 文献覆盖边界
> - `10-识别条件到框架设计的形式化推导.md` — **本文的延续**：从 §0.3 的三项证明 → 识别条件 → 框架推导的完整映射
> - 本文 + 10 共同构成论文方法部分的理论基础

---

## 0. 起点判断：我们目前拥有什么

### 0.1 文献事实（已确认）

基于对现有工作的覆盖审计（详见 `08-Gap1覆盖审计`）：

| 工作 | 实际估计的量 | 为什么与 SQCAD 不同 |
| --- | --- | --- |
| Memory Worth | 历史 success/failure 共现 → 关联价值 | 不区分 policy-generated exposure 与 causal contribution |
| CMI | query-local intervention effect $\Delta_t(i)$ | 固定 query + candidate，不涉及未来轨迹 |
| Trivium | 一般序贯因果修订（causal probe → SCM revision） | treatment 是预设 SCM 的 probe，不是 persistent memory access |
| GovMem | 写入时证据资格（provenance, scope, counterevidence） | 判断写入资格，不估计写入后持久访问的跨期因果价值 |
| OPE / MSM / causal bandits | 通用序贯处理效应 | 未针对 memory-specific treatment construction 给出可操作协议 |

### 0.2 研究假设（待证明）

基于以上文献事实，我们形成如下**研究假设**（注意：这是假设，不是结论）：

> 现有工作可能都没有直接估计"改变既有记忆的持久访问状态后，对未来生命周期轨迹的累计因果价值"。
>
> 具体而言：
> - 历史关联价值 $\ne$ 持久访问干预的生命周期价值；
> - query-local intervention effect $\ne$ 持久访问干预的生命周期价值；
> - 通用序贯因果工具存在，但尚未针对 memory-specific persistent-access treatment 构造给出可操作协议。

**这个假设的独特交叉点**由四个要素共同定义：

1. treatment 是 persistent access action，而非一次 prompt insertion；
2. exposure 由当前 policy 生成，且随时间变化；
3. treatment 会改变未来 candidate stream 和后续 policy feedback；
4. 目标是 lifecycle policy value，而非单次回答分差。

只有当这四个要素同时缺失于现有工作时，该假设才成立。

### 0.3 假设成立的条件：三项证明的当前状态

**不能仅仅因为文献没有写出某个公式，就断言"现有工作无法求解"。** 必须通过以下三个证明将假设升级为理论空白：

```text
证明 1（estimand 区分）✅ 已完成（命题 A/B/C 联合支持）
  ┃  定义的量 V_s^π(a) 与 Memory Worth、CMI、OPE/MSM 等估计的量在构造性反例中不同
  ┃  状态：三项反例全部成立（20/20 seeds），25 个单元测试通过
  ┃
  ▼
证明 2（不可识别性）✅ 反例已建立，定理待形式化
  ┃  命题 A: P(O|M₁)=P(O|M₂) 但 lifecycle value 符号相反（代数等价构造）
  ┃  命题 B: Δ_do 完全相等但 lifecycle value 符号相反（forced intervention）
  ┃  命题 C: source 数据相同但 target value 符号相反（两个世界构造）
  ┃  状态：构造性反例全部成立；尚未写成正式的 non-identifiability theorem
  ┃
  ▼
证明 3（决策必要性）✅ 反例已建立
  ┃  命题 A: Memory Worth 在 M₂ 中 regret = 1100.0
  ┃  命题 B: CMI observational regret = 1784.0
  ┃  命题 C: source-average 在至少一个 world 中产生 regret > 0
  ┃  状态：所有 regret > 0 严格成立
```

**当前总体状态**：
- 不可识别性一侧（证明 1–3 的反例层面）：**基本立住**
- 可识别性一侧（identification theorem、observable formula、partial-identification bound）：**尚需完成**
- Gap 当前定位：**counterexample-grounded, memory-specific identification gap**
- **不能写成**："基础理论空白已经被证明"或"不可识别性定理已经成立"

### 0.4 证明通过后的路线图：从反例到框架的推导链

当前的核心任务已从"构造反例证明 Gap 存在"转向"从反例和识别条件推导框架"。

推导链（详见 `10-识别条件到框架设计的形式化推导.md`）：

```text
Non-identifiability (counterexamples A, B, C)
    → Minimal identification assumptions (9 conditions)
        → SQCAD logging / intervention protocol
            → Qualification gate
                → Risk-sensitive reversible access decision
```

**论文的核心逻辑因此变为**：

> 先证明 persistent-access lifecycle value 在历史日志、局部干预或无条件作用域平均下不可识别；随后刻画其识别所必需的日志、干预和稳定性条件；SQCAD 将这些条件实现为 Evidence–Qualification–Access 的可审计治理协议。

而非：

> 我们设计了三个模块，实验显示它们有效。

**三层框架的理论角色**（详见 `10` 的 §3）：

| 框架层 | 理论角色 | 关键约束 |
|---|---|---|
| **Evidence** | 保存识别所需变量和干预记录 | 每个字段必须对应一条识别条件的观测性要求 |
| **Qualification** | 检查识别假设是否足以授权决策 | `unresolved` 是理论要求（识别条件不满足时禁止 action），非经验保守 |
| **Access** | 在已识别或有界的价值下执行长期动作 | 接收 qualification + 风险 + 成本 + interference |

反例 → 识别条件 → 框架组件的完整对应表见 `10` 的 §2 和 §4。

### 0.5 任何时候证明失败的处理

```text
证明 1 失败 → 收缩假设：V_s^π 与已有 estimand 重叠 → 重新定义或放弃
证明 2 失败 → 收缩假设：现有日志已可识别 → Gap 缩小为 engineering gap
证明 3 失败 → 收缩假设：V_s^π 无决策增量 → 问题本身不成立
```

### 0.6 阅读指南

- **如果你在评估 Gap 是否成立**：重点读 §0.1–0.3（文献事实 → 假设 → 需完成的证明）
- **如果你在构造证明**：重点读 §1–§4（estimand 定义 + 不可识别性 + 决策必要性）和 §7（定理候选）
- **如果你在设计框架**：重点读 §5–§6（识别条件 → 框架推导）和 §7.5 的框架修改分支表——**但请注意，在证明通过之前框架设计仅为候选**
- **如果你在规划实验**：重点读 §8（验证闭环）和 §9（主张升级阶梯）
- **如果你在做下一步决策**：重点读 §0.4–0.5（分支逻辑）和 §11（工作顺序）

---

## 1. 研究假设的严格表述

> §0 已说明当前状态是"假设"而非"已证明的 Gap"。本节将此假设写成可操作、可证伪的形式。

### 1.1 假设的核心陈述

**H1（estimand 区分假设）**：存在一个定义良好的 estimand $V_s^\pi(a)$——persistent-access lifecycle value——它不同于：(i) 历史关联价值（Memory Worth 类），(ii) query-local intervention effect（CMI 类），(iii) 通用序贯因果修订的 treatment effect（Trivium 类），(iv) 写入时证据资格判断（GovMem 类）。

**H2（不可识别性假设）**：在仅观测历史 candidate、exposure 和 outcome 的日志信息集合下，$V_s^\pi(a)$ 不可被点识别。即存在 $M_1 \neq M_2$ 使得 $P_{M_1}(O) = P_{M_2}(O)$ 但 $V_{s,M_1}^\pi(a) \neq V_{s,M_2}^\pi(a)$。

**H3（决策必要性假设）**：存在至少一类环境，其中使用关联价值、局部效应或 scope 平均值替代 $V_s^\pi(a)$ 做访问决策会产生严格正的 regret。

### 1.2 假设的证伪条件

每个假设都有明确的证伪路径：

| 假设 | 如何被证伪 | 证伪后的处理 |
| --- | --- | --- |
| H1 | 发现已有工作明确定义并估计了 persistent-access lifecycle value | 收缩 Gap；若已有工作仅部分覆盖，缩小为"未被充分形式化" |
| H2 | 无法构造出 observationally equivalent 但 lifecycle value 不同的两个世界 | 说明现有日志信息已足够；Gap 缩小为 engineering gap |
| H3 | 在所有构造环境中，替代决策的 regret 均为零 | $V_s^\pi$ 无独立决策价值；问题本身不成立 |

### 1.3 不能再使用的宽泛表述

以下表述均不足以支撑理论空白（因为它们是口头断言，不是可证伪的假设）：

- Agent Memory 尚未使用因果分析；
- 现有 memory governance 只有相关性，没有因果性；
- 现有工作都忽略了内生性；
- 现有工作不能处理序贯因果问题；
- Bayesian 泛化可以解决历史评估无法外推的问题。

CMI 已覆盖固定 query 下的局部干预，Trivium 已覆盖一般序贯因果修订，GovMem/When Not to Write Memory 已覆盖写入时 provenance 和证据资格，MSM、DR、OPE 与 causal bandit 已提供通用序贯处理理论。SQCAD 不能把这些相邻工作抹掉。

### 1.4 假设的窄问题形式

需要研究的不是"某条记忆当前有没有帮助"，而是：

> 在给定作用域和目标策略下，改变既有记忆的**持久访问状态**，对未来候选流、共同暴露、行动、结果、后续学习和治理成本产生的累计价值，是否能够被历史日志或 query-local intervention 识别？若不能，需要哪些最小的观测和干预条件？

这个问题的独特交叉点由四个要素共同定义：

1. **treatment** 是 persistent access action，而不是一次 prompt insertion；
2. **exposure** 由当前 policy 生成，且随时间变化；
3. **treatment** 会改变未来 candidate stream 和后续 policy feedback；
4. **目标** 是 lifecycle policy value，而不是单次回答分差。

只有这四个要素同时进入正式模型，Gap 1 才不是将一般 causal/OPE 问题换一种术语。

---

## 2. 阶段 A：Estimand 形式化

> 出口标准：estimand 在数学上可写、可区分、可审计。完成后方可进入阶段 B。

### 2.1 作用域

作用域 $(s)$ 不是一个模糊标签，而应至少包含：

```text
s = (task distribution, user/principal, tool set, model/version,
     risk regime, reader, evaluator, memory budget, target policy)
```

source scope $(s)$ 表示形成 qualification 的历史环境；target scope $(s^*)$ 表示要部署或评估的未来环境。若模型版本、工具或 evaluator 发生改变，必须明确它们属于 scope shift，而不能继续使用同一个平均效应。

### 2.2 处理单元与状态

处理单元需要在论文中固定。候选选择包括：

- raw memory item；
- evidence-anchored relation；
- memory 的 persistent access state。

SQCAD 的理论对象应优先选择"记忆 $(i)$ 的持久访问状态"，因为只有这样才能表达 protect、downweight、isolate、archive 和 restore 对未来 candidate stream 的影响。raw memory 是证据载体，relation belief 是派生信念，二者不能直接代替 treatment。

### 2.3 持久访问 treatment

定义：

$$
A_{i}^{\mathrm{pers}}
\in \mathcal A
=\{\text{keep},\text{downweight},\text{isolate},\text{archive},\text{restore}\}.

$$

需要明确 action 的生效时刻、持续时间、是否可撤回、是否影响 candidate generation、是否改变 workspace budget，以及多个 memory action 是否相互竞争。

一次 query 中的加入/移除属于局部 exposure treatment：

$$
E_{i,t}\in\{0,1\}.

$$

它可以是生命周期模型中的中介变量或局部子实验，但不能直接冒充 $A_i^{\mathrm{pers}}$。

### 2.4 生命周期价值

在作用域 $(s)$、目标策略 $\pi$、时间窗口 $(H)$ 和折扣因子 $\gamma$ 下，定义：

$$
V_s^\pi(a)
=
\mathbb E^{\pi}
\left[
\sum_{t=1}^{H}\gamma^{t-1}
\bigl(Y_t-\lambda C_t-\rho R_t\bigr)
\;\middle|\;
do(A_i^{\mathrm{pers}}=a),s
\right].

$$

其中：

- $Y_t$：任务或行动效用；
- $C_t$：token、延迟、probe、人工 review 或恢复成本；
- $R_t$：风险或危害项；
- $\lambda,\rho$：预注册的成本和风险权重；
- $H$：生命周期评估窗口。

针对两个持久动作的比较为：

$$
\tau_s^\pi(a_1,a_0)=V_s^\pi(a_1)-V_s^\pi(a_0).

$$

这个 estimand 不是"更复杂的 utility score"，而是一个反事实决策量：它回答改变长期访问权是否会使未来轨迹更好。

### 2.5 三种量必须分开

| 量 | 处理 | 固定内容 | 回答的问题 |
| --- | --- | --- | --- |
| 历史关联价值 | exposure 与 outcome 的共现 | 历史 policy | 被检索后通常是否伴随成功 |
| query-local intervention effect | 当前 prompt 加入/移除记忆 | query、候选集、模型和 evaluator | 这条记忆对当前回答是否有即时作用 |
| persistent-access lifecycle value | 改变长期 access state | 未来内容由 policy 重新生成 | 允许该记忆持续访问是否改善未来轨迹 |

前两者可以作为 lifecycle value 的证据或中介，但不能自动识别第三者。

---

## 3. 阶段 B：不可识别性与必要性证明

> 出口标准：至少 Theorem 1 和 Theorem 2 的构造性反例成立。若反例构造失败，立即收缩 Gap 并回到阶段 A 重新定义 estimand。

### 3.1 不可识别性不是"存在内生性"的口头说法

设历史可观测数据为：

$$
O_{1:H}=\{C_t,X_t,E_t,P_t,D_t,A_t,Y_t,c_t\}_{t=1}^{H},

$$

其中 $C_t$ 为 candidate stream，$X_t$ 为任务、用户、工具和模型状态，$E_t$ 为 exposure，$P_t$ 为位置/预算，$D_t$ 为 adoption 的可观测代理，$A_t$ 为行动，$Y_t$ 为 outcome，$c_t$ 为成本。

如果存在两个结构模型 $M_1,M_2$，满足：

$$
P_{M_1}(O_{1:H})=P_{M_2}(O_{1:H}),

$$

但：

$$
V_{s,M_1}^\pi(a)\neq V_{s,M_2}^\pi(a),

$$

则 $V_s^\pi(a)$ 在该观测信息集合下不可识别。

证明重点应是构造"日志相同、干预后未来不同"的两个世界。例如：

- 世界 A：高成功共现的记忆是真正有用的；
- 世界 B：同一记忆只是被有利任务和另一条真正有用的 memory 共同暴露；
- 当前 policy 产生相同的历史 candidate/exposure/outcome 分布；
- 一旦 archive 该 memory，两个世界的未来 recurrence、action 和 regret 不同。

这将"策略生成的数据存在内生性"转化为一个可检验的 impossibility claim。

> ⚠ **分支点 B1**：如果无法构造出 observationally equivalent 但 lifecycle value 不同的两个世界，说明在给定日志信息集合下，persistent-access value 可能已被识别。此时应重新检查日志中包含的信息是否比我们假设的更丰富，并相应收缩 Gap。

### 3.2 query-local causal effect 仍然不够

CMI 类方法可以估计：

$$
\Delta_t(i)
=
\mathbb E[Y_t\mid do(E_{i,t}=1)]
-
\mathbb E[Y_t\mid do(E_{i,t}=0)].

$$

即使 $\Delta_t(i)$ 被无偏估计，也不能推出：

$$
V_s^\pi(\text{archive})
-
V_s^\pi(\text{keep}).

$$

需要通过一个反例或分解说明：局部干预固定了当前 candidate/query，而持久干预改变未来 candidate stream、co-memory composition、policy update 和后续任务。因此 Gap 1 不是否定 CMI，而是证明其 estimand 对 lifecycle decision 不充分。

> ⚠ **分支点 B2**：如果存在一个从 $\{\Delta_t(i)\}$ 到 $V_s^\pi(a)$ 的通用映射（即使在特定条件下），则局部效应足以支撑 lifecycle decision。Gap 1 缩小为"需要显式写出这个映射的条件"，而非"存在理论空白"。

### 3.3 笼统作用域平均也不够

定义作用域异质效应：

$$
\tau(s)=V_s^\pi(a_1)-V_s^\pi(a_0).

$$

历史总体平均：

$$
\mathbb E_{s\sim P_{\mathrm{source}}}[\tau(s)]

$$

一般不能替代目标作用域 $s^*$ 的：

$$
\tau(s^*).

$$

可构造 source 平均效应为零，但 target scope 中效应显著为正或为负的例子。这说明"估计了某个因果效应"仍然不等于"获得了未来记忆治理的可用证据"。

### 3.4 多记忆竞争不能默认可加

在固定 workspace budget 下，提高记忆 $(i)$ 的访问质量会降低其他候选的访问质量。于是：

$$
V(a_i=1,a_j=1)-V(a_i=0,a_j=0)
\neq
\tau_i+\tau_j

$$

一般成立。理论工作需要选择一种明确处理方式：

- 定义 joint treatment；
- 定义在固定 coalition 下的 conditional effect；
- 给出上下界；
- 或承认单记忆 effect 在竞争性预算下不可独立识别。

不能在理论上使用单记忆 ATE，在系统中却执行相互排斥的 top-k 访问。

---

## 4. 阶段 B（续）：证明这个量有决策意义

> 仅有不可识别性还不够——需要证明忽略 $V_s^\pi$ 会导致实际治理错误。

定义风险和成本约束下的访问决策：

$$
a^\star
=
\arg\max_{a\in\mathcal A}
\left\{
V_s^\pi(a)-\lambda C(a)-\rho R(a)
\right\}.

$$

若系统使用历史关联、query-local effect 或笼统 scope 平均值形成 $\hat a$，则决策遗憾为：

$$
\mathrm{Regret}_s
=
V_s^\pi(a^\star)-V_s^\pi(\hat a).

$$

需要证明或构造至少一类环境，使得：

- association 推荐 archive，但 lifecycle value 推荐 keep；
- query-local effect 推荐 keep，但长期 co-memory feedback 推荐 downweight；
- source-scope 平均值推荐 archive，但 target scope 中 rare protective memory 应被保留；
- 贸然行动的期望损失高于 abstain 或额外 probe 的成本。

这样才能证明 $V_s^\pi$ 不是人为增加复杂度，而是对访问治理具有不可替代的决策信息。论文不必声称该量在所有环境中提高 utility；应声称忽略它在某些可构造环境中产生严格 regret，因而它是管理问题的必要决策对象。

---

## 5. 阶段 C：从不可识别性反推识别条件

> 出口标准：识别条件列表可操作化，每条条件对应一个可审计的日志字段或实验设计要素。

### 5.1 source-scope 识别条件

至少需要明确讨论：

1. **Consistency**：实际执行的 persistent action 与反事实 action 定义一致；
2. **Sequential exchangeability**：给定完整历史状态、policy state、task state 和 memory state 后，处理分配不再受未观测混杂影响；
3. **Positivity/overlap**：在目标状态下，各候选 persistent action 具有非零支持；
4. **Treatment observability**：access action、持续时间和生效状态被真实记录；
5. **Exposure observability**：candidate、exposure、position、budget 和 reader context 可区分；
6. **Adoption measurement**：模型是否使用 memory 不能简单等同于 prompt 出现，必须给出可观测代理、误差模型或不识别边界；
7. **Interference specification**：说明 co-memory 竞争、workspace budget 和共同暴露如何进入 outcome；
8. **Measurement stability**：reader、model、tool、evaluator 版本在 source evaluation window 内固定或显式建模。

> ⚠ **分支点 C1**：如果某些条件（如 adoption measurement 或 sequential exchangeability）在实践中不可满足，不应强制产生点估计。应输出 bound/partial identification，或在无法满足时输出 `unresolved`。

### 5.2 需要哪些额外干预

当 observational logs 不满足 exchangeability 或 positivity 时，需要低风险随机 micro-intervention，例如在安全候选中随机执行 protect/downweight 或短时 isolate，以获得外部 treatment variation。干预必须记录：

- 随机化概率；
- eligible candidate set；
- action 生效时间和持续窗口；
- 共同暴露和预算位置；
- downstream action/outcome；
- intervention cost 与 rollback。

若实验只强制把记忆加入 prompt，而没有改变未来 persistent access state，则只能支持 query-local claim，不能支持 lifecycle claim。

### 5.3 不能识别时的输出

理论上，无法满足条件时不应强制产生连续价值分数。应允许输出：

- point identification；
- interval/bound identification；
- unresolved/abstention。

`unresolved` 的语义是"没有权限改变持久访问权"，不是"记忆价值为零"或"记忆有害"。

---

## 6. 阶段 C（续）：作用域迁移与 Bayesian 价值估计的位置

source-scope 的 lifecycle value 与 target-scope 的决策应分开：

$$
V_{s^*}^\pi(a\mid D_s)
=
\int V_{s^*}^\pi(a;\theta)
p(\theta\mid D_s)\,d\theta .

$$

这个 posterior-predictive quantity 属于 transport 和 decision 层。它需要额外说明：

- target scope 是否落在 source support 内；
- 哪些机制跨 scope 保持不变；
- treatment effect 是否可迁移；
- scope shift 是否改变 reader、evaluator 或 outcome measurement；
- Bayesian posterior 的先验和结构假设是什么。

重要边界：Bayesian posterior 不能自动解决因果不可识别性。如果历史日志对两个结构模型同样兼容，posterior predictive 仍依赖先验和结构假设，不能写成"仅由数据识别出的未来因果价值"。

因此理论顺序应是：

```text
source-scope identification
        → target-scope transport assumptions
        → posterior uncertainty / value of information
        → risk-sensitive access decision
```

> ⚠ **分支点 C2**：若 source-scope identification 本身就不完整，Bayesian transport 层不能弥补这一缺陷。scope transport 的条件是否成立，决定了 Gap 2 是需要独立的理论处理，还是可以作为 Gap 1 的推论。

---

## 7. 阶段 D：从识别条件推导框架

> 出口标准：框架的每个组件都能追溯到阶段 C 的某个识别条件或阶段 B 的某个决策必要条件。若追溯链断裂，该组件应被移除或标记为工程选择而非理论要求。

### 7.1 推导逻辑

SQCAD 的 Evidence–Qualification–Access 三层结构不是先验的架构选择，而是从阶段 B–C 的条件中推导出来的：

| 框架组件 | 推导来源 | 理论依据 |
| --- | --- | --- |
| **Evidence 层**（不可变来源记录 + provenance） | 识别条件 4–6（treatment/exposure/adoption observability） | 若日志不可重建反事实路径，识别条件不可审计 |
| **Qualification 层**（scope/version 条件下的资格判断） | 识别条件 1–3, 7–8（consistency, exchangeability, positivity, interference, stability） | 决定证据是否满足作用域下的识别和决策门槛 |
| **Access 层**（固定预算内的动作执行） | §4 的决策遗憾构造 + §3.4 的多记忆竞争 | 在竞争预算下分配访问质量；不能反过来伪造 qualification evidence |

推导链：

```text
识别条件要求记录 candidate → exposure → adoption → action → outcome → governance action → next candidate
        ↓
Evidence 层 = 该链条的不可变记录
        ↓
识别条件在给定 scope 下可能满足也可能不满足
        ↓
Qualification 层 = 逐 scope 判断是否满足门槛
        ↓
满足门槛后，仍需在固定预算和竞争环境下做决策
        ↓
Access 层 = 接收 qualification + 风险 + 成本 + interference，执行动作
```

### 7.2 Evidence 层

保存 immutable source、provenance、scope、version、candidate generation、exposure、intervention 和 outcome 记录。它不直接决定长期访问，也不被派生 belief 覆盖。

### 7.3 Qualification 层

从"给记忆打正负分"升级为"判断证据是否满足作用域下的识别和决策门槛"：

$$
Q_i(s)\in\{positive,negative,unresolved,mismatch\}.

$$

正向或负向 qualification 必须关联 treatment definition、scope、overlap、干预证据和 calibration；`unresolved` 表示缺乏改变 persistent access 的权限。

### 7.4 Access 层

在固定 workspace budget 下分配访问质量。必须接收 qualification、风险、成本和 interference 信息，执行 keep、downweight、isolate、archive 或 restore。Access policy 不能反过来伪造 qualification evidence。

### 7.5 框架修改分支表

> ⚠ **分支点 D1 — Qualification gate 的设计空间**：
>
> 当前设计：$Q_i(s)$ 输出四类离散状态，只有 `positive` 或 `negative` 允许改变 persistent access。
>
> 备选方案：
> - 若 Theorem 3 的识别条件在实践中过于严格，gate 可改为连续 confidence score + 阈值
> - 若 `unresolved` 输出过多导致系统无法做任何决策，可增加 "probationary access" 中间状态
> - 若实验显示简单的 local audit 已足够减少 false forgetting，qualification 可降级为 audit-only
>
> ⚠ **分支点 D2 — Access 层的设计空间**：
>
> 当前设计：Access 在固定 budget 下做 top-k 选择，各记忆独立评分。
>
> 备选方案：
> - 若 Theorem 5 严格证明不可加性 → 改为 coalitional access（joint treatment over memory groups）
> - 若 budget 约束在实践中不紧 → 简化为 threshold-based access（超过门槛即保留）
> - 若 competitive interference 效应小 → 保留 per-memory scoring，但加入 post-hoc fairness check
>
> ⚠ **分支点 D3 — 三层是否必要**：
>
> 若实验显示三层分离增加了工程 overhead 但未产生决策收益：
> - Evidence 层可合并到日志系统（不单独作为框架组件）
> - Qualification 与 Access 可合并为单一 risk-sensitive policy
> - 三层结构的必要性本身就是一个可检验的假设

### 7.6 日志必须能重建反事实评估所需路径

最小可执行链条是：

```text
candidate generation
→ proposal score
→ exposure propensity
→ position / budget
→ adoption proxy
→ action
→ outcome / risk / cost
→ governance action
→ next candidate stream
```

如果 adoption 无法观测，框架必须公开代理定义和测量误差，而不是把"出现在 prompt 中"写成"产生了处理作用"。

---

## 8. 阶段 D（续）：证明成功后框架如何落位到决策

有了点估计、区间或 posterior 后，定义访问动作：

$$
a^\star
=
\arg\max_{a\in\mathcal A}
\left[
\widehat V_s^\pi(a)
-\lambda \widehat C(a)
-\rho \widehat R(a)
\right],

$$

但只有在识别和不确定性门成立时才允许改变 persistent access。否则：

- 点识别充分且风险可接受：允许 qualified action；
- 只有区间且动作排序稳定：允许保守动作或受限访问；
- 区间跨越决策阈值：执行额外 probe 或 review；
- overlap/measurement/transport 不成立：输出 `unresolved`，保持可撤回的当前任务访问，不改变长期权限。

这使 qualification gate 成为理论结果的决策推论，而不是一个事后添加的工程模块。

---

## 9. 定理候选与优先级

以下是下一阶段应优先尝试的理论结果，不代表已经成立。

### Theorem candidate 1：Observational non-identifiability

在只观测历史 candidate、exposure 和 outcome，且 persistent access 改变未来 candidate transition 的设置下，存在 observationally equivalent 的结构模型，其 lifecycle value 不同。因此 $V_s^\pi(a)$ 不可由该日志集合点识别。

### Theorem candidate 2：Local intervention insufficiency

即使所有 query-local intervention effect $\Delta_t(i)$ 均已知，只要 persistent action 会改变未来 candidate transition、co-memory composition 或 policy update，仍不存在从 $\{\Delta_t(i)\}$ 到 $V_s^\pi(a)$ 的一般无假设映射。

### Theorem candidate 3：Identification with micro-intervention

在 consistency、sequential exchangeability、positivity、treatment/adoption observability、interference specification 和 measurement stability 成立，并加入有记录的 randomized micro-intervention 后，lifecycle value 可由序贯 g-formula、MSM、DR/OPE 或相应的 memory-specific estimator 识别。

### Theorem candidate 4：Scope transport limitation

若 target scope 的状态分布超出 source support，或 scope shift 改变 treatment-response mechanism，则 source-scope value 不能无条件 transport；在给定 overlap 和 invariant-mechanism 假设下只能得到条件化的 target value 或界。

### Theorem candidate 5：Competitive interference

在固定 workspace budget 和共同 candidate pool 下，单记忆 treatment effect 一般依赖其他被访问记忆和 budget allocation；因此 additive per-memory value 不是一般成立的 estimand，必须使用 joint/conditional treatment、coalitional value 或界。

### 优先级与分支策略

```text
优先：Theorem 1 + Theorem 2
  ├─ 两者均成立 → 继续 Theorem 3（主理论贡献）
  ├─ Theorem 1 失败 → 收缩 Gap，重新检查日志信息集合
  ├─ Theorem 2 失败 → Gap 1 缩小为 engineering gap
  └─ 两者均失败 → 重新定义 estimand（回到阶段 A）

次优先：Theorem 3（若 1+2 成立）
  ├─ 成立 → 主理论贡献确立
  └─ 部分成立（需要更强条件）→ 以 bound/partial ID 作为理论输出

边界结果：Theorem 4 + Theorem 5
  └─ 避免论文一开始承担过大的理论范围；
      可作为 "extensions" 或 "limitations" 放入讨论
```

---

## 10. 验证闭环

### 10.1 理论反例

构造至少两个历史日志分布相同、但 archive/keep 后未来轨迹不同的世界，验证 Theorem candidate 1。

### 10.2 局部效应反例

构造 current-query local effect 相同、但 persistent rollout value 相反的世界，验证 Theorem candidate 2。

### 10.3 识别实验

加入预注册的 randomized low-risk micro-intervention，记录 propensity、candidate pool、共同暴露、adoption proxy 和 downstream outcome，验证识别协议能恢复已知或可审计的反事实差异。

**状态（2026-08-12）**：两阶段实验完成——Stage 1 理想环境验证恢复（bias≈0、CI 诚实 0.97±0.05、自信错误 0、unresolved 恰为 neutral）；Stage 2 五种违反（C6/C7/C3/C8/Cor1）全部被 gate 捕获为 unresolved/mismatch。实现与数字见 `实验证据链/03-识别恢复实验报告-20260812.md`。**尚未验证**：观测路径（sequential g-formula/DR）、部分识别界、chronological future rollout。

### 10.4 未来策略 rollout

source period 只形成 qualification；冻结规则后进入 chronological future period，真实改变 persistent access，比较 future candidate stream、累计 utility、false-forgetting regret、harmful retention、active tokens、probe/review cost。

### 10.5 强基线

至少包括 keep-all、fixed decay、Memory Worth、FadeMem/Oblivion、CMI-style local audit、review-only 或 conservative keep。所有基线共享 reader、candidate stream、budget、model、tool 和 evaluator。

---

## 11. 论文主张的升级阶梯

| 阶段 | 可以声称 | 不能声称 | 当前状态 |
| --- | --- | --- | --- |
| 文献+直觉 | 提出 memory-specific lifecycle identification problem | 已证明理论空白 | ✅ 已完成 |
| 有定义与构造性反例 | A formally counterexample-grounded, memory-specific identification gap | 已证明现实系统中普遍成立；不可识别性定理已形式化 | ✅ **当前所处阶段** |
| 有形式化不可识别性定理 | 正式的 observational non-identifiability theorem | 已证明跨 scope 泛化 | ⬜ 待完成 |
| 有识别定理 | 给出最小日志、overlap 和干预条件下的 identification formula，且协议路径在理想环境恢复已知值、条件违反时门控弃权 | 已证明所有条件下均可识别；观测路径已验证 | 🔶 定理已写、Stage 1/2 已验（协议路径） |
| 有决策反例 | 证明忽略 lifecycle value 导致治理 regret | 已证明平均 utility 普遍提升 | ✅ 已完成 |
| 有 future rollout | 证明协议在特定真实系统中有效 | SOTA、普适最优、无条件 transport | ⬜ 待完成 |
| 有 transport/bound 理论 | 建立作用域条件下的 memory lifecycle decision theory | 任意新任务和模型都可迁移 | ⬜ 待完成 |

---

## 12. 当前 SQCAD 的准确定位

### 12.1 可以说的

> SQCAD 通过三个构造性反例（观测等价 SCM、等 do-effect 相反 lifecycle、source-equivalent 不同 target）建立了 persistent-access lifecycle value 的识别空白。当前 Gap 定位为：
>
> **A formally counterexample-grounded, memory-specific identification gap for persistent-access lifecycle value.**
>
> 一个通过观测等价模型和决策遗憾反例建立的、面向持久记忆访问生命周期价值的识别空白。
>
> 不可识别性一侧已基本立住；可识别性一侧：Theorem 3 v2 给出充分可审计授权条件（原称 minimal conditions，必要性证明后更名，见 `12-必要性证明与识别路线分类学`）与双路估计公式，**协议路径（随机化持久动作 rollout）在理想合成环境中恢复了已知生命周期值**（bias=−0.47、CI 覆盖 12/12、自信错误 0、unresolved 恰为 neutral，5 seeds 稳定），**五种条件违反（C6/C7/C3/C8/Cor1）全部被 Qualification gate 捕获为 unresolved/mismatch**。SQCAD 的 Evidence–Qualification–Access 框架从识别条件直接导出（详见 `10-识别条件到框架设计的形式化推导.md`），而非先验架构选择。

### 12.2 不能说的

- "我们已经建立完整的 Agent Memory 基础因果理论"
- "不可识别性定理已经形式化证明"
- "识别定理已经完成"——观测路径（g-formula/DR）与部分识别界未实现未验证，识别仅在合成理想环境的协议路径上被验证
- "SQCAD 已改善真实 Agent Memory 治理"——尚无 chronological future rollout / 真实数据验证
- "所有 OPE/MSM 方法都无法完成作用域迁移"

### 12.3 当前最准确的一句话

> A counterexample-grounded, memory-specific identification gap that derives an auditable governance protocol from explicit non-identifiability constructions and minimal identification assumptions — with the identification theorem stated and its protocol route verified in an ideal synthetic environment, the observational route and real-world rollout still open.

---

## 13. 下一步工作顺序

### 13.1 已完成（不可识别性一侧）

- [x] 第 1 步：固定最小状态变量和 notation（已在 `gap_proof_experiments.py` 中完成）
- [x] 第 2–3 步：构造三个命题的反例（命题 A/B/C 全部通过，20/20 seeds 稳定）
- [x] 第 4 步：决策 regret 反例（所有 $\operatorname{regret} > 0$）
- [x] 第 5 步：从反例提取识别条件（9 条，见 `IDENTIFICATION_CONDITIONS`）
- [x] 第 6 步（部分）：识别条件 → 框架设计的推导链（见 `10-识别条件到框架设计的形式化推导.md`）

### 13.2 可识别性一侧

**第 7 步：将反例形式化为定理** ✅ 已完成
- 命题 A → observational non-identifiability theorem（Theorem 1）
- 命题 B → local intervention insufficiency theorem（Theorem 2）
- 命题 C → scope transport limitation theorem（Corollary，见 `11-形式化定理陈述与证明.md`）

**第 8 步：证明 identification theorem** 🔶 定理已写、协议路径已实验验证
- 核心问题：在什么最小条件下，$V_s^\pi(a)$ 可由日志和 micro-intervention 识别？
- 输出：observable identification formula 或 partial-identification bound
- 状态：Theorem 3 v2 已写出（决策期模型 + 双路估计器 + Qualification 门控）；**Stage 1 通过**（协议路径恢复已知值，5 seeds 稳定），**Stage 2 五种违反全部被 gate 捕获**（见 `实验证据链/03-识别恢复实验报告-20260812.md`）
- 剩余：观测路径（sequential g-formula/DR）实现与验证；C6/C7 失败时的部分识别界

**第 9 步：完成识别条件 → 框架的逐条实现**
- 每条识别条件对应一个框架组件（见 `10` 的 §2）
- 如果某条条件没有被框架实现，理论主张不能落地
- 如果某个框架组件无法追溯到条件，标记为工程选择
- 下一步解锁：chronological future rollout（Stage 1 已通过，比较 keep-all / fixed decay / Memory Worth / CMI / naive OPE / SQCAD）

### 13.3 后续（框架与实验）

**第 10 步：实现 SQCAD logging / intervention protocol**
**第 11 步：source-scope 识别实验 + future policy rollout**
**第 12 步：强基线比较（keep-all, Memory Worth, CMI, fixed decay）**

### 13.4 贯穿始终的约束

- 每个框架模块必须可追溯到某个不可识别性反例或识别条件
- 不在没有定理和反例前使用 "fundamental theoretical gap" 作为确定性结论
- Introduction 当前可写 "counterexample-grounded identification gap"，不能写 "fundamental theoretical gap proved"

---

## 14. 研究过程中必须保持的边界

- 不把 Bayesian posterior 当作自动的因果识别；
- 不把 query-local CMI effect 当作 lifecycle policy value；
- 不把 candidate 出现在 prompt 中当作 adoption 已被观测；
- 不把 unresolved 当作 negative value；
- 不把受控潜在结果实验当作真实 Agent Memory benchmark；
- 不把一般 OPE/MSM 的存在写成 SQCAD 的理论创新；
- 不把"文献尚未覆盖该交叉点"写成"所有先验理论都无法解决"；
- 不在没有定理和反例前使用"基础理论空白"作为确定性结论。

---

## 15. 一句话研究逻辑

> 当前我们已通过三个构造性反例（观测等价 SCM、等 do-effect 相反 lifecycle、source-equivalent 不同 target）将 Gap 建立为 **counterexample-grounded memory-specific identification gap**。不可识别性一侧基本立住；下一步集中证明"在什么最小条件下该量可由日志和 micro-intervention 识别"，并由识别条件直接导出 SQCAD 的 Evidence–Qualification–Access 框架——每个组件必须追溯到某个反例或条件，否则标记为工程选择。**在 identification theorem 完成前，不能声称"基础理论空白已被证明"。**
