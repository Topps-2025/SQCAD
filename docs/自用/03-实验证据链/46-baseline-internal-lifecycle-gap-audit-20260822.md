# Baseline-internal Lifecycle Gap Audit（2026-08-22）

> **Fidelity re-audit note (2026-08-22):** this report's numerical rows are
> constructive score controls.  The subsequent fidelity audit confirms that
> CMI, DeMem, Trivium and GovMem rows must not be called paper-mechanism
> reproductions; Memory Worth is only an associational proxy because the
> success/retrieval signal is substituted.  See the dedicated audit in
> `47-baseline-reproduction-fidelity-audit-20260822.md`.

## 1. 目的与证据边界

本报告执行的是**基线内部缺口诊断**，不是 SQCAD 与基线的性能比较。对每个基线先冻结它自己的 scalar score (S_b(x))，再在同一个 LifecycleBench episode 上执行统一的 keep/archive paired intervention，并由独立 evaluator 计算

\[
\Delta(x)=V^K(x)-V^A(x).
\]

要检验的不是“SQCAD 分数更高”，而是现有 score 是否已经编码 lifecycle information：

\[
S_b(x_1)\simeq S_b(x_2),
\qquad
\Delta(x_1)\neq\Delta(x_2).
\]

若同一 score fiber 还出现

\[
\Delta(x_1)<0<\Delta(x_2),
\]

则在固定成本合同下得到 score-only action 的 opposite-sign witness。若只存在同号但不同的 contrasts，则只报告 cost-shift witness，不把它升级为固定成本 failure。

所有结果均为 `[实验]` 的构造性算法证据；不能写成自然任务 external-validity、完整官方系统复现或所有 Agent 的普遍失败结论。

## 2. 实验合同

实现：`src/sqcad/baseline_internal_gap_audit.py`；运行器：`tools/run_baseline_internal_gap_audit.py`；结果：`results/baseline_internal_lifecycle_gap_audit_20260822.json`。

- 主样本：LifecycleBench 每个 `(family, variant, entity)` 取一个确定性 episode，共 25 个 episode。
- 配对 rollout：同源 future stream，唯一干预是 decision-point 的 keep/archive 持久动作。
- baseline score：只由 `PublicDecisionView` 计算，字段不含 `needed_future_ids`、`oracle_action`、`tau` 或 evaluator 的 lifecycle value。
- score fiber：将 score 四舍五入到 8 位后做 exact equality；这是一个保守、可复现的 collision 定义。
- identification positive control：另取 4 个 observation-equivalent hitchhiker pairs，共 8 个 episode。它们的 public trace 相同但 hidden needed id 翻转，专门检验不可识别性；不计入任何基线的 \(\widehat\varepsilon_{\rm LC}\)。

对一个 score fiber \(F_s\)，报告

\[
\widehat\varepsilon_{\rm LC}(s)
=\max_{x_i,x_j\in F_s}|\widehat\Delta_i-\widehat\Delta_j|,
\]

以及全样本中的最大 witness。异号 fiber 的 randomized minimax regret 为

\[
R_{\rm rand}^*(d_+,d_-)
=\frac{d_+d_-}{d_++d_-},
\quad
d_+=\Delta_+,
\quad d_-=-\Delta_-.
\]

若仅有同号差异，报告 midpoint cost shift 下界

\[
R_{\rm shift}\ge \frac14|\Delta_i-\Delta_j|.
\]

## 3. 覆盖的基线 surface

| surface | 证据等级 | 冻结的 score | 允许的解释 |
|---|---|---|---|
| `simplemem_lexical` | official-code surface + constructed intervention audit | SimpleMem `keyword_search` 的 raw-row lexical channel；关键词列表/LLM compression/embedding 未接入 | 只挑战已验证 lexical surface，不挑战完整 SimpleMem |
| `oblivion_decay` | transported official rule + constructed intervention audit | 官方已核对的 decay rule：\(\exp[-\mathrm{age}/((\mathrm{utility}+\mathrm{frequency})T)]\) | 只覆盖 decay equation；LLM uncertainty/Qdrant 层未复现 |
| `memory_worth` | associational signal proxy | Beta(1,1) 后验成功率的 signal-substituted proxy | 不能称论文机制的精确复现 |
| `fademem` | internal proxy | differential decay：\(\log(1+f)e^{-a/\tau_{sem}}\) | 仅命名 proxy；Agent-memory 官方实现未核实 |
| `demem` | internal distinction heuristic | 与候选平均 local relevance 的 heuristic distinction | 不是 DeMem certified-conflict partition learner |
| `cmi_local` | internal local-effect heuristic | 决策前 relevance/correction proxy | 不是 CMI no/with/perturbed intervention |
| `trivium` | internal demand/effect control | local effect × 折扣后的公开 future-query demand | 无 persistent causal log / budgeted causal probes |
| `govmem` | not transportable as GovMem | prior-session coverage + semantic tie-break control | GovMem 是 write-time policy，不是 access-time retention |

