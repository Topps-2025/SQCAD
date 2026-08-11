---
type: experiment-report
status: preliminary
tags:
  - longmemeval
  - retrieval
  - benchmark
  - agent-memory
---

# LongMemEval-S 初步检索基线报告

## 1. 实验定位

这是当前项目完成的第一个真实公开 benchmark 实验。实验只评估 session-level evidence retrieval，不调用回答 LLM，也不评估最终 QA 正确率或因果遗忘策略。其作用是验证数据、证据标签与检索接口，并给出后续状态治理方法必须超过的确定性底线。

实现：[[longmemeval_retrieval_probe.py]]；完整结果：[[longmemeval_s_retrieval_probe.json]]；Oracle 接口校验：[[longmemeval_oracle_retrieval_probe.json]]。BM25/dense 融合实现：[[longmemeval_dense_hybrid_probe.py]]；完整多划分结果：[[longmemeval_dense_hybrid_probe.json]]。

## 2. 可复现信息

- 官方仓库：`xiaowu0162/LongMemEval`；本地 commit：`9e0b455f4ef0e2ab8f2e582289761153549043fc`；
- 数据：官方 `longmemeval-cleaned` 中的 `longmemeval_s_cleaned.json`；
- SHA-256：`D6F21EA9D60A0D56F34A05B609C79C88A451D2AE03597821EA3D5A9678C3A442`；
- 470 个非 abstention 问题；按官方说明排除 `question_id` 以 `_abs` 结尾的30题；
- session 粒度；BM25 参数 `k1=1.2, b=0.75`；ASCII 字母数字小写分词；
- 对照为确定性 recency 排序；指标按官方 `evaluate_retrieval` 的定义补齐 `recall_any`、`recall_all` 和 `ndcg_any`。

## 3. 总体结果

| 方法 | Recall-any@1 | Recall-all@5 | NDCG-any@5 | Recall-all@10 | NDCG-any@10 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Recency | 0.0383 | 0.0660 | 0.1059 | 0.1404 | 0.1530 | 0.1594 |
| Turn-max BM25（表示解构基线） | 0.8617 | 0.8000 | 0.8557 | 0.8894 | 0.8764 | 0.8999 |
| MiniLM dense（256-token截断） | 0.7702 | 0.7745 | 0.8058 | 0.8830 | 0.8326 | 0.8390 |
| BM25 | **0.8638** | **0.8298** | **0.8835** | **0.9021** | **0.8972** | **0.9075** |

该结果确认 LongMemEval-S 不是简单的“最近记忆”任务；纯时间保留在证据召回上明显失效。BM25 已形成较强的廉价检索底线，因此后续解构—抽象方法不能只与 recency/FIFO 比较。仅把 session 拆成 turns 并取最大 BM25 分数没有带来总体增益，说明“粒度变细”本身不是有效解构，更不能被包装为因果抽象。

每题平均包含47.7个历史 sessions；top-5 只占候选集合的平均10.5%，但 BM25 能在82.98%的非拒答问题上召回全部证据。该比例可以作为第一版读时预算参考，但不能被解释为“其余89.5%记忆可永久删除”：未进入当前问题 top-5 的记忆仍可能服务未来问题。

## 4. BM25 与 dense 的题型分解

| 题型 | $n$ | BM25 Recall-all@5 | Dense Recall-all@5 | BM25 NDCG@5 | Dense NDCG@5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| knowledge-update | 72 | 0.944 | 0.778 | 0.958 | 0.784 |
| multi-session | 121 | 0.636 | **0.719** | 0.799 | **0.815** |
| single-session-assistant | 56 | 1.000 | 0.982 | 1.000 | 0.982 |
| single-session-preference | 30 | 0.867 | 0.833 | 0.734 | **0.780** |
| single-session-user | 64 | 1.000 | 0.797 | 0.983 | 0.751 |
| temporal-reasoning | 127 | 0.780 | 0.709 | 0.856 | 0.765 |

Turn-max BM25 在 knowledge-update 上将 Recall-all@5 从 0.944 提高到 0.958，但在 multi-session、preference 和 temporal-reasoning 上分别降至 0.595、0.667 和 0.748。该异质性进一步支持本文的方法边界：解构器必须保留跨 turn 关系、作用域和证据组合，不能简单将整体轨迹切碎。

