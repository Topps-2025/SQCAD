# SQCAD — 中文文档（GitHub 展示）

SQCAD（Scope-qualified, Competition-gated Access for Agent Memory）研究的是：**什么证据有资格改变 Agent 记忆的持久访问策略，以及固定工作区预算下如何分配当次访问资源**。

核心主张：持久 `keep/archive` 动作的长期价值在当前观测下不可识别时，不能把相关性分数直接当作授权；必须区分"提出候选"（Evidence）、"资格判断"（Qualification）与"改变访问状态"（Access）三个环节。持久治理动作（archive / restore / probe / 弃权）都受识别条件约束。

## 结构

| 目录 | 内容 |
|---|---|
| [00-研究总图](00-研究总图.md) | 研究问题、核心分离、证据状态与结论边界 |
| [01-研究理念](01-研究理念/README.md) | 背景概念、动机与研究理念基座 |
| [02-现有工作与痛点](02-现有工作与痛点/README.md) | 现有工作地图、文献证据索引与研究痛点 |
| [03-核心问题与框架设计](03-核心问题与框架设计/README.md) | 框架设计、概念节点与框架图 |
| [04-数据与实验](04-数据与实验/README.md) | 数据集与关键实验结果 |

英文版见 [docs_en](../docs_en/00_overview.md)。完整实验报告、理论证明与实验方案（内部资料）在 `docs/自用/`。

## 核心结果（2026-08-17）

- **公开集**：同一 chronological stream 与统一合同下，最小修复 Guard-1 将 LoCoMo token-F1 从 0.0344 提升到 0.0455（略高于 BM25 的 0.0454），LongMemEval-S Hit 0.785 → 0.915；GPU 复核与本地一致。
- **自建集**：SQCAD-LifecycleBench 1,380 个 keep/archive 反事实 episode，可测量 lifecycle value / regret / false-commit / probe / restore；oracle 上界 +0.964，probe-willing +0.865；三项框架修改判定有定量依据。
- **审计**：R1–R5、R7 四通道公允性防线通过（真值可独立检验、失败可发生、泛化可被挑战、评价不可被猜），13 行预注册判定全命中；R2 脆弱参数已重定位到有效域。
