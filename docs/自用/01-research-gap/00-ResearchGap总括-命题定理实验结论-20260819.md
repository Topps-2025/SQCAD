# SQCAD Research Gap 总括：假设、命题、定理与实验结论

> 本文是 `01-research-gap` 的总括入口。它回答一条完整的问题：**我们最初提出了什么 Research Gap 假设？把它形式化成了哪些命题和定理？为每个命题设计了什么实验、为什么这样设计、结果是什么？最终哪些结论成立，哪些仍不能声称？**
>
> 文件职责：正式定理和证明仍在 `研究逻辑与理论证明/`；实验数值和复现细节仍在 `../03-实验证据链/`；本文只负责把两者按论证顺序接起来。当前已完成结论以证据链报告为准，历史路线文件不作为最新结果来源。

## 1. Research Gap 假设从哪里来

### 1.1 初始研究假设

现有 Agent Memory 方法常用历史关联、查询相关性、访问频率、时间衰减、结果反馈、query-local 干预或决策压缩来决定记忆的写入、检索或压缩。但 SQCAD 关心的不是一次查询是否命中，而是：

$$
\tau_s^\pi(i)
=V_s^\pi(\operatorname{keep}_i)-V_s^\pi(\operatorname{archive}_i),
$$

即在未来任务分布、候选生成、暴露顺序、预算竞争、共同记忆干扰、作用域/版本变化和成本都被纳入时，一条记忆的**持久访问动作**是否有长期价值。

因此最初的 Research Gap 假设是：

> 历史关联、固定 query-local 因果效应和 source-scope 平均效应，可能都不足以授权逐记忆的持久 `keep/archive` 决策；缺少的不是一个更复杂的排序分数，而是 lifecycle value 的识别与授权层。

这个阶段只是文献驱动的假设，不是“所有现有工作都无法解决”的结论。相关覆盖审计和历史形成过程见[历史路线文件](../02-历史草稿/研究路线与方案/08-Gap1覆盖审计与框架设计重点-20260811.md)和[从直觉 Gap 到理论空白](../02-历史草稿/研究路线与方案/09-从研究直觉Gap到理论空白-研究逻辑与下一步工作.md)。

### 1.2 三个必须分开的 estimand

| Estimand | 代表性方法/信号 | 它回答什么 | 为什么不能直接当作 SQCAD 目标 |
|---|---|---|---|
| historical association | Memory Worth 类共现/成功率 | 过去一起暴露时是否一起带来成功 | 不能区分“真正有用”和被一起暴露的 hitchhiker |
| query-local intervention effect | CMI 类 `with-memory - no-memory` | 当前查询中加入该记忆的局部影响 | 不包含后续候选、预算、共同记忆和生命周期反馈 |
| persistent-access lifecycle value | SQCAD `keep - archive` | 持久动作改变未来整个决策期的净价值 | 是本文真正的 treatment–outcome 目标 |

## 2. 从 Gap 假设到可证伪命题

### 2.1 命题 A：观测关联不能一般识别生命周期价值

**设计。** 构造两个世界 `M1/M2`，让完整公开观测日志的联合分布完全相同，但把隐藏的长期需要关系翻转。两个世界都给基线同样的信息，避免把失败归因于基线没有看到关键字段。

**实验为什么这样设计。** 如果两个世界的 `P(O)` 完全相同，而最优持久动作相反，那么任何只依赖该观测日志的关联规则都必须在至少一个世界中犯错。这直接检验的是 information/estimand 层，而不是某个实现的参数质量。

**结果。** `max_field_diff=0`；构造实例中生命周期差异约为 `+1650` 与 `−1100`，Memory Worth 型规则在负值世界的 regret 为 `1100`。完整记录见[Gap 证明实验报告](../03-实验证据链/01-Gap证明实验报告-v2-20260812.md)和[公平性审查](../03-实验证据链/02-Gap实验公平性审查-20260812.md)。

**证明内容。** 这支持 Theorem 1：persistent-access lifecycle value 存在 observational non-identifiability。它不证明所有关联方法在所有数据上都失败，只证明在包含该观测等价对的模型类上，不存在对所有世界都正确的纯观测 committing rule。

### 2.2 命题 B：query-local 正确因果效应仍不足以决定生命周期动作

**设计。** 对两条记忆施加真实的 `do` 干预，令它们的 query-local effect 都精确等于 `2.000`，但分别改变后续任务、候选竞争和预算拥挤。

**实验为什么这样设计。** 这样可以排除“CMI 只是估计不准”的反驳：即使 local causal effect 已经无偏且精确，若它和 lifecycle value 仍然符号相反，失败原因就是 estimand 不匹配。

