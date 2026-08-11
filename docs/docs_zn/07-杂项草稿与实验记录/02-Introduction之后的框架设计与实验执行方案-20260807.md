---
type: post-introduction-framework-design
status: current-teacher-facing-minimal-design
date: 2026-08-07
language: Chinese
paper_type: algorithmic-method
target_venue: ICLR 2027
intro_source: ../07-Introduction规范稿.md
framework_source: 00-最新版框架完整设计与实验方案.md
formal_evidence: 实验资产/最小框架挑战实验/最小框架挑战正式实验报告-v3.md
---

# Introduction 之后的框架设计与实验执行方案

> 本文件面向老师审阅。Introduction 按当前要求保持定稿；后续框架已根据正式反例和单模块消融重新收缩。这里完整解释 Method、数据获取、基线、消融、执行顺序和停止条件，不把尚未通过实验的组件包装为创新。

> **版本提示（2026-08-07 后续更新）：** 本文件解释的是已有正式实验支撑的 v3。针对“相关不等于因果、现在不等于未来、这个不等于那个”的候选 v4 已单独形成 `04-贝叶斯作用域迁移门控与非对称访问动态设计提案-20260807.md`。v4 继承本文件删除复杂解构、删除重复预算模块和 Evidence/Belief/Access 分离的裁决，但新增的未来价值后验、transport gate、default-cold 和非对称后验损失均待正式消融。

## 0. 本轮最重要的修改

原方案是“任务解构—层级重组—统一 VOI 预算—组到项反事实搜索—资格化—可恢复衰减”的 12/13 阶段框架。正式 v3 表明：

- item causal probe 当前净效用显著为负；
- hierarchy 增加成本并降低效用；
- adaptive budget cap 被 EVSI stop 完全覆盖；
- sentinel correction 退化；
- recovery 几乎不触发，不能作为性能贡献；
- 只有 **qualification-gated access governance** 获得稳定正向支持。

因此最终方案删除中间的“航空母舰”模块，变成一条最短论证链：

```text
不可变证据
  → 可寻址原子 treatment
  → 关联信号只提议/低风险条件访问
  → 少量付费干预审计
  → 有作用域序贯资格
  → 资格门控、非对称、可撤回的访问治理
  → Evidence / Belief / Access 分离保存
```

## 1. 论文到底回答什么

### 1.1 核心研究问题

> 在 Agent Memory 的候选暴露与任务结果由同一策略、任务难度和历史状态共同产生时，什么证据有资格改变一条记忆未来的可访问性；这种资格如何在作用域变化、不确定性和错误遗忘/错误保留代价不对称时转化为可撤回的生命周期动作？

### 1.2 两个子问题

- **RQ1：资格证据。** 如何避免把内生轨迹中的成功共现、频率或语义相关性直接写成可迁移贡献？
- **RQ2：治理权限。** 如何避免把局部后验、未决证据或平均效用直接写成永久保留/删除，并为低频高后果记忆保留恢复路径？

### 1.3 当前可证伪假设

| 假设 | 检验 | 当前状态 |
| --- | --- | --- |
| H1：内生共现可使 association 偏离 component effect | 固定微日志、已知潜在结果、混杂/平稳切片 | 受控 DGP 支持；真实日志待测 |
| H2：unresolved 参与衰减会增加错误遗忘 | v2 与 v3 qualification gate 对照 | 已支持 |
| H3：资格门控治理优于固定时间衰减 | 420 paired worlds | Utility 与 FF-regret 已支持；harm/压缩不支持 |
| H4：选择性因果 probe 提高端到端效用 | causal evidence remove/replace | 当前否定 |
| H5：解构层级节省探测并提高泛化 | hierarchy/oracle 对照 | 当前否定 |
| H6：额外自适应预算 cap 有独立价值 | EVSI only vs cap | 当前否定 |

## 2. 框架设计的世界观

### 2.1 解构是测量问题，不是因果真理

复合轨迹必须转成可寻址的处理对象，否则无法 mask、delay 或 replace 某一成分。但 LLM 抽取出的实体、关系或路径不是被发现的真实因果变量。最终只保留 source-linked atomic handle；复杂 hierarchy 必须通过独立 Gate A，否则删除。

### 2.2 因果是治理资格，不是默认在线排序器

因果干预已被 CMI、MemAudit、ActMem、Trivium 等工作部分覆盖；我们的差异不能写成“首次使用因果”。本方案只要求：历史 association 没有权限直接改变持久 access policy，少量付费干预才可能授予这种权限。当前 probe 不提高性能，因此定位为 audit/qualification，而非更强检索器。

### 2.3 预算是停止原则，不是第二套模块

