# SQCAD-LifecycleBench（SQCAD-LB）数据集构建方案

## 1. 定位

LongMemEval-S 与 LoCoMo 继续承担公开外部验证：候选覆盖、证据召回、QA F1、token/storage/probe/restore 成本、版本冲突和 archive 后的访问恢复。它们没有同一持久动作在未来的对照轨迹，不能单独证明 keep/archive 的生命周期价值。

为检验 SQCAD 的核心主张，构建 SQCAD-LifecycleBench（SQCAD-LB）：一个由自然语言轨迹、隐藏可执行世界、持久动作反事实分支和独立评测器组成的 Agent Memory 基准。

## 2. 目标对象

对记忆 $i$、scope $s$，比较 $\tau(i,s) = V_s^\pi(\operatorname{keep}_i) - V_s^\pi(\operatorname{archive}_i)$。其中 $V_s^\pi(a)$ 是从持久动作决策点开始，到预注册 horizon 结束的折扣效用、风险和访问成本总和。keep/archive 必须改变未来候选生成、曝光机会、workspace 竞争和恢复路径；若只改变当前 QA 的 top-k，仍只是 retrieval benchmark。

## 3. 数据合同：六个必备特征

### 3.1 持久动作分支

每个关键记忆在同一决策点 fork 出至少两条分支：Branch-K（keep，进入 persistent store 与普通候选池）和 Branch-A（archive，不进入普通候选池，仅可由有限 probe 临时访问）。可选 Branch-P 用于测试 probe 后 restore。

### 3.2 真正的 chronological future

决策后必须有按时间展开的未来事件：新任务、版本更新/纠错、低频 bridge 需求、竞争性干扰、scope 变化和可执行工具/行动结果。任何 policy 只能看到当前时刻以前的信息。

### 3.3 可执行 outcome

隐藏评测器逐步计算 answer/action utility、harm penalty、storage/exposure/probe/latency cost、stale-version use、unsafe action 和 scope/policy violation。horizon、discount、预算及成本权重在生成前冻结；答案准确率只是 outcome 的组成部分。

### 3.4 同源反事实

keep/archive 分支共享未来用户事件、任务难度、工具返回、外部变化和随机数流；唯一允许不同的是持久动作及由此导致的候选、曝光与 Agent 行为。这样分支差异才能归因于记忆治理。

### 3.5 隐藏可核验标签

evaluator 独占 lifecycle_value_keep、lifecycle_value_archive、tau_keep_archive、oracle_action、needed_future_ids、harmful_exposure、rescue_possible、scope_validity 和 identification_regime。Gold 不得进入被测 policy 输入。

### 3.6 压力与不可识别世界

必须包含：观测等价但最优动作相反、局部效应相同但生命周期价值相反、共暴露 bundle、低频 bridge、archive-induced self-obscuring、scope/version drift、未来才显现风险的 stale memory。另设 stable-positive、stable-negative 与 neutral controls。

## 4. 三层数据结构

Public Trace Layer 公开历史对话、允许的时间/session/provenance/scope 字段、当前任务、候选提议、预算与工具接口；隐藏未来 needed ids、分支结果、oracle action、latent role 与 hidden confounder。

Policy Log Layer 统一记录 candidate、qualification request/state、persistent action、exposure、adoption、tool/action、outcome、cost、state transition 和 next candidate set。

Hidden Counterfactual Layer 由 evaluator 独占 keep/archive 分支、潜在结果、未来依赖图、oracle、识别 regime、干预有效性、生成器版本与随机种子。

## 5. Agent 合成：双 Agent + 独立世界模拟器

不能让同一个 LLM 同时生成样本并决定因果真值。

1. **Scenario Designer** 生成冻结的结构化模板：实体、旧/新事实、scope、风险类型、未来事件槽位和依赖图；不生成 oracle outcome。
2. **Trace Realizer** 将模板变为多 session 自然对话、任务、工具调用和纠错；允许同义表达、指代、多跳、无关高频信息及 hitchhiker，但必须通过 schema 校验：不得泄露未来或改写冻结事实。
3. World Simulator 维护 user、task、memory、tool、risk 和 candidate-generator 状态；在决策点复制状态，使用相同未来事件和随机数运行 paired rollout。事实依赖、风险、候选变化和任务成功由可审计规则决定；LLM 只负责文本表面。
4. Independent Evaluator 读取隐藏世界、分支结果和 policy log，计算 $\tau$、false commit、lifecycle regret、harmful exposure、rescue 与总成本。

