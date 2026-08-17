---
type: data-card
scope: agent-memory-forgetting
status: reproducibility-freeze-draft
updated: 2026-08-03
---

# Agent Memory 遗忘研究数据卡（当前冻结草案）

本数据卡区分三种用途：公开对照集用于外部可比性，语义 Gate A 用于表示审计，可控 simulator 用于因果估计真值。公开 QA 数据没有逐条记忆动作的反事实金标，因此不能单独证明遗忘策略的因果有效性。

## 1. 已下载并完成 hash 冻结的资产

| 资产 | 本地路径 | SHA-256 | 用途 | 状态 |
| --- | --- | --- | --- | --- |
| LongMemEval-S cleaned | `tmp/upstream/LongMemEval/data/longmemeval_s_cleaned.json` | `D6F21EA9D60A0D56F34A05B609C79C88A451D2AE03597821EA3D5A9678C3A442` | 470 个非 abstention 问题的主检索/外部有效性对照 | 已下载；BM25、MiniLM、RRF、词法/关系负对照已完成 |
| LongMemEval Oracle | `tmp/upstream/LongMemEval/data/longmemeval_oracle.json` | `821A2034D219AB45846873DD14C14F12CFE7776E73527A483F9DAC095D38620C` | 证据已知上界，用于区分检索瓶颈与记忆治理瓶颈 | 已下载；只作上界，不作主结果 |
| Semantic Gate A 200 packets | `Material/03-核心研究问题与具体设想/experiments/semantic_gate_a/longmemeval_semantic_gate_a_200.jsonl` | `7C987647C56055512CBB9219F5020396320E5103C0EB4B61EB2A54287EF4D5C` | 70 multi-session、50 temporal、50 update、30 preference 的证据/因子/关系人工审计 | 模板已冻结；人工双标未完成 |
| Oblivion source snapshot | `tmp/upstream/oblivion-main.zip` | `753C49FF255ED2D3916998505ACEBD5E610FAE9A1B643DADCBB207197196EEBE` | 直接遗忘/访问衰减强基线代码审计与后续复现 | 代码已审计；当前 Python/模型端点条件不足，未称为本地复现 |

LongMemEval 上游 commit 为 `9e0b455f4ef0e2ab8f2e582289761153549043fc`，仓库入口为 <https://github.com/xiaowu0162/LongMemEval>。Semantic Gate A 沿用上游许可；在公开发布对话文本前仍需复核再分发条款。

## 2. 计划使用但尚未完成统一复现的公开集

| 数据集 | 入口 | 计划作用 | 当前限制 |
| --- | --- | --- | --- |
| GoodAI-LTM | <https://github.com/GoodAI/goodai-ltm-benchmark> | 在线 retain/revise/update 与恢复行为 | 仓库可访问；许可证和数据条款需人工复核；需要统一 runner |
| LoCoMo | <https://github.com/snap-research/locomo> | 长程多跳、时间和开放域外部有效性 | 仓库可访问；尚未锁定本地 release/hash 与统一 evaluator |
| MemoryAgentBench | <https://github.com/HUST-AI-HYZ/MemoryAgentBench> | 选择性遗忘及增量记忆复验 | 可列入 P2；需锁定论文对应 commit 与子任务许可 |
| MemBench | 论文与本地 PDF | 事实/反思、知识更新与容量覆盖 | 官方 artifact 尚未核验，不能写成已复现结果 |

## 3. 可控因果真值层

`experiments/governance_baseline_simulator.py` 及其多随机种子输出提供可枚举潜在结果、日志策略、候选记忆、状态动作和治理风险。该层用于验证 ATE/CATE、MSM、DR-OPE、策略排序和错误遗忘指标，不能替代自然对话生态效度。

## 4. 统一实验冻结要求

在比较 FadeMem、Oblivion、Memory Worth、DeMem 或本方法前，必须固定基础模型、候选记忆流、写入器、embedding、retriever、top-k、工作区 token、存储预算、工具版本、evaluator、随机种子和动作日志格式。论文报告值与本地复现值分栏；未满足统一条件的数字只能作为背景，不进入同一 SOTA 主表。

## 5. 当前不可宣称内容

- Gate A 尚未通过，模板生成不等于人工语义质量达标；
- POS/关键词/关系 sidecar 不是语义因果解构器；
- LongMemEval retrieval 结果不是 forgetting result；
- simulator 结果不是公开 benchmark SOTA；
- Oblivion、FadeMem、Memory Worth、DeMem 等尚未在统一协议下完成本地端到端复现。