追求因果需要付费，但 v3 显示 task-adaptive cap 与 EVSI stop 重复。最终只问：下一次 probe 是否可能改变资格或治理动作，且其期望决策价值是否超过成本。若不能，就停止；不再保留额外“预算调度器”。

### 2.4 衰减是访问动作，不是证据消失

原始证据不衰减；关系信念不按时间任意衰减；只有 access weight 在 qualified evidence 和非对称风险决策下可以降低或恢复。`unresolved` 永远不能改变持久访问权。

## 3. 完整流程与每个环节的必要性

### Stage 0：Immutable Evidence Journal

**输入：** user/task message、environment observation、Agent action、tool result、outcome。  
**输出：** 带 event ID、timestamp、subject、available_at、permission、hash 和版本的原始记录。  
**职责：** 为所有后续 handle、干预、belief 和 access action 提供不可变来源。  
**为什么必要：** 如果 effect posterior 或摘要能覆盖原始记录，错误资格无法重放、撤回和恢复。  
**不是什么：** 不是论文算法创新；是系统契约。  
**验证：** evidence survival、hash、rollback、删除传播与索引残留审计。

### Stage 1：Source-Linked Treatment Adapter

**输入：** raw evidence 与当前 task contract。  
**输出：** 可执行 expose/mask/delay/replace 的 session、turn、字符跨度或 episode pointer。  
**职责：** 只解决“测试什么”，不判断“什么是真的因果”。  
**机制：** 核心默认使用确定性 source pointer；fact/constraint/action/relation 等语义 sidecar 仅作可选候选键，并保存 adapter/sidecar version 与 scope hint。  
**为什么必要：** 整体 episode 干预同时改变多个成分，无法定位 treatment。  
**风险：** parser noise、不可独立 mask、关系幻觉。  
**验证：** whole session/turn/span 的 remove-replace；只有额外主张语义解构时才运行人工 Gate A。  
**当前裁决：** LongMemEval-S 中 full-session BM25 Recall-all@5=0.8298，高于 turn-max 0.8000；现有 factor/rule/relation sidecar 无稳定增量。保留 source handle，删除 group hierarchy、PathBundle 和“结构性能创新”。

### Stage 2：Shared Candidate Proposal + Conditional Association

**输入：** task scope/risk/version、共享检索候选、历史 association。  
**输出：** audit shortlist 与当前任务访问值。  
**机制：** semantic 与 association 各取 `ceil(sqrt(N))` 前列，取并集；未资格记忆只使用 ((1-risk)) 折扣的条件关联值。  
**为什么必要：** 全量因果审计不可承受，而在低风险平稳任务中关联信号仍有实际价值。  
**硬边界：** association 不进入 causal posterior，不产生 positive/negative qualification，不改变持久 access weight。  
**验证：** association-only、no-association、association-directly-updates-belief 三路对照。

### Stage 3：Selective Scoped Causal Audit

**输入：** shortlist、当前 best alternative、probe cost、scope。  
**输出：** 已支付、可审计的 expose/mask/delay/replace 观测。  
**机制：** 只在 qualification EVSI 高于成本时 probe；candidate set、propensity、workspace position、model/tool/evaluator version 在行动前冻结记录。  
**为什么必要：** 没有干预，Gap 1 仍停留在共现；但 probe 只负责证据资格，不承诺在线性能。  
**当前反证：** v3 `causal evidence` Utility -0.0138 ± 0.0068，零 probe price 仍为负。  
**裁决：** 论文措辞降级为 selective audit；真实 benchmark 若继续无增益，不列性能贡献。

### Stage 4：Sequential Scoped Qualification

**输入：** 同一 scope/version 的付费干预后验。  
**输出：** `positive-qualified`、`negative-qualified` 或 `unresolved`。  
**机制：** Bonferroni family control + `6/(π²n²)` sequential alpha spending；资格记录 evidence、family、look、scope 和撤回条件。  
**为什么必要：** 后验均值符号、一次显著结果或 group average 都不足以获得长期治理权限；重复查看会制造假资格。  
**关键规则：** group evidence 只决定下一步测谁，不授予 item 资格。  
**验证：** no gate、fixed threshold、no sequential spending、global pooling、version scope 的 remove/replace。

### Stage 5：Qualification-Gated Access Governance

**输入：** qualification、scope match、task risk、effect posterior、execution cost、false-forgetting weight。  
**输出：** protect、full access、conditional access、veto、downweight、isolate、archive 或 recovery。  
**机制：** 比较 retain loss 与 archive loss；只有 qualified state 才能更新持久 access weight。  
**为什么必要：** 因果效应不是治理动作；负效应、高风险和执行成本要与错误遗忘的正向尾风险显式权衡。  
**状态语义：**

- positive-qualified：该 scope 下允许 full access/protect；
- negative-qualified：该 scope 下 veto/downweight/archive；
- unresolved：持久访问权冻结，仅当前低风险 conditional access。

