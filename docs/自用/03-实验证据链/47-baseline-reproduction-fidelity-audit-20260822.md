# Baseline Reproduction Fidelity Audit（2026-08-22）

## 结论

当前五个具名基线**都不能称为论文系统的精确复现**。现有工作更准确的定位是：

| 基线 | 当前实现最准确的名称 | 复现精度 | 是否可用于 lifecycle gap 构造实验 |
|---|---|---|---|
| CMI | query-local causal-effect / observational control | 低到中 | 可以，但只能挑战 local-effect sufficiency，不得写成 CMI 系统失败 |
| Memory Worth | MW-shaped associational proxy | 中（公式形状保留，信号不等价） | 可以，但必须声明 signal substitution |
| DeMem | decision-distinction heuristic | 低 | 可以作为 heuristic control，不能代表 DeMem learner |
| Trivium | demand-weighted effect control | 低 | 可以作为 temporal-demand control，不能代表 Trivium |
| GovMem | access-time coverage control | 不可迁移 | 不应作为 GovMem 结果；只能保留为内部 coverage control |

判断依据严格分为 `[论文]`、`[代码]`、`[实验]`、`[推断]` 和 `[未验证]`。

## 1. CMI

### 论文机制

`Causal Intervention-Based Memory Selection for Long-Horizon LLM Agents`（arXiv:2605.17641）定义的是候选记忆级的受控 intervention：

1. no-memory 条件得到 (s_{no})；
2. with-memory 条件得到 (s_{with})；
3. perturbed-memory 条件得到 (s_{pert})；
4. (Utility=s_{with}-s_{no})，(Stability=s_{with}-s_{pert})；
5. 依据 Utility/Stability threshold 选择记忆，并对 risky memory 做 veto。

