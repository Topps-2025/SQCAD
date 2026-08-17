---
type: annotation-protocol
status: draft-for-pilot
scope: semantic-decomposition-gate-a
---

# LongMemEval 语义解构 Gate A 标注规范

## 1. 目的、主张与边界

### 一句话论点

在投入全量语义 Sidecar 与端到端因果治理实验前，本标注集用于检验解构器能否从原始 Agent Memory 证据中恢复**带精确来源、时间和作用域的任务相关因子与关系**；它不把任务相关性、自然语言因果词或人工解释当作已识别的反事实效应。

### 标注集能回答的问题

1. 解构器是否找到任务所需的实体、属性、条件、行动、结果、偏好、时间、约束、工具和版本？
2. 每个因子和关系能否精确回溯到原始 session、turn 与字符跨度？
3. 否定、更新、冲突、先后顺序和主体/任务作用域是否被保留？
4. 抽象规则候选是否明确记录支持证据、适用边界和潜在反例？

### 标注集不能回答的问题

- 某条记忆的暴露是否真正改变 Agent 行动或任务结果；
- 某个自然语言关系是否是环境中的真实结构因果关系；
- 某个遗忘策略是否优于 BM25、RRF、Oblivion 或其他强基线。

这些问题仍需 propensity 日志、安全微干预、DR/MSM/OPE 与独立测试 episode 回答。

## 2. 数据单位与抽样

一个 `packet` 对应一个 LongMemEval 问题及其官方 gold evidence sessions。官方标签仅用于构造**评估包**，不得进入 query-independent memory writer，也不得用于训练本文方法。

| 问题类型 | 数量 | 研究目的 |
| --- | ---: | --- |
| multi-session | 70 | 跨事件组合、共同支持与关系拼接。 |
| temporal-reasoning | 50 | 时间点、顺序、持续区间和有效期。 |
| knowledge-update | 50 | 新旧事实、冲突、覆盖与版本化。 |
| single-session-preference | 30 | 偏好抽象、主体作用域和例外条件。 |

共200个问题包。每类按固定 SHA-256 排序选择；前10个进入 `pilot`，形成40包双人试标，其余160包在本体冻结后进入 `main`。

## 3. 术语表

| 规范术语 | 定义 |
| --- | --- |
| Evidence span | 原始 session 某一 turn 中的精确字符区间，是所有因子和关系的来源锚点。 |
| Factor | 可单独寻址的语义候选，如实体、属性、条件、行动、结果、时间或约束。 |
| Relation | 两个或多个因子之间的显式或必要推断关系。 |
| Abstract rule candidate | 由一个或多个证据支持、带显式作用域的可复用条件命题；仍是待验证假设。 |
| Scope | 规则或因子适用的主体、任务、时间、工具版本、权限或环境边界。 |
| Provenance coverage | 预测因子/关系能否完整指向支持其成立的原始证据跨度。 |
| Query-required component | 回答当前问题所需的最小因子或关系；仅用于评估任务充分性。 |

全文固定使用以上名称，不把 Factor 称为“真实因果变量”，不把 Abstract rule candidate 称为“已发现因果规律”。

## 4. 标注顺序

必须按以下顺序进行，不能先写规则再反向寻找证据：

1. 隐藏 `adjudication_only.reference_answer`；阅读问题和 evidence sessions；
2. 标记 Evidence spans；
3. 从跨度建立 Factors；
4. 标记 Relations、时间和作用域；
5. 标记 Query-required components；
6. 仅在有多个支持或明确可复用条件时提出 Abstract rule candidates；
7. 为每条规则写出至少一个 `counterexample_check`；
8. 完成第一遍后才允许查看参考答案，用于漏标核对，不得用答案中的新信息补写不存在于证据中的事实。

## 5. Evidence span

每个跨度必须包含：

```json
{
  "span_id": "sp_001",
  "session_id": "...",
  "turn_index": 0,
  "char_start": 12,
  "char_end": 37,
  "text": "exact substring from the turn",
  "role": "user"
}
```

规则：