**结果。** 一条记忆的 lifecycle value 约为 `−1784`，另一条约为 `+1776`；两者 local effect 仍相同。CMI/naive OPE 型规则在负生命周期记忆上产生约 `1784` 的 regret。

**证明内容。** 这支持 Theorem 2：query-local intervention effect 不一般识别 persistent-access lifecycle value。它不是否定局部因果估计，而是限定它的作用范围。

### 2.3 命题 C：source-scope 平均不能自动迁移到 target lifecycle decision

**设计。** 保持 source 数据和 source 平均效应相同，改变 target scope 或 target mechanism，使同一条记忆在目标作用域中的长期价值发生变化。

**实验为什么这样设计。** 这直接检验 scope transport，而不是把 source 期的统计规律默认当成 target 期的决策证据。

**结果。** source 观测无法唯一确定 target 的最优动作；错误迁移会产生正的 target regret。具体构造与边界见[形式化定理](研究逻辑与理论证明/11-形式化定理陈述与证明.md) §4 和[最接近工作全文核对](../03-实验证据链/10-最接近工作全文级核对与因果文献定位-20260813.md)。

**证明内容。** 这形成 Corollary 1：scope transport 需要额外稳定性、支持或机制假设，不能由 source 平均自动授权 target 的持久动作。

## 3. Gap 形式化后得到的定理

| 理论对象 | 从哪个问题导出 | 定理/命题回答什么 | 实验验证状态 |
|---|---|---|---|
| Theorem 1 | 命题 A | 观测等价世界可以有相反 lifecycle 最优动作 | 构造性证明 + 代码验证通过 |
| Theorem 2 | 命题 B | local intervention effect 可以相同而 lifecycle value 符号相反 | 构造性证明 + 代码验证通过 |
| Theorem 3 | “如果 gap 存在，什么条件下能恢复？” | C1–C8 是一组可操作、可审计的充分识别与治理授权条件；协议路径可恢复，失败时输出 `unresolved/mismatch` | Stage 1/2 验证协议路径和 gate；观测 g-formula/完整 lifecycle DR 仍未闭环 |
| Corollary 1 | 命题 C | source-scope value 不自动 transport 到 target scope | 构造性证明 + scope violation 实验 |
| Theorem 4 | “未识别时能否强制二选一？” | 未识别类上 committing rule 的最坏情况错误概率至少 `1/2`、regret 有下界；低于下界必须 probe 或 defer | 证明 + `660` 数值验证 |
| Theorem 5 | Theorem 4 的一般化 | 安全提交当且仅当识别集合不跨动作边界；跨零时使用 minimax regret，而不是随机硬提交 | 完整证明 + 计算验证 |

### 3.1 T1：self-obscuring lifecycle theorem

T1 把命题 A 的“信息看不到”进一步变成长期动态代价：持久 archive 会减少未来证据可得性，错误提交会自我强化。

- 无恢复提交策略的 regret 为 `Theta(T)`，无恢复斜率在当前构造中精确为 `5.8500`；
- 具备 restore/probe 的策略把 regret 变成与恢复速率相关的有限平台，实验值约为 `0.4250 / 0.2937 / 0.0000`（策略不同）；
- 当候选支持独立于持久动作时，线性下界消失，说明真正关键的是 action-dependent evidence availability。

### 3.2 T2：reduction separation

T2 进一步检验能否把问题忠实化约成普通 bandit/OPE，而不显式记录证据可得性状态。

- 任何满足动作、即时 reward、观测信息和反馈保真条件的 reduction，都保留 self-obscuring 的线性 regret；
- 配对 regret 恒等式逐点为 `11700.0`，最大 regret 下界为其一半 `5850.0`；
- 只有显式增加 evidence-availability/restore 状态，才可能打破该分离。

### 3.3 P4：探测复杂度下界

P4 检验“增加 probe 是否免费”。区分 `+tau` 和 `-tau` 两个世界时，任何错误率不超过 `delta` 的探测过程需要至少 `log(1/delta)/KL` 级别的观测；数值中 `U=800` 与理论量级约 `850.2` 接近。结论是 probe 必须按信息价值和生命周期代价共同定价，而不是单纯增加检索次数。

## 4. 为定理设计的识别与门控实验

### 4.1 Theorem 3 Stage 1：理想识别环境

**设计。** 随机化 `keep/archive`，固定未来 rollout horizon、策略和成本合同，使用独立 RNG 的 oracle 与估计器；这样能直接测协议路径是否恢复已知 lifecycle value。

**结果。** 聚合 bias `−0.47`，CI 覆盖 `12/12`，自信错误 `0`，`unresolved` 恰为 3 个 neutral；short-term 记忆即使 local effect 为正，也被正确 archive。详见[识别恢复实验](../03-实验证据链/03-识别恢复实验报告-20260812.md)。

