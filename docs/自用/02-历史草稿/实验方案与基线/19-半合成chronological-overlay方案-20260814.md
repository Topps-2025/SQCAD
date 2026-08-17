# 半合成 Chronological Overlay 实验方案（2026-08-14，目标阶段 3）

> 触发依据：`实验证据链/16-` §4 判定——公开数据无 lifecycle 金标（无未来纠错/有害保留标签、LME 单题、LoCoMo 后置 QA），最接近的客观代理（ku 旧版本召回）方向受 recency 偏置与检索 oracle 强度支配，不足以承载治理价值判据。本方案在公开轨迹上注入**程序化生成**的未来事件与客观标签（doc 17 §2.4/§7.1），直接检验 T1/T2 理论预测的治理指标。

## 1. 基板与注入原则

- **基板**：LoCoMo（纵向：10 会话 × ~200 QA × 多天时间线；LME 单题样本不适用）。
- **注入只使用历史时点可见信息**：注入 turn 的内容由该时点已发生的会话文本构造（或全新合成内容，但不得引用未来）；未来事件（更新/纠错）在时间上晚于被修改的事实。
- **标签全部程序化**：未来 QA 的金标 = 数据集自身 answer/evidence + 注入事件定义的预期暴露/污染判定（非人工标注，doc 17 §7.1）。
- **复用统一合同**：同一 `run_policy`/`evaluate_trace`/预算/显著性管线（`16-` 冻结协议），policy 只看到注入后的流，评估器独占标签。

## 2. 注入事件类型（对齐 T1/T2 机制）

| 事件 | 构造 | 未来客观标签 | 检验的机制 |
|---|---|---|---|
| **E1 版本更新干扰** | 在 $t_u$ 注入 `UPDATE: <entity> changed from <old> to <new>`（<old> 来自一个 needed turn 的文本片段） | 原 QA 不变（问过去状态）→ 暴露旧版本 = 命中、暴露更新 = 干扰 | 时间一致性 / stale-version |
| **E2 纠错事件** | $t_0$ 注入错误事实 $F$（同实体、错误值）；$t_1>t_0$ 注入 `Correction: <F 错误，实际是 X>`（$X$=数据集金标答案） | $t_1$ 后 QA 金标 = $X$ → 保留 $F$ 且未见纠错 → 失败；纠错延迟 = $t_1$ 后仍暴露 $F$ 的 QA 比例 | 纠错吸收 / harmful retention |
| **E3 有害保留** | 仅 $t_0$ 注入 $F$（无纠错）；$F$ 与 evidence turn 共享 $\ge$ 3 词（版本冲突可检测） | QA 金标 = 数据集答案 → 暴露 $F$ 而未暴露 evidence → 失败 | 有害保留代价 |
| **E4 稀有正向保护** | 不注入内容；从低频 session 的 needed turn 中选 | 原 QA | 稀有保护（正例） |
| **E5 self-obscuring + 恢复** | 无注入；记录证据 turn 是否被写时逐出（档案），QA 时 probe 触发条件（$\ge$ 3 词重叠） | 档案中的证据被 probe/restore 救回 = rescue；否则 = false forgetting | 归档遮蔽未来证据 / probe-restore 通道 |

**中间时点 QA**（构造真正的 chronological future split）：选取证据 turns 全部早于注入 session 的 QA 子集，在注入 session 边界处"提问"（该时点之后的事件对它们不可见）；其余 QA 保持后置（官方协议）。两类分栏报告。

## 3. 指标（objective，全部程序化）

- **E1**：旧版本召回（=未来 QA 命中）、更新干扰暴露率。
- **E2**：纠错后命中率、纠错延迟（$t_1$ 后暴露 $F$ 的 QA 比例）、$F$ 的衰减时间。
- **E3**：有害暴露率（暴露 F 且未暴露 evidence 的 QA 比例）。
- **E4**：稀有 needed 召回。
- **E5**：false forgetting（证据被归档且未救回）、rescue rate（probe/restore 救回比例）、probe/restore 成本。
- **全局**：总命中、成本（storage/exposure/probe/restore），按事件分层 + paired bootstrap（n=10 会话；预注册 seed 不变）。

## 4. 预注册比较集

bm25（检索 oracle 上界）、recency（recency-biased 持久化对照）、keep_all（成本上界）、sqcad 全配置 + 关键消融（no_probe/no_restore、no_version_gate、no_fallback、no_positive_protection）。判定规则与 `16-` 相同（paired studentized bootstrap，CI 排除 0 = 显著）。

## 5. 预期与诚实边界

- 预期：E1/E2/E3/E5 上 sqcad 相对 recency/检索基线在纠错吸收、有害暴露、rescue 指标上显著占优（D0 已证机制，这里是外部轨迹上的机制激活检验）；E4 上稀有保护为正；全局静态召回仍以 bm25 为界（合理边界）。
- 边界：注入密度是设计参数（预注册：每会话至多 1-2 个事件、QA 数固定）；结果证明"机制在真实轨迹结构上的可操作性"，不是"真实 Agent Memory 部署收益"（同 `07-` 成本合同的声称纪律）。
