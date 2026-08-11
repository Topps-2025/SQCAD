---
type: experiment-report
status: structural-negative-control
scope: semantic-gate-a
---

# POS/Regex 语义解构下界 baseline 报告

## 1. 目的与定位

本实验实现一个无需外部 API、无需查询答案、无需 `answer_session_ids` 和金标标注的 Gate A 下界对照。它用于验证 Gate A 的数据接口、证据谱系闭合和关系引用是否可被一个弱表示器端到端消费；它不是本文提出的语义解构器，也不是因果发现器，更不能作为公开 benchmark 的 SOTA 或最终方法结果。

实现文件为 `semantic_decomposition_pos_baseline.py`，预测文件为 `predictions_pos_regex_baseline.jsonl`。原始 evidence session 保持不变，预测只替换 `annotation` sidecar；`adjudication_only` 被从预测工件中移除，避免参考答案泄漏。

## 2. 方法

对每个 evidence turn，基于确定性的句子/词法正则和轻量 POS 启发式生成：

- 证据跨度：句子级 `[char_start, char_end)`，保留 session、turn、角色和原文；
- 因子候选：实体、属性、行动、偏好和时间；
- 关系候选：`performs`、`prefers`、`during` 和 `uses_tool`；
- 抽象规则：固定为空。

最后一项是有意设计：局部共现不足以支持跨情境规则，更不足以支持 `causal_candidate`。因此该 baseline 不会把共现升级为因果关系，也不会进行不可逆删除授权。每个 packet 设置有限 sidecar 预算（384 个跨度、768 个因子、768 个关系），以避免长会话将代理结构膨胀为第二份原文。

## 3. 审计结果

- 200 个 packet 的 packet ID 与顺序集合一致；
- 预测不包含 `adjudication_only`、`reference_answer` 或 `answer_session_ids`；
- 原始问题、问题类型、日期和 evidence sessions 与输入逐字段一致；
- 每个预测跨度均通过原文字符区间回溯校验；
- 所有因子的 span 引用和所有关系的 factor/span 引用均闭合；
- 预测 schema 可被 Gate A scorer 读取（但空模板不产生可解释的分数）；
- 结构测试 `test_semantic_decomposition_pos_baseline.py`：3 tests OK。

## 4. 为什么暂不报告 Gate A 分数

当前 `longmemeval_semantic_gate_a_200.jsonl` 仍是未标注模板，200 个 packet 的 gold `annotation` 为空；40 个 pilot 也尚未完成双人独立标注、裁决和本体冻结。直接将预测与空模板运行 scorer，只能得到“gold component 数为零”的接口性数字，不能估计 factor F1、relation F1、provenance 或 scope 质量。因此本实验仅报告结构审计，不把空模板分数写成 Gate A 结果。

下一步必须先完成 40 个 pilot 的双人标注与裁决，再以冻结后的金标运行 scorer，并将本 baseline 作为明确的 negative control。预期它会暴露词法粒度、跨句关系、更新/否定、主体作用域和时间范围方面的误差；无论结果如何，都不能替代真实语义解构器。

## 5. 对架构的含义

该下界对照支持一个工程约束：图或关系 sidecar 只是可替换的逻辑组织视图，不能成为原始证据的唯一存储；任何抽象规则必须保留支持跨度、作用域和版本，并在因果资格审查前保持 `candidate` 状态。只有在 Gate A 通过、随后完成处理定义、overlap、DR/MSM/OPE 和独立任务回放后，解构—抽象联合表示才可进入遗忘治理。