### 4.1 Dense 复现信息与成本

- 模型：`sentence-transformers/all-MiniLM-L6-v2`，`model.safetensors` SHA-256 `53AA5117...D9DB`；
- 本地 Transformers mean pooling + L2 normalization；CPU；batch 64；每个 session 截断至256 tokens；
- 18,239个唯一 session 文档和470个问题；完整运行约14分23秒，峰值工作集约1.52 GB；
- 实现与输出：[[longmemeval_dense_probe.py]]、[[longmemeval_dense_probe.json]]。

MiniLM dense 总体低于 BM25，但在 multi-session 上明显更好，说明强基线不能只选一种检索器。与此同时，256-token 截断可能损害长 session，对该 baseline 的结论应限定于当前模型和编码预算。

### 4.2 开发集选择的 BM25/dense router

使用 [[longmemeval_bm25_dense_router.py]] 在每个题型内选择 BM25 或 dense：每个划分以稳定哈希取20%开发题，按 Recall-all@5、NDCG@5 选择，80%测试；重复10个划分。完整结果见 [[longmemeval_bm25_dense_router.json]]。

相对 BM25，router 的测试变化为：Recall-all@5 `+0.0054 ± 0.0109`，Recall-all@10 `+0.0077 ± 0.0042`，但 NDCG@5 `-0.0064 ± 0.0100`、MRR `-0.0061 ± 0.0082`。“±”为95%置信区间半宽。结果不支持稳定的整体优势，只说明 multi-session 等切片存在语义检索增量。第一版主基线应继续报告 BM25、dense 和 router 三者，而不能只挑对拟议方法最有利的对照。

最明显的改进空间位于 multi-session、temporal-reasoning 和 preference。它们分别对应跨事件组合、时间/作用域条件以及高层偏好抽象，因而比单会话事实更适合检验解构—抽象表示。但公开标签只给出证据 session，并不提供“哪个内部因子具有因果贡献”的真值；不能据此直接训练或验证因果规则。

### 4.3 Dev-tuned BM25/dense RRF hybrid

为避免把单一 BM25 当作过弱基线，新增固定 session candidate stream 的 RRF 融合实验。对每个确定性 split，使用20%开发题在 `alpha ∈ {0, 0.1, 0.25, 0.5, 0.75, 1, 1.5, 2}` 中选择 dense 排名权重，再在80%测试题评估；共10个 split，基础模型、编码长度和候选流均固定。

| 方法 | Recall-any@1 | Recall-all@5 | NDCG-any@5 | Recall-all@10 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.8663 ± 0.0038 | 0.8273 ± 0.0042 | 0.8823 ± 0.0026 | 0.9001 ± 0.0025 | 0.9085 ± 0.0031 |
| MiniLM dense | 0.7693 ± 0.0053 | 0.7707 ± 0.0021 | 0.8037 ± 0.0030 | 0.8789 ± 0.0034 | 0.8379 ± 0.0035 |
| Dev-tuned RRF hybrid | 0.8419 ± 0.0086 | **0.8607 ± 0.0044** | 0.8923 ± 0.0042 | **0.9275 ± 0.0061** | 0.8997 ± 0.0055 |

“±”为10个 split 的95%置信区间半宽。Hybrid 在 Recall-all@5 与 Recall-all@10 上超过 BM25，但在 Recall-any@1 与 MRR 上下降，说明融合改变的是多证据覆盖而非所有排序维度。后续治理实验必须同时报告 BM25、dense、RRF hybrid；不能只挑选对拟议方法最有利的指标或检索器。

## 5. 对后续实验的约束

1. 固定同一 session candidate stream 和 BM25 排名，先比较整体 session、因子束和规则+证据三种表示，避免把检索器替换误认为治理收益；
2. 在相同 top-k 与 token 预算下报告 Recall-all、NDCG、关键证据保全、表示 token 数和延迟；
3. 将 BM25、MiniLM dense 和 dev-tuned RRF hybrid 固定为检索强基线，并在条件允许时增加 Oblivion；当前检索基线不能代替完整 Agent Memory SOTA；
4. 端到端 QA 必须使用同一 reader/evaluator；未配置模型或 API 前，不生成不可比较的答案分数；
5. 因果效应准确性继续由可控 simulator 校准，LongMemEval 只承担外部效用与过程归因。