**当前证据：** 相对 fixed decay，v3 Utility +0.2352 ± 0.0228、FF-regret +0.1165；但多保留 32.6% 热记忆且 harm 略差。  
**准确主张：** 阻止无资格证据驱动错误遗忘；不是更强压缩，也不是已证明的总体安全最优。

### Stage 6：Three Persistent States + Recovery

**输入：** journal、belief update、governance action。  
**输出：** 独立的 Evidence Survival、Relation Belief 和 Access Policy 状态。  
**机制：** 索引只是派生投影；archive 保留 source/rollback pointer；同 scope positive evidence 可恢复，否则付费 item revalidation。  
**为什么必要：** “证据存在”“关系可信”“当前可访问”是不同命题。  
**当前证据：** recoverability 性能增益约为零；因此只作为安全/审计不变量。  
**验证：** merged state、hard delete、free semantic restore、no recovery；除任务指标外检查 evidence survival 和 rollback correctness。

## 4. 框架为什么已经是最小的

| 环节 | 删除后 Gap 是否仍可回答 | 结论 |
| --- | --- | --- |
| Evidence Journal | 无法审计 treatment 和撤回状态 | 必须，但属底座 |
| Atomic handle | 无法组件级干预；可回退 whole episode | 条件保留，待 Gate A |
| Conditional association | 成本失控或证据不足时完全不用记忆 | 必须作为 fallback |
| Selective audit | 永远无法越过共现 | 概念必须；性能主张待验证 |
| Scoped qualification | 未决证据仍可能变成治理动作 | 必须 |
| Gated governance | 因果证据无法回答生命周期动作 | 当前唯一实证核心 |
| Three-state/recovery | 派生状态覆盖证据、不可撤回 | 必须作为安全契约 |

以下模块已证明冗余或退化，不再出现于最终主图：group hierarchy、group probe、PathBundle、BCPS 名称、adaptive budget cap、sentinel、item veto、contextual effect、semantic bins。

## 5. 数据获取方案

### 5.1 已完成：受控反例与模块挑战

- 6 named scenarios × 50 seeds；
- 120 random stress worlds；
- 13 policies，共 5460 rows；
- 共享 world stream、candidate stream 和 probe potential outcomes；
- v2 保留为失败反例，v3 为冻结正式结果。

用途是证明机制必要性和删除模块，不用于 SOTA。

### 5.2 可选增强：Semantic Sidecar Gate A

数据：LongMemEval 的证据型问题和时间/更新切片。  
标注：source span、类型、scope、是否可独立 mask、冲突和版本。  
指标：source F1、atomicity agreement、intervention validity、abstention、跨模型稳定性。  
当前两个 40-packet pilot workspace 均未标注。该 Gate 不再阻塞核心框架，因为核心默认使用 raw source handle；若希望额外主张 semantic decomposition，则必须完成双人盲化标注，且 sidecar 在固定预算下相对 raw-only 有增量，否则删除该贡献。

### 5.3 必做二：统一公开 benchmark

最小集合：LongMemEval + LoCoMo + 一个动态在线协议。  
必须固定：reader、生成模型、candidate k、token/workspace、prompt、tool、evaluator、API price。  
必须注入/切分：过时、版本变化、低频高后果约束、高相似无关记忆、复发和高干预成本。  
公开 benchmark 没有逐条因果真值，因此主任务分和风险指标不能替代干预校准。

### 5.4 必做三：真实微干预校准

在低风险任务随机 expose/mask/delay，保留 held-out randomized probes；先验证 overlap、propensity、adoption observability 和 evaluator stability，再比较 observational estimator、DR/MSM/OPE 与 randomized ground truth。

## 6. Baseline 体系

### 6.1 生命周期直接基线

- keep-all/no-memory；
- Recency/LRU/Frequency；
- fixed exponential decay；
- FadeMem；
- Oblivion；
- Memory Worth；
- DeMem。

这些工作分别已覆盖差异衰减、访问再激活、结果反馈和决策压缩，不能用弱化实现代替官方基线。

### 6.2 检索与表示基线

- BM25、dense、hybrid/RRF；
- raw episode、summary、source-linked atomic span；
- 相同 candidate stream 下比较，不让新方法使用额外候选或 token。

### 6.3 因果功能对照

- CMI：query-time intervention；
- MemAudit：post-hoc attribution；
- ActMem：causal-semantic structure；
- Trivium：persistent causal evidence/probing；
- 通用 MSM、DR/DML、DR-OPE/CRM。

这些不一定可合并为同一端到端排名；必须按功能、日志条件和成本范围对照。

## 7. 消融实验

