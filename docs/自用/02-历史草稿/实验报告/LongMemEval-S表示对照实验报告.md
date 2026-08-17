---
type: experiment-report
status: negative-result
tags:
  - longmemeval
  - decomposition
  - abstraction
  - evidence
---

# LongMemEval-S：整体、因子、规则与规则+证据表示对照

## 1. 目的与严格边界

该实验在 LongMemEval-S 的470个非拒答问题上，对比四种查询无关、相同候选 session、相同 BM25 检索器的表示：

1. `raw_session`：完整 session；
2. `factor_evidence`：按跨 session IDF 信息密度选择两个来源句子；
3. `rule_only_proxy`：从来源 session 提取12个 TF-IDF 关键词作为规则候选代理；
4. `rule_plus_evidence_proxy`：规则关键词与对应来源句子成束表示。

实现：[[longmemeval_representation_probe.py]]；完整结果：[[longmemeval_representation_probe.json]]。

“规则代理”不是因果规则，也没有使用问题、答案或 `has_answer` 标签进行写入期抽取。该实验的目的不是证明拟议方法有效，而是检验廉价无监督解构/抽象能否成为合理替代，并为真正方法设置负对照。

## 2. 总体结果

| 表示 | 原始 token 比例 | Recall-any@1 | Recall-all@5 | NDCG-any@5 | Recall-all@10 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 完整 session | 1.000 | **0.864** | **0.830** | **0.884** | **0.902** | **0.908** |
| 因子证据代理 | 0.062 | 0.270 | 0.253 | 0.326 | 0.313 | 0.394 |
| 仅规则代理 | 0.007 | 0.606 | 0.491 | 0.598 | 0.543 | 0.689 |
| 规则+证据代理 | 0.072 | 0.415 | 0.385 | 0.473 | 0.506 | 0.547 |

结果是明确的负结果：所有压缩表示均未超过完整 session。`rule_only_proxy` 虽以0.7%的 token 保留约49.1%的 Recall-all@5，但“规则+证据”没有形成预期协同；两个高 IDF 句子的选择还严重破坏证据覆盖。

## 3. 题型异质性（Recall-all@5）

| 题型 | 完整 session | 因子代理 | 仅规则代理 | 规则+证据代理 |
| --- | ---: | ---: | ---: | ---: |
| knowledge-update | 0.944 | 0.139 | 0.542 | 0.306 |
| multi-session | 0.636 | 0.124 | 0.298 | 0.174 |
| single-session-assistant | 1.000 | 0.804 | 0.964 | 0.964 |
| single-session-preference | 0.867 | 0.267 | 0.400 | 0.300 |
| single-session-user | 1.000 | 0.344 | 0.703 | 0.563 |
| temporal-reasoning | 0.780 | 0.150 | 0.354 | 0.307 |

只有 single-session-assistant 对规则代理较宽容；multi-session、temporal-reasoning、preference 和 knowledge-update 均依赖被无监督压缩丢失的关系、时间或更新证据。

## 4. 对论文框架的直接修正

1. **解构—抽象不能替换原始证据。** 工程上应实现双通道 sidecar：原始证据索引始终保留，因子/规则只增加检索键、作用域过滤和治理信号。
2. **证据覆盖必须成为写入门控。** 若候选因子无法覆盖来源中的关键实体、时间、否定、更新和关系，不得晋升为活跃规则。
3. **规则必须携带可回退证据。** “规则+证据”不是简单文本拼接，而应在读时按查询和风险选择最小充分来源；当前固定两句代理证明静态证据预算不足。
4. **抽象收益应以增量而非替代衡量。** 主实验应比较 `raw retrieval` 与 `raw + factor/rule sidecar`，而不是预设压缩表示必然优于原文。
5. **token 减少不是成功。** 只有在固定证据召回/任务效用下减少 token，或在固定 token 下提高效用，才能形成帕累托改进。

## 5. 下一版方法对照

- `Raw-only`：完整 session BM25/dense；
- `Proxy factor/rule replacement`：本实验负对照；
- `Raw + factor keys`：因子只参与候选扩展，最终返回原始证据；
- `Raw + scoped rule + evidence pointer`：规则参与查询匹配，但暴露时携带来源；
- `Rule-only`：专门测试无证据抽象的错误泛化与幻觉风险。

只有后两种 sidecar 方法在多题型、多随机种子和固定预算下超过 Raw-only，才能说明解构—抽象模块具有公开 benchmark 增量。

## 6. Sidecar 融合的开发—测试复验

进一步使用 [[longmemeval_sidecar_rrf.py]] 将 Raw BM25 与三类代理通过 RRF 融合。每个划分种子以稳定哈希选择20%问题作为开发集，从 `0, 0.1, 0.25, 0.5, 0.75, 1, 1.5, 2` 中选择 sidecar 权重，再在其余80%问题测试；共10个划分种子。完整结果见 [[longmemeval_sidecar_rrf.json]]。

| Sidecar | 平均选择权重 | Test Δ Recall-all@5 | Test Δ NDCG-any@5 |
| --- | ---: | ---: | ---: |
| 因子证据代理 | 0.010 | -0.0027 ± 0.0052 | -0.0057 ± 0.0072 |
| 仅规则代理 | 0.065 | -0.0018 ± 0.0042 | -0.0103 ± 0.0085 |
| 规则+证据代理 | 0.010 | -0.0013 ± 0.0026 | -0.0040 ± 0.0039 |

“±”为跨10个划分的95%置信区间半宽。开发集在绝大多数划分中选择权重0，测试差值也均未显示正向增益。因此，即使采用“不替换原文”的 sidecar 架构，当前无监督词法代理仍不能改善 Raw BM25。这个结果否定的是廉价代理，不是否定未来的证据锚定语义解构；但在真实语义模块取得公开增量前，论文不能声称解构—抽象已通过外部有效性验证。

## 7. 可审计句法—语义关系 Sidecar

在词法代理之后，进一步实现了带来源句、主语、谓词、宾语和局部否定标记的 POS-v2 关系候选。完整协议与结果见 [[LongMemEval-S可审计关系Sidecar实验报告]]。该表示覆盖99.97%的 session、约占原文10.9%的 token；开发集调权的 Raw+relation RRF 将 Recall-all@5 从0.8273微升至0.8295，但 Recall-any@1、NDCG@5和MRR分别下降0.0717、0.0155和0.0389，且远低于 BM25+dense RRF 的 Recall-all@5=0.8607。因此，谓词—论元切分仍不是本文所需的因果解构，只能作为更强的负对照与候选覆盖诊断。
