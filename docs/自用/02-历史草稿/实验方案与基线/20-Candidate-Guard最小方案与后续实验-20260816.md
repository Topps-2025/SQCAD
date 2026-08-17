# Candidate-Guard 最小方案与后续实验

## 当前结论

原 SQCAD 在公开集上的瓶颈是 candidate coverage，而不是需要放松决策识别门。Candidate-Guard 把 BM25 仅作为一次性证据提议器，最多提出有限候选；它不授权持久 keep/archive，不绕过 unresolved，也不把 gold evidence 送入策略。

## 推荐配置

主结果使用 `sqcad_candidate_guard_1`。`_2` 和 `_4` 只作为预算敏感性结果，不作为默认配置。

## 后续必须做的实验

1. 在相同候选预算下加入 dense/RRF，检验候选 guard 是否依赖 lexical overlap。
2. 对 Guard-1 的 candidate probe 做分层统计：版本冲突、稀有 session、multi-hop、temporal update。
3. 记录 probe 命中率、候选进入暴露池比例和恢复后持久留存比例，避免只报告 QA F1。
4. 在半合成 chronological overlay 中验证：candidate proposal 增加覆盖，但不改变跨零识别集合的授权状态。
5. 使用配对 bootstrap 报告 Guard-1 与原 SQCAD/BM25 的 hit、recall、F1、token 和 probe 成本差异。
