---
type: experiment-audit
status: public-retrieval-reproduced-semantic-gate-pending
date: 2026-08-07
scope: LongMemEval-S retrieval and atomic-treatment interface
---

# 最小框架公开证据与 Atomic Treatment 裁决

## 1. 审计目的

正式 v3 已否定 noisy hierarchy、group probe 和 sentinel 的必要性，但最终框架仍需要一个可执行的 treatment 单元。该审计回答：复杂语义解构是否仍应作为核心前置条件，还是确定性的原始 session/turn/source span 已足以承担最小 treatment 接口。

本审计不评估回答生成、Agent 行动效用或因果生命周期治理；它只使用 LongMemEval-S 的公开 session-level evidence labels，验证真实候选结构上的检索、粒度和来源闭合。

## 2. 数据与复现身份

- 数据：LongMemEval `longmemeval_s_cleaned.json`；
- 上游 commit：`9e0b455f4ef0e2ab8f2e582289761153549043fc`；
- SHA-256：`D6F21EA9D60A0D56F34A05B609C79C88A451D2AE03597821EA3D5A9678C3A442`；
- 470 个非 abstention 问题；
- 平均每题约 47.7 个历史 sessions；
- 公开 labels 只用于 evaluator，不进入 query-independent writer。

Gate A manifest 中遗留的旧工作区路径已修正到当前 `Casual Memory` 工作区；数据和空模板 hash 均与冻结记录一致。

## 3. 2026-08-07 重跑验收

### 3.1 Gate A 结构

- `test_score_semantic_gate_a.py` 与 `test_semantic_decomposition_pos_baseline.py`：**7 passed**；
- 空模板验证：200 packets，160 main + 40 pilot；
- question type：knowledge-update 50、multi-session 70、single-session-preference 30、temporal-reasoning 50；
- evidence sessions：418；
- annotation SHA-256：`7C987647C56055512C2BB9219F5020396320E5103C0EB4B61EB2A54287EF4D5C`；
- packet identity SHA-256：`98A1934E175DA9FF445BEEBBBB2E425A09E1940360DB7549953A05CFA84E5A3D`。

POS/regex baseline 重新生成 200 packets 后，与既有 `predictions_pos_regex_baseline.jsonl` **逐字节相同**：

- 文件大小：59,113,386 bytes；
- SHA-256：`D73D43C3EAF353F324DF215E8F67C66983F065311124AC68B9417649D19ED3D9`。

这证明数据接口、source span 回溯和关系引用闭合可复现，但不产生语义 gold。

### 3.2 公开 retrieval 重跑

`longmemeval_retrieval_probe.py` 在当前数据上重新运行；重跑结果与既有 `longmemeval_s_retrieval_probe.json` 的 overall、by-question-type 和全部 470 个 per-question records **完全一致**。

| 表示/策略 | Recall-all@5 | MRR | 解释 |
| --- | ---: | ---: | --- |
| Recency | 0.0660 | 0.1594 | 不能作为唯一强基线 |
| Full-session BM25 | **0.8298** | **0.9075** | 当前确定性廉价主基线 |
| Turn-max BM25 | 0.8000 | 0.8999 | 粒度变细没有总体增益 |

既有开发—测试审计进一步显示：

- factor evidence、rule-only 和 rule+evidence replacement 均显著低于 raw session；
- Raw + factor/rule sidecar 的开发集最优权重接近 0，测试增量为负；
- POS-v2 relation sidecar 仅将 Recall-all@5 从 0.8273 微升到 0.8295，却使 Recall-any@1、NDCG@5 和 MRR 明显下降；
- BM25+dense RRF 的 Recall-all@5 为 0.8607，说明检索器融合比自造结构 sidecar 更有实际增量。

## 4. 为什么 LongMemEval-S 不能伪装成纵向治理 benchmark

对 470 个问题的 session identity 审计得到：

- 18,239 个唯一 sessions；
- 22,419 次 session 出现；
- 3,567 个 session 被多个问题复用，最大复用 6 次；
- 882 个唯一 gold sessions；
- 只有 8 个 gold session 被复用，最大仅 2 次。

因此 LongMemEval-S 适合检验证据检索和 treatment 粒度，却缺少足够的重复 gold exposure 来形成可信的长期 reinforce/decay/archive/recovery 序列。若人为复制任务或根据 gold 构造漂移，会把研究者设计的 DGP 当成公开 benchmark 事实。该数据不能单独验证 lifecycle causal governance。

## 5. 对 Atomic Treatment 的正式裁决

### 5.1 核心默认

最终框架默认使用确定性的：

- session ID；
- message/turn ID；
- source character span；
- 必要时 whole-episode pointer。

这些 handle 具备 source identity、可 mask/replace 和可回放性，不需要宣称恢复语义因子或真实因果变量。它们足以支撑最小的组件级 treatment contract。

### 5.2 可选增强

fact/constraint/action/relation 等语义类型、跨 turn relation 和抽象规则只作为可选 sidecar。只有完成 40-packet 双人盲化 pilot、裁决、本体冻结和 main evaluation，并在 raw-only 基础上取得固定预算增量后，才能进入方法贡献。

### 5.3 当前 Gate A 状态

两个 pilot workspace 均有 40 packets，但所有 annotation 状态仍为 `unannotated`。人工 Gate A 因而没有完成，不能报告 factor F1、relation F1、scope completeness 或 annotator agreement。

这不再阻塞最小框架本身，因为最小 treatment 已退回确定性 source handle；它只阻塞“语义解构是创新/提高性能”的额外主张。

## 6. 对最终架构的进一步收缩

1. 将 `Atomic Treatment Constructor` 改为 **Source-Linked Treatment Adapter** 更准确；
2. 核心路径不需要 factor ontology、relation graph、abstract rule 或人工 semantic Gate A；
3. cheap proposal 直接作用于 raw session/turn/span；
4. 付费干预对明确 pointer 执行 expose/mask/delay/replace；
5. 语义 sidecar 只能扩展候选键，不能替换 raw evidence 或授予资格。

## 7. 剩余外部验证

公开端到端 lifecycle 仍需要动态多轮协议，以及固定 reader、Agent、model/tool、evaluator 和价格。当前本地 Oblivion/GoodAI-LTM runner 仍依赖可用的生成模型和 judge endpoint；没有这些外部条件时，不能把 retrieval-only 指标替代 Agent 任务效用。

下一步应优先：

1. 在可运行动态协议中比较 keep-all、fixed decay、Memory Worth、Oblivion/FadeMem 和 qualification gate；
2. 记录 candidate→exposure→adoption→action→outcome；
3. 对低风险子任务随机 expose/mask，建立真实或半真实 randomized holdout；
4. 若 probe 仍无净收益，最终论文定位为 access-governance protocol，而不是端到端性能方法。

## 8. 有界结论

> 公开 LongMemEval-S 证据不支持复杂解构或关系 sidecar 作为核心性能模块，但支持一个更小、更可靠的 treatment 接口：使用不可变的 session/turn/source-span pointer 进行候选、干预和回放。语义解构从核心前置条件降级为可选增强；其人工 Gate A 尚未完成。公开数据同时表明 LongMemEval-S 缺少足够纵向 gold 复用，不能被改造成 lifecycle governance 真值而不引入新的半合成假设。