ActMem、SAGE、MemAudit、GateMem 没有被硬凑进数值表：ActMem 当前只有 partial mechanism path，后三者没有可公平迁移的 scalar keep/archive score，分别标为 partial/not-transportable。

## 4. 结果

| baseline | future-kernel non-null rate | value-relevant rate | heterogeneous fibers | opposite-sign fibers | 最大 \(\widehat\varepsilon_{\rm LC}\) | 最大 fixed-cost randomized regret |
|---|---:|---:|---:|---:|---:|---:|
| SimpleMem lexical | 1.00 | 0.88 | 4 | 2 | 159.7820 | 30.3748 |
| Oblivion decay | 1.00 | 0.88 | 1 | 1 | 159.7820 | 30.3748 |
| Memory Worth | 1.00 | 0.88 | 4 | 2 | 159.7820 | 30.3748 |
| FadeMem proxy | 1.00 | 0.88 | 2 | 1 | 123.2040 | 4.0639 |
| DeMem proxy | 1.00 | 0.88 | 4 | 3 | 159.7820 | 30.3748 |
| CMI local proxy | 1.00 | 0.88 | 3 | 2 | 159.7820 | 30.3748 |
| Trivium proxy | 1.00 | 0.88 | 0 | 0 | 0.0000 | 0.0000 |
| GovMem proxy | 1.00 | 0.88 | 4 | 2 | 122.5390 | 3.4402 |

代表性最大 witness 是 `version_update/update_before` 与 `version_update/update_after`：在多个 score surface 上两者 score 相同，但

\[
\Delta_1=-118.9964,\qquad
\Delta_2=40.7856,
\]

因此

\[
|\Delta_1-\Delta_2|=159.7820,
\quad
R_{\rm shift}\ge39.9455,
\quad
R_{\rm rand}^*\approx30.3748.
\]

该构造把“历史上看起来同样有用的 phone/contact memory”与未来 version update overlay 分开：即时 score 相同，但持久 keep/archive 对后续 candidate/evidence state 的影响不同。这个结果支撑的是**score-only lifecycle sufficiency 的算法反例**，不是声称这些基线在所有自然任务都失败。

Trivium 在本次 25-episode、8 位 exact-score 规则下没有 score collision，因此报告零，而不是人为放宽 fiber 或挑选结果。这说明该小实验也能给出负结果；Trivium 是否在更大自然轨迹中具有非零 \(\varepsilon_{\rm LC}\) 仍未验证。

## 5. 不可识别性正控

4/4 observation-equivalent pairs 都出现 oracle flip：

\[
\Delta_{base}=-7.5936,
\qquad
\Delta_{flip}=4.2162.
\]

两条 public trace 完全相同而 hidden needed id 不同，因此任何只依赖该 public trace 的 baseline 都无法区分它们。这不是某个 baseline 的 score omission，而是 identification positive control；它不进入 baseline-specific \(\widehat\varepsilon_{\rm LC}\) 或“抨击某基线”的统计量。

## 6. 对 research gap 的支持与边界

本轮直接补齐了 gap 的第一层证据：在同一构造 Agent 环境内，多个具名/机制 baseline 的 scalar score fiber 中存在 lifecycle-value heterogeneity，且在大多数 surface 上存在 fixed-cost opposite-sign witness。数学上，这正是 G2/G4 所需的“score quotient 未能把 future kernel 压缩为 action-sufficient statistic”的可执行 witness。

本轮没有完成三件事：

1. 没有证明完整官方 Agent memory system 在自然任务中普遍 future-lossy；
2. 没有估计真实轨迹上的 per-action conditional KL、recoverability cost 或自然 utility separation；
3. 没有比较 SQCAD 修复后的 \(\widehat\varepsilon_{\rm LC}\) 是否下降。

因此下一阶段应在保持同一 paired intervention contract 的真实/公开 Agent traces 上做 score-fiber audit，再单独进行 SQCAD repair experiment：

\[
\widehat\varepsilon_{\rm LC}(T_{\rm SQCAD})
<
\widehat\varepsilon_{\rm LC}(S_b),
\]

并报告自然 task utility、成本和 bootstrap/paired confidence interval。
