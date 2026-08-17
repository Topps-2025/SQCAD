---
type: experiment-report
status: negative-with-diagnostic-signal
tags:
  - longmemeval
  - decomposition
  - relation-extraction
  - sidecar
  - retrieval
---

# LongMemEval-S：可审计关系 Sidecar 实验报告

## 1. 研究问题与边界

本实验检验一个比 TF-IDF 关键词更结构化、但仍可在本地复现的解构代理：将每个 session 写入期文本解析为带来源句、主语、谓词、宾语和局部否定标记的关系候选，再把关系索引作为 Raw evidence 的 sidecar，通过开发集调权的 RRF 融合。抽取过程不使用问题、答案、`answer_session_ids` 或 `has_answer` 标签。

该解析器是**句法—语义候选构造器**，不是因果发现器。它不能验证某个关系是否对 Agent 行动或任务结果具有反事实增量，也不能取代本文后续的 propensity 日志、微干预与效应估计。

实现：[[longmemeval_relation_sidecar_probe.py]]；修复版完整结果：[[longmemeval_relation_sidecar_v2.json]]。早期诊断 artifact `longmemeval_relation_sidecar_probe.json` 存在缩写辅助词与全句否定范围污染，不进入主比较。

## 2. 协议

- 数据：LongMemEval-S，470 个非 abstention 问题；18,239 个去重 session；
- 表示：NLTK POS 标注的 verb-centred relation candidates；每个 session 最多64条；
- v2 修复：跳过缩写/情态辅助词；系词统一为 `be` 属性关系；否定只在谓词前后4个 token 内判定；
- 检索：Raw BM25、relation-only BM25、RRF(Raw BM25, relation BM25)；
- 调权：每个稳定哈希 split 用20%开发题从 `0, 0.1, 0.25, 0.5, 0.75, 1, 1.5, 2` 选择关系权重，80%测试；10个 split；
- 选择目标：开发集 Recall-all@5，NDCG@5 与较小权重依次作为 tie-break；
- 资源观测：完整 v2 CPU 运行约57分钟，工作集超过1 GB；因此其成本不能与 BM25 视为等价。

## 3. 抽取覆盖与审计

| 指标 | 结果 |
| --- | ---: |
| unique sessions | 18,239 |
| sessions with at least one relation | 18,233 |
| relation coverage | 0.9997 |
| mean relations/session | 61.29 |
| relation-token/raw-token ratio | 0.1092 |

修复版保存100个稳定哈希抽样 session 的来源句与关系候选，共1,200条审计关系。缩写谓词碎片（`m/re/s/ve/d/ll`）由早期版本的128/1,200降至0/1,200；局部否定标记为19/1,200。该检查只说明两类明确实现错误被修复，**不等同于主客体、共指、时间或作用域语义准确率**。

## 4. Held-out 多指标结果

下表为10个开发—测试 split 的测试均值，括号内为95%置信区间半宽。

| 方法 | Recall-any@1 | Recall-all@5 | NDCG-any@5 | Recall-all@10 | NDCG-any@10 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Raw BM25 | 0.8663 (±0.0038) | 0.8273 (±0.0042) | 0.8823 (±0.0026) | 0.9001 (±0.0025) | 0.8962 (±0.0022) | 0.9085 (±0.0031) |
| Relation only | 0.5012 (±0.0117) | 0.5159 (±0.0094) | 0.5753 (±0.0073) | 0.6092 (±0.0083) | 0.6067 (±0.0065) | 0.6255 (±0.0081) |
| Raw + relation RRF | 0.7947 (±0.0218) | 0.8295 (±0.0033) | 0.8668 (±0.0094) | 0.9015 (±0.0027) | 0.8815 (±0.0092) | 0.8697 (±0.0134) |

相对 Raw BM25 的逐 split 配对差如下：

| 指标 | $\Delta$ Raw + relation RRF | 95% CI 半宽 |
| --- | ---: | ---: |
| Recall-any@1 | −0.0717 | ±0.0222 |
| Recall-all@5 | +0.0021 | ±0.0020 |
| NDCG-any@5 | −0.0155 | ±0.0094 |
| Recall-all@10 | +0.0013 | ±0.0012 |
| NDCG-any@10 | −0.0147 | ±0.0093 |
| MRR | −0.0389 | ±0.0138 |

开发集选择的关系权重为：`alpha=0` 1次、`0.1` 5次、`0.25` 4次。结果表明，结构化关系索引对“全部证据是否进入 top-k”存在极小正向信号，但以明显降低首位命中、排序质量和 MRR 为代价；它也远低于 dev-tuned BM25+dense RRF 的 Recall-all@5=0.8607。因此，该方法没有形成多指标帕累托改进，更不能作为 SOTA 候选。

## 5. 对研究框架的含义

本实验否定的是“只要把文本拆成谓词—论元关系，就足以实现有效解构”。其诊断意义有三点：

1. **覆盖率不等于解构质量。** 99.97%的 session 能产生关系，但 relation-only Recall-all@5 只有0.516；高覆盖不能证明候选保持了任务所需条件。
2. **局部结构不足以支持抽象。** POS 关系缺少共指消解、事件时间、主体/工具版本、否定作用域、更新关系和跨 session 证据组合，无法形成本文所要求的有作用域规则。
3. **候选扩展与排序质量存在冲突。** sidecar 略增多证据覆盖，却显著损害 top-1 与 MRR；后续治理器必须把 coverage、precision、token 和延迟共同纳入目标，而不能只优化 Recall-all@5。

因此，论文主张仍应保持 Conditional GO：可审计关系 sidecar 显示“结构化候选可能补充多证据覆盖”的微弱迹象，但没有证明真实解构—抽象模块的外部有效性。下一版解构器必须至少提供角色/主体区分、共指、时间、作用域、事件更新与证据跨度，并在人工标注切片上先通过 precision/recall 与 scope completeness 门槛，再运行昂贵的完整 benchmark。

## 6. 下一步实验门槛

1. 从 multi-session、temporal-reasoning、preference 和 knowledge-update 中分层抽取200个证据 session，建立人工 `entity / condition / action / outcome / time / scope / provenance` 标注；
2. 比较 POS-v2、LLM/信息抽取器和人工标注，报告 factor precision/recall、relation F1、provenance coverage 与 scope completeness；
3. 只有达到预注册 Gate A 后，才在全量数据构建 semantic sidecar；
4. 公开主实验必须同时超过 Raw BM25 与 BM25+dense RRF 的固定预算前沿，并报告 Recall-all、NDCG、MRR、token、预处理时间和恢复风险。

## 相关文档

[[LongMemEval-S初步检索基线报告|强检索基线]]、[[LongMemEval-S表示对照实验报告|词法表示负对照]]、[[../05-解构抽象因果遗忘框架阶段性可行性判断|阶段性可行性判断]]、[[../06-解构抽象能力的学术化界定与因果架构融合|学术化方法界定]]