**证明内容。** 只支持“C1–C8 满足时，协议路径在当前合成世界可恢复 lifecycle value”，不支持完整观测路径已经验证。

### 4.2 Theorem 3 Stage 2：条件违反与 Qualification gate

**设计。** 逐一制造 adoption error、co-exposure、eligibility/support 缺失、measurement drift 和 scope transport violation；同时运行 gate 和盲于 gate 的强制提交对照。

**结果。** 五类违反都被 gate 标记为 `unresolved` 或 `mismatch`；强制版本在 co-exposure 和 eligibility 下分别出现约 `41.0` 与 `83.4` 的结构性 regret。

**证明内容。** Qualification 不是普通置信度阈值，而是把“没有资格授权”的状态显式化。它证明的是失败检测和保守退守，不是零成本或所有情况下零错误。

### 4.3 Theorem 4/5：决策识别和门控必要性

**设计。** 使用 Theorem 1 的相同观测、相反最优动作世界，令 committing rule 只能以概率 `p` 选择 keep；再与 `unresolved` 和 probe 对照。

**结果。** 最优随机提交概率 `p*=0.6`，最坏情况 regret `660`，错误概率下界 `0.5`；输出 `unresolved` 可将决策 regret 降为 0，但延宕成本需要另行计入。

**证明内容。** 在含符号翻转对的未识别类上，门控/探测是最坏情况安全所必需；C1–C8 本身不是唯一路线，IV、bundle、fresh randomization 等额外假设可以缩小识别类。

## 5. Research Gap 最终结论

### 已经证明的结论

1. **Gap 不是纯文献空白。** 在明确的 treatment、observation contract 和 lifecycle estimand 下，命题 A/B/C 构造了可复核的 memory-specific identification gap。
2. **常用替代信号有明确边界。** 历史关联、query-local 因果效应和 source-scope 平均，均不能在一般情况下替代持久访问 lifecycle value。
3. **问题可以被条件化解决。** C1–C8 提供一组可操作、可审计的充分授权条件；Stage 1 支持协议路径恢复，Stage 2 支持失败时退守。
4. **未识别时不能无条件强制提交。** Theorem 4/5 证明，识别集合跨动作边界时，安全路径是获取新证据或拒绝提交；这就是 Qualification/probe/defer 的理论来源。
5. **self-obscuring 是动态反馈问题。** 持久动作会改变未来证据可得性，因此不能简单化约成不带 evidence-availability state 的普通检索或 bandit 问题。

### 仍不能声称的结论

- 不能声称“所有现有 Agent Memory 系统都无法处理该问题”；当前文献审计支持的是估计目标层面的限定缺口。
- 不能声称 C1–C8 是唯一或逐项必要条件；Theorem 4/5 的必要性对象是识别意识、probe/defer 能力和可审计的授权，而不是某一套条件清单。
- 不能把 `660`、`5850` 等构造实例常数直接迁移为真实系统性能界。
- 不能把合成识别实验写成真实 Agent Memory 已完成因果验证；公开轨迹和 LifecycleBench 分别承担外部效度和内部反事实效度，端到端 Phase B 仍是后续工作。
- 不能把理论证明写成 SOTA 结果；它证明的是结构性限制和治理必要性，不是 benchmark 排名。

## 6. 证据导航

| 用途 | 文件 |
|---|---|
| 正式定理与证明 | [11-形式化定理](研究逻辑与理论证明/11-形式化定理陈述与证明.md)、[12-必要性与识别路线](研究逻辑与理论证明/12-必要性证明与识别路线分类学-20260813.md)、[15-T1](研究逻辑与理论证明/15-self-obscuring形式定理与严格证明-20260813.md)、[16-T2/P4](研究逻辑与理论证明/16-T2严格reduction-separation与P4minimax探测下界-20260813.md) |
| Gap 反例与公平性 | [01-Gap 证明](../03-实验证据链/01-Gap证明实验报告-v2-20260812.md)、[02-公平性审查](../03-实验证据链/02-Gap实验公平性审查-20260812.md) |
| 识别恢复与门控 | [03-识别恢复](../03-实验证据链/03-识别恢复实验报告-20260812.md)、[04-估计有效性](../03-实验证据链/04-估计有效性实验报告-20260812.md)、[11-必要性实验](../03-实验证据链/11-必要性证明实验报告-20260813.md)、[12-动态探索](../03-实验证据链/12-决策识别理论与动态探索实验报告-20260813.md) |
| 当前证据链总览 | [03-00 实验报告与当前结论](../03-实验证据链/00-实验报告与当前结论.md) |
