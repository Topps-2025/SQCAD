---
type: experiment-audit
status: preliminary
scope: retrieval-baseline-strengthening
---

# LongMemEval-S 强检索基线扩展审计

## 1. 目的

当前 LongMemEval-S 已有 BM25、MiniLM dense 和开发集调权的 BM25+dense RRF。为了避免把“session 只截取前256 tokens”误当作语义检索能力上限，本轮尝试两项强基线扩展：

1. BGE-small-en-v1.5，使用 CLS pooling 与查询指令；
2. 本地 all-MiniLM-L6-v2 的 token 分块检索：每段最多220 tokens、32 tokens 重叠，session 内以最大 chunk 相似度聚合，再按原协议调 RRF。

两项扩展均固定原始 session candidate stream、问题过滤、BM25 排名、20/80 development–test split、alpha 网格和 Recall-all@5 主选择目标。

## 2. 结果状态

| 配置 | 状态 | 可引用结果 |
| --- | --- | --- |
| BGE-small-en-v1.5 | Hugging Face 代理 SSL/EOF，5次重试后无法下载 tokenizer_config.json | 无；不得写入 benchmark 表 |
| MiniLM 分块全量（470题、10 splits） | 代码启动并运行约1小时，CPU 工作集接近2 GB；为控制资源已终止，未生成 JSON | 无；不得写成负结果或正结果 |
| MiniLM 分块 smoke test（5题、2 splits） | 完成 | 仅证明实现链路，不构成 benchmark 结果 |

全量分块运行被终止前没有写入部分结果文件，因此不存在可误读的半成品数字。BGE 下载失败也不改变已有 MiniLM、BM25 或 RRF 结果。

## 3. Smoke test 记录

输出文件：longmemeval_minilm_chunk_smoke.json。

- 题数：5；
- 去重 session：253；
- chunk 数：2,923；
- chunk 长度/重叠：220/32；
- session pooling：max；
- 模型设备：CPU；
- 结果仅用于验证 chunk 切分、相似度聚合、RRF 调权和 JSON 协议。

由于样本量和 split 数极小，smoke test 的 Recall 或 MRR 不进入论文结果表，也不用于选择任何方法。

## 4. 工程诊断

本轮审计产生了两个可复用结论：

1. **模型下载是外部依赖边界。** 新 embedding 模型必须在有固定缓存、revision 和 hash 的环境中预下载；当前网络代理不能支撑可复现的 BGE 结果。
2. **全量分块需要更高效的执行路径。** 当前脚本逐批编码所有 chunk，CPU 成本接近不可接受。下一次应优先使用 GPU 或离线向量缓存；若只研究实际 RRF，可先对 BM25 top-N 候选做 chunk reranking，并把候选截断明确写入协议。

在这些条件满足之前，论文的强检索控制仍以已完成的三项为准：

- BM25；
- 本地 all-MiniLM-L6-v2 的256-token session dense；
- 同一候选流上的 dev-tuned BM25+dense RRF。

这些结果已经覆盖首位命中、多证据覆盖、NDCG、MRR 和10个 held-out splits；新增扩展不能替代它们，也不能因为运行失败而声称现有 baseline 已达到公开 SOTA。

## 5. 对论文主张的影响

本审计不支持任何新的性能主张。它只加强了实验边界：

- 若未来分块或 BGE 超过 RRF，拟议治理方法仍需在同一强检索前沿上比较；
- 若新增 baseline 只增加 token、延迟和存储而没有多指标收益，应作为非帕累托控制；
- 语义解构的公开实验仍须等待 Gate A 双标通过，不能用更强 embedding 替代语义/因果标注。

## 6. 相关文件

[[longmemeval_dense_hybrid_probe.py|可配置 dense/RRF 脚本]]、[[LongMemEval-S初步检索基线报告|已完成检索基线]]、[[../09-English-Experiments-Draft|英文 Experiments]]、[[../02-Agent Memory遗忘评测基准、基线与数据选择方案|数据与 baseline 方案]]