## 6. 首版场景族

高频 hitchhiker：与有用证据共现但无增量价值；低频 bridge：稀有未来任务依赖其检索通路；版本更新：新旧事实适用时间不同；harmful stale：旧事实触发错误或风险；self-obscuring：archive 后证据不再自然进入候选；scope mismatch：同一实体在不同 user/tool/model 版本含义不同；co-exposure bundle：单条不可分但 bundle 可治理；local-vs-lifecycle conflict：当前有用但长期挤占关键路径。

另设稳定正例、稳定负例和 neutral controls，避免方法只会弃权。

## 7. 生成与评测阶段

Phase A 使用规则世界主验证：精确计算反事实价值、检查分支唯一差异、构造观测等价世界并做 paired bootstrap。自然语言可以由 Agent 生成，但 LLM 不决定真值。

Phase B 从规则世界抽取代表 episode，冻结 reader/agent、prompt、工具和模型版本，只切换 persistent memory state；由工具环境和独立 evaluator 判定 outcome。

Phase C 在 LongMemEval-S/LoCoMo 上继续运行 Guard-1、BM25/dense/RRF 与生命周期控制基线，报告覆盖、QA、成本、版本冲突和恢复；不把这些结果写成因果资格证明。

## 8. 数据切分、防泄漏与公平性

- 按 scenario template、domain、user、entity、事件组合分组切分，不能按 QA 随机切分；
- 同一 episode 的所有分支和 QA 必须在同一 split；
- test 保留 unseen domain、scope 组合和冲突模式；
- prompt、world version、seed、成本合同、budget、reader/evaluator 版本进入冻结 manifest；
- 所有基线共享 public trace、未来事件、budget、reader/agent、工具、成本合同与 hidden evaluator。

推荐 train/dev/test 为 60/20/20；若仅作 benchmark，可只公开 trace 与 dev evaluator。

## 9. 指标与基线

资格层：false-commit rate、safe-commit rate、abstention precision、interval coverage、scope/version mismatch detection、bundle unresolved rate。

访问层：lifecycle regret、future evidence recall、harmful exposure、rare-bridge rescue、archive-induced false forgetting、probe action-change rate、restore precision、time-to-recovery。

成本：persistent/exposure tokens、probe/restore 次数与 token、latency、预注册成本合同下的 net utility。

基线分三组：

- 检索基线：BM25、dense、RRF、keep-all；
- 生命周期基线：FIFO、LRU、recency、固定/频率衰减、Memory Worth、CMI local-effect proxy；
- 授权/探测基线：blind point gate、forced commit、always defer、random probe、BM25-score probe、VOI probe，以及 SQCAD 的 no-qualification、no-censoring、no-restore、no-lineage/version-gate 消融。

## 10. SQCAD-LB-MVP

第一版使用 6 类场景：hitchhiker、rare bridge、version update、harmful stale、self-obscuring、scope mismatch；每类 200 个 episode；每个 episode 1 个持久决策点；每个决策点保留 keep/archive paired rollout；每条 rollout 10 个未来任务；outcome 由规则计算，自然语言由 Agent 生成。

Go/No-Go 判据：

1. SQCAD 比 blind commit 少 false commit；
2. SQCAD 比 always defer 有更多安全 commit；
3. VOI probe 比随机/BM25 probe 以更低成本更常改变正确动作；
4. 在相同或更低 lifecycle regret 下，storage/probe 成本可接受。

## 11. 证据分工与实现建议

LongMemEval-S/LoCoMo 负责公开轨迹的覆盖、QA 与系统成本外部效度；SQCAD-LB 负责反事实 lifecycle、资格授权、probe/restore 与 regret；真实 Agent rollout 负责部署外部效度。

建议新增 src/sqcad/lifecycle_bench/，包含 world.py、scenarios.py、realizer.py、rollout.py、evaluator.py、generator.py 和 tests/test_lifecycle_bench_contract.py。它不直接并入 public contract；两者可复用预算与 bootstrap，但不可混用 gold 语义。