| 编号 | 单变量变化 | 回答的问题 | 预注册裁决 |
| --- | --- | --- | --- |
| A1 | atomic handle ↔ whole episode/summary | 解构是否真有必要 | 无增益则删除解构贡献 |
| A2 | association conditional ↔ direct belief update | Gap 1 是否真实影响治理 | direct update 不伤害则收紧 gap |
| A3 | EVSI probe ↔ no/uniform/entropy probe | 付费审计是否值得 | 不优于 no-probe 则仅作诊断 |
| A4 | version scope ↔ global pooling | scope 是否必要 | 无校准/风险改善则简化 |
| A5 | sequential three-state ↔ sign/fixed threshold | qualification 是否必要 | 无差异则删除统计复杂度 |
| A6 | unresolved freeze ↔ unresolved decay | 治理权限门是否必要 | v2/v3 已支持，公开任务复验 |
| A7 | asymmetric ↔ symmetric loss | 低频高后果是否被保护 | 无 FF/worst-group 改善则删除 |
| A8 | three states ↔ merged state | 来源和访问是否可审计 | rollback/evidence audit 必须改善 |
| A9 | archive/revalidate ↔ delete/free restore | 恢复路径是否安全 | 性能无增益仍可保留安全接口 |

## 8. 指标与统计

**任务层：** accuracy/F1、utility、regret、tool success。  
**风险层：** harmful selection、risk-weighted harm、false forgetting/retention、worst-group、CVaR。  
**治理层：** active fraction、access weight、archive/restore、recovery latency、qualification coverage/calibration。  
**成本层：** token、latency、storage、probe/revalidation count and price、zero-price utility、break-even。  
**审计层：** evidence survival、decision-log completeness、rollback success、source leakage。

统计采用 paired seeds/tasks、95% CI、命名压力切片和随机 stress worlds；任何 CI 跨零或极少触发的模块写“未获得证据”。

## 9. 当前正式结果如何约束论文

### 9.1 可以写

- 未决证据驱动衰减会造成错误遗忘；
- 资格门控访问治理在受控世界中相对 fixed decay 提高净效用并降低 FF-regret；
- 该收益来自更保守的权限管理，而非压缩更多；
- 模块挑战删除了 hierarchy、adaptive cap、sentinel 和 recovery performance claim。

### 9.2 不能写

- 因果 probing、解构或 hierarchy 已提高真实性能；
- 当前框架总体风险更低；
- 当前框架压缩更强；
- 已超过 FadeMem、Oblivion、Memory Worth、DeMem；
- 因果、衰减、恢复或预算思想“人无我有”。

## 10. Introduction 之后的论文结构

1. **Problem Formulation**：内生 candidate/exposure/adoption/outcome 与两个 lifecycle losses；
2. **System Contract**：Evidence/Belief/Access 分离和 treatment/log schema；
3. **Conditional Association and Selective Audit**：cheap fallback、可执行干预与 EVSI stop；
4. **Sequential Scoped Qualification**：三态门、family/time control、scope/revocation；
5. **Qualification-Gated Governance**：非对称损失、访问更新、archive/revalidation；
6. **Controlled Counterexamples**：v2 失败、v3 模块挑战；
7. **Public Evaluation**：强基线、真实成本、外部有效性；
8. **Limitations**：probe 当前负收益、结构未支持、更多热记忆、harm 未改善。

## 11. 后续执行优先级

1. 冻结本最小框架和新主图，不再恢复已删除模块；
2. 核心实验直接使用 raw session/turn/span treatment；Gate A 仅在继续主张语义解构时执行；
3. 建立同 reader/candidate/budget 的动态公开 baseline harness；
4. 先跑 keep-all、fixed decay、Memory Worth、FadeMem/Oblivion、DeMem，再加入最小框架；
5. 加入 randomized micro-intervention calibration；
6. 只有公开端到端净效用/风险前沿通过，才写性能型贡献；否则定位为 causal audit + governance protocol。

## 12. 给老师的最终判断

当前最可信的论文不是一个“解构 + 因果图 + 搜索 + 预算 + 衰减 + 恢复”的大全系统，而是一个更窄的问题：

> **在内生暴露的 Agent Memory 生命周期中，未决或关联证据是否有权改变长期访问状态？**

我们的正式反例给出的答案是“没有”。最小方法因此围绕 qualification permission 构建：廉价共现仍可用于低风险当前任务，付费干预只为少数候选产生资格，资格通过后才允许在明确 scope 下执行非对称、可撤回的访问治理。当前唯一被实验直接支持的是这条权限门；其余模块均接受删除。

完整公式、日志 schema、Go/No-Go 和复现入口见 `00-最新版框架完整设计与实验方案.md`；正式数值见 `实验资产/最小框架挑战实验/最小框架挑战正式实验报告-v3.md`。