- 使用 `[char_start, char_end)` 半开区间；`text` 必须与原文完全一致；
- 优先选择最小但语义充分的跨度；否定词、时间词和条件从句不得省略；
- 若一个关系跨两个句子或两个 session，分别建立跨度并在 relation 中同时引用；
- 不允许只引用整个 session 作为来源，除非确实无法缩小且在 `notes` 中说明原因。

## 6. Factor 本体

允许的 `factor_type`：

| 类型 | 示例含义 | 必须注意 |
| --- | --- | --- |
| `entity` | 人、组织、地点、对象、文档 | 主体身份与同名实体区分。 |
| `attribute` | 学位、职业、颜色、状态 | 属性值与持有者分开。 |
| `condition` | “若下雨”“在工作日” | 必须保留触发条件。 |
| `action` | 购买、调用工具、修改设置 | 区分计划、建议与实际执行。 |
| `outcome` | 成功、失败、症状、结果 | 不把预计结果标成已发生结果。 |
| `preference` | 喜欢、避免、优先级 | 必须绑定主体与适用对象。 |
| `time` | 时间点、区间、频率、相对顺序 | 记录标准化值与原文形式。 |
| `constraint` | 安全、权限、预算、禁止条件 | 低频高损失约束不得省略。 |
| `tool` | API、软件、设备、模型 | 同时记录版本或配置时拆成独立因子。 |
| `version` | 新旧事实、模型/工具版本 | 用于 update 和冲突解析。 |

Factor 结构：

```json
{
  "factor_id": "fa_001",
  "factor_type": "preference",
  "normalized_form": "prefers vegetarian food",
  "span_ids": ["sp_001"],
  "subject_scope": "user",
  "task_scope": "food-recommendation",
  "temporal_scope": null,
  "polarity": "positive",
  "evidential_status": "explicit"
}
```

`evidential_status` 只能为 `explicit / necessary_inference / hypothesized / contradicted`。`hypothesized` 因子不能进入 Query-required gold，也不能独立支持规则激活。

## 7. Relation 本体

允许的 `relation_type`：

- 结构：`is_a / has_attribute / belongs_to / part_of`；
- 时间：`before / after / during / valid_from / expired_at`；
- 更新：`updates / contradicts / supersedes / reaffirms`；
- 行动：`performs / uses_tool / produces / prevents / enables`；
- 条件与作用域：`applicable_under / scoped_to / exception_to`；
- 偏好：`prefers / avoids / indifferent_to`；
- 因果候选：`causal_candidate`。

`causal_candidate` 仅表示文本明确声称或任务要求检验因果联系，必须同时填写：

```json
{
  "relation_id": "re_001",
  "relation_type": "causal_candidate",
  "source_factor_ids": ["fa_001"],
  "target_factor_ids": ["fa_002"],
  "span_ids": ["sp_001", "sp_002"],
  "evidential_status": "hypothesized",
  "causal_validation_required": true
}
```

禁止仅因两个因素共同出现或语言模型给出解释，就将关系升级为已验证因果。

## 8. Abstract rule candidate

只有满足以下条件才提出规则候选：

- antecedent、consequent 和 scope 均明确；
- 所有变量有 Factor ID；
- 每项支持都能回溯至 Evidence spans；
- 局部偏好、一次性事件或特定版本不会被写成无条件规律；
- 至少写出一个可能使规则失效的反例检查。

```json
{
  "rule_id": "ru_001",
  "antecedent_factor_ids": ["fa_001"],
  "consequent_factor_ids": ["fa_002"],
  "scope": {
    "subject": "user",
    "task": "food-recommendation",
    "time": null,
    "tool_version": null
  },
  "support_span_ids": ["sp_001", "sp_002"],
  "status": "candidate",
  "causal_validation_required": true
}
```

## 9. Query-required component

Query-required gold 用于检验表示是否保持任务充分性，而不是训练检索器。标注最小充分集合：若删除某因子或关系会使答案无法由证据推出，则将其 ID 放入 `query_required_factor_ids`。对 multi-session 问题必须检查是否覆盖所有 gold sessions；不能只标最终答案字符串。