`[论文]` 该机制和 Causal-LoCoMo 在 arXiv 摘要中明确说明。`[代码]` 官方仓库 [Saksham4796/causal-memory-intervention](https://github.com/Saksham4796/causal-memory-intervention) 的 `src/agents/cmi_agent.py` 实际实现了 no/with/perturbed 三路、Utility/Stability 和 risk veto。

### 当前代码对照

- `[代码]` `src/sqcad/public_unified_contract.py:790-810` 的 `causal_item` 只计算 BM25 exposure 下 query-overlap value 的 observational contrast；没有 LLM no/with/perturbed 运行。
- `[代码]` `src/sqcad/public_online_baselines.py:187-225` 的 `causal_item_online` 是同一 naive exposure contrast 的 chronological 版本。
- `[代码]` `src/sqcad/unified_baseline_runner.py:665-670` 的 `causal_item` 依据合成 `item_effect_lcb` 排序，并通过统一 probe contract 补齐 unidentified item；这不是官方 CMI agent。
- `[代码]` `src/sqcad/baseline_internal_gap_audit.py:175-176` 的 `cmi_local` 只是 `local_relevance - correction penalty`，连 observational exposure contrast 都不是。

### 判断

现有 CMI 行可支持的说法是：

> “query-local causal-effect estimand 的生命周期充分性构造性反例”。

不能支持：

> “我们复现了 CMI 并证明 CMI 在 lifecycle memory 上失败”。

若要升级为 CMI reproduction，最小补齐是直接运行官方 `CMIAgent`，固定其 API/model/config，记录每个 candidate 的 (s_{no},s_{with},s_{pert})、Utility、Stability、threshold 和最终 selected IDs，再在同一 paired lifecycle intervention 上评估。

## 2. Memory Worth

### 论文机制

`When to Forget: A Memory Governance Primitive`（arXiv:2604.12007）使用每条 memory 的两个计数器：

\[
MW(m)=\frac{hits^+(m)}{hits^+(m)+hits^-(m)},
\]

其中计数来自 memory 被实际检索条件下的 episode success/failure。论文明确说明它收敛到 associational quantity

\[
p^+(m)=P(y_t=+1\mid m\in M_t),
\]

而不是 causal contribution。

### 当前代码对照

- `[代码]` `src/sqcad/public_unified_contract.py:470-478` 对每个 query 与所有 message 做 lexical overlap，并把 overlap 当作 hit；它没有判断 memory 是否进入实际 exposed workspace，也没有真实 episode success/failure。
- `[代码]` `src/sqcad/public_online_baselines.py:148-152` 同样对所有 message 更新 counters，不受当步 retained workspace 限制。
- `[代码]` `src/sqcad/unified_baseline_runner.py:636-641` 使用 candidate 预生成的 `success_rate` 与 implicit-100 history，而不是运行两个计数器。
- `[代码]` `src/sqcad/baseline_internal_gap_audit.py:203-208` 使用 decision local relevance 作为 `local_success_rate`，因此只是更进一步的 constructed associational proxy。

### 判断

Memory Worth 是五者中“score 形式”最接近的一个，但**信号替换改变了 estimand**。当前结果可以称为 `MW-shaped query-overlap proxy`，不能称为“正确估计的 Memory Worth”。原有文档中“正确实现 two counters”或“correctly estimated quantity”的措辞需要收窄。

最小修复是构造一个真正的 chronological MW runner：只有 memory 实际进入当步 workspace 时才更新 (hits^+) 或 (hits^-)，success/failure 必须来自统一 evaluator 的当步 episode outcome；同时保留 query-overlap proxy 作为单独控制。

## 3. DeMem

### 论文机制

`Remember the Decision, Not the Description: A Rate-Distortion Framework for Agent Memory`（arXiv:2605.10870）不是“把 item effect 与均值作差”。论文的核心是：在固定预算下，以可达 decision quality 的损失定义 rate-distortion，并由**certified decision conflict** 触发 online memory partition refinement，同时给出 near-minimax regret。

### 当前代码对照

- `[代码]` `src/sqcad/public_online_baselines.py:95-99` 使用 (|posterior-mean(posterior)|)。没有 partition state、decision conflict certificate、merge/split/refinement 或 rate-distortion objective。
- `[代码]` `src/sqcad/unified_baseline_runner.py:659-664` 使用 (|group\_effect\_lcb-mean\_effect|)，只是 group-level distinction ranking。
- `[代码]` `src/sqcad/baseline_internal_gap_audit.py:170-172` 使用 local relevance 偏离候选均值，同样没有 DeMem learner。
- `[代码]` `docs/自用/03-实验证据链/15-基线开源状态与无GPU复现审计-20260813.md:50-52` 过去把当前行描述为“decision-conflict-gated retention”，与实际代码不一致，已收窄为 distinction heuristic。

### 判断

DeMem 当前只能作为“decision-distinction heuristic control”。它可以测试“简单 distinction score 是否保留某些构造性区分”，不能支持“DeMem 的 exact forgetting boundary / near-minimax learner 在 lifecycle gap 中失败”。若要精确复现，需要先形式化论文的 partition state、conflict certification 和 update rule，再做 online chronological replay。

## 4. Trivium

### 论文机制

`Trivium: Temporal Regret as a First-Class Objective for Causal-Memory Controllers`（arXiv:2606.04421v3）包含 persistent causal log、outcome/temporal/epistemic regret 分账、detectability/change-point 假设和 budgeted causal probes。论文摘要还明确说明 logarithmic result 只适用于 identification delay，不是普通 comparator regret。

### 当前代码对照

- `[代码]` `src/sqcad/public_online_baselines.py:102-108` 只是 `(1 + prior lexical hits) * base score`。
- `[代码]` `src/sqcad/unified_baseline_runner.py:671-683` 只是 `effect * demand(required_group)`，probe 使用统一 runner 的 synthetic oracle-style `_probe_qualification`，不是 Trivium causal log/probe policy。
- `[代码]` `src/sqcad/baseline_internal_gap_audit.py:179-181` 使用公开 future-query demand，且显式标为 transductive upper-bound；没有 temporal/epistemic posterior ledger。

### 判断

当前 Trivium 行不是 Trivium reproduction，而是“demand-weighted effect control”。它可以用于检验 demand weighting 的构造性敏感性，不能用于声称 Trivium 的 temporal-regret/probe 机制失败。过去“Trivium probe-layer row”表述过强，已收窄。

## 5. GovMem

### 论文机制

`When Not to Write Memory: Governing False Promotion from Correlated Agent Traces` 是 write-time policy：从 dependency-aware support 与 counterevidence 中作 `promote / reject / needs-review` 决定。它并不是一个已定义的 access-time keep/archive retention score。

### 当前代码对照

- `[代码]` `src/sqcad/public_online_baselines.py:111-117` 的 `_coverage_loss` 仅按 prior query hit count 排序。
- `[代码]` `src/sqcad/public_online_baselines.py:34-37` 曾把该行解释为“evict what minimises expected future loss”，但没有 dependency graph、counterevidence、review state 或 write-time promotion。
- `[代码]` `src/sqcad/baseline_internal_gap_audit.py:184-186` 仍是 access-time coverage control。

### 判断

GovMem 在当前合同下应标为 `not transportable`，而不是 paper-mechanism proxy。保留该实现的唯一合理方式是改名为 `prior_query_coverage_control`，作为内部控制；它不能进入“具名 GovMem 基线”的 lifecycle gap 结论。

## 6. 对现有结果和论文措辞的影响

现有 LoCoMo/LME-S 数字可以保留为**五种简化控制的合同层结果**，但不能再写成“五个论文基线的复现结果”。尤其是：

- online 与 batch 的差异只是当前 10 conversations/冻结 reader 下的敏感性检查，不是未来查询泄漏的一般上界；
- `CMI + DeMem + Trivium + GovMem` 的低 F1 只能说明这些简化控制在该合同下表现弱，不能说明对应论文系统表现弱；
- baseline-internal gap audit 中 CMI/DeMem/Trivium/GovMem 的 score-fiber witness 是 heuristic/control witness，不是对论文算法本身的 failure witness；
- Memory Worth 的 witness 可以保留为 associational-score failure，但必须写成 signal-substituted proxy。

## 7. 最小补齐顺序

1. 先直接运行 CMI 官方仓库的小型 CausalMemBench/Causal-LoCoMo 子集，记录三条件 intervention trace。
2. 重写 Memory Worth 为真实 retrieval-conditioned success/failure counter；query-overlap 另列 control。
3. 若没有 DeMem/Trivium/GovMem 官方代码，按论文伪代码分别实现 partition-conflict、causal-log/probe、write-time promotion 三个独立 runner；不能继续用一个 scalar heuristic 代替。
4. GovMem 在 access-time 主表中删除；除非定义并预注册 write-time-to-access-time transport protocol。
5. 重新生成结果表和 lifecycle gap audit，并把 evidence level 设为 `[代码]`、`[实验]` 的具体层级，不再使用具名系统泛化措辞。