## 10. 双标、裁决与 Gate A

### Pilot 质控

40个 pilot 包由两名标注者独立完成，裁决前计算：

- Evidence span token-F1；
- Factor type micro/macro-F1；
- normalized factor matching F1；
- Relation type F1；
- provenance coverage；
- subject/task/time scope completeness；
- negation、temporal 与 update error rate；
- rule overgeneralization rate。

### 预注册通过门槛

| 指标 | Gate A 门槛 |
| --- | ---: |
| Factor micro-F1 | $\ge$ 0.80 |
| Relation F1 | $\ge$ 0.70 |
| Provenance coverage | $\ge$ 0.95 |
| Scope completeness | $\ge$ 0.90 |
| Negation/temporal/update error rate | $\le$ 0.10 |
| Rule overgeneralization rate | $\le$ 0.10 |

门槛应在查看全量 benchmark 结果前冻结，不能为保留某个模型而事后降低。若真实解构器未通过 Gate A，则停止全量规则抽象，退回 Raw evidence 或证据级治理。

### 可执行评分规则

[[score_semantic_gate_a.py]] 将上述门槛转化为确定性评分：

- Evidence span 以同一 session/turn 中的原文 token 位置计算 precision、recall 和 F1；
- Factor 匹配要求类型相同、normalized token Jaccard $\ge$ 0.5且来源跨度有非零重叠，再按词项与 provenance 加权得分进行一对一贪心匹配；
- Relation 匹配要求 relation type 及经 Factor 映射后的 source/target 集合一致；
- provenance coverage 要求匹配单元的来源 token-F1 $\ge$ 0.8；
- scope completeness 只统计 gold 中明确要求的 subject/task/time 字段；
- 漏掉的否定、时间或 update 单元计为错误，避免通过完全不预测来获得低错误率；
- 以 packet 为 bootstrap 单位重复1,000次。对于“越大越好”指标使用95%区间下界判定，对于错误率使用区间上界判定，而不是只看点估计。

```powershell
python score_semantic_gate_a.py `
  longmemeval_semantic_gate_a_200.jsonl `
  predictions.jsonl `
  --split pilot `
  --bootstrap-samples 1000 `
  --output gate_a_score.json
```

评分器只评估表示忠实度、证据谱系和作用域；其 `passed=true` 也不构成因果效应或端到端治理优势证明。

## 11. 盲法与数据泄漏防护

1. `answer_session_ids` 只用于构建评估包；系统预测阶段不得读取该字段；
2. 第一遍人工标注隐藏参考答案；
3. pilot 可用于本体和说明书修订，不用于调最终测试阈值；
4. main 集在本体冻结后标注，模型开发与最终评估划分另行固定；
5. 人工语义标签不是因果效应金标；任何因果主张仍需独立干预数据。

### 文件版本与不可变身份

- `longmemeval_semantic_gate_a_200.jsonl` 是只读空模板，不直接覆盖；每名标注者复制为独立工作文件；
- manifest 同时记录空模板整文件 SHA-256 与排除 `annotation` 字段后的 `packet_identity_sha256`；
- 人工填写后整文件哈希可以变化，但问题、证据 session、turn、参考答案和 split 等不可变内容必须继续匹配 `packet_identity_sha256`；
- 校验器检查跨度字符偏移、role、Factor/Relation/Rule ID 引用、provenance、枚举本体与 causal-validation 标记；未通过校验的文件不得进入一致性或模型评分。

## 12. 需要人工确认的事项

- 最终是否由两名独立标注者完成全部200包，或仅对 pilot 与20% main 双标；
- 目标投稿 venue 对数据再分发和附录规模的要求；
- 是否公开原始对话文本，或只发布 question/session ID、跨度和派生标签。

## 相关文件

[[longmemeval_semantic_gate_a_manifest.json|数据清单]]、`longmemeval_semantic_gate_a_200.jsonl`、[[../LongMemEval-S可审计关系Sidecar实验报告|POS-v2关系Sidecar负结果]]、[[../../06-解构抽象能力的学术化界定与因果架构融合|学术化方法界定]]
