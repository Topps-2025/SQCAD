# Faithful Baseline Reproduction（round7，2026-08-22）

本轮将历史 unified-contract proxy 与论文/仓库机制的 faithful core 分离。新增
`src/sqcad/faithful_baseline_reproduction.py`、
`tools/run_faithful_baseline_reproduction.py` 和专项测试。旧 proxy 行没有被覆盖，
因此历史结果仍可追溯，但不再被称为五个论文系统的复现结果。

## 证据等级

| 系统 | 新 runner | 当前等级 | 严格边界 |
|---|---|---|---|
| CMI | `CMIProtocol` | `[代码] official-code faithful core` | 已实现 no/with/perturbed、Utility、Stability、threshold、风险 veto；HybridRetriever、LLM answer/scorer 由调用方注入；未声称已跑完整官方 benchmark |
| Memory Worth | `MemoryWorthProtocol` | `[论文] paper-mechanism faithful core` | 只在实际 `exposed_ids` 上更新 success/failure 两计数器；决策严格使用前序历史；不接受 query-overlap 作为 outcome |
| DeMem | `DeMemProtocol` | `[论文] paper-mechanism faithful core (partial)` | 显式 partition、certified decision conflict、在线 refinement；论文未唯一规定的 decoder/judge/阈值保留为 unresolved |
| Trivium | `TriviumProtocol` | `[论文] paper-mechanism faithful core (partial)` | 持久 causal log、预算 probe、posterior 更新、outcome/temporal/epistemic regret ledger；change-point 与 probe utility 的论文配置仍需注入 |
| GovMem | `GovMemProtocol` | `[论文] paper-mechanism faithful core` | 独立 write-time support/counterevidence adjudication，输出 promote/reject/needs-review；不把 access-time coverage control 冒充 GovMem |

## 输入合同

每个 `BaselineEpisode` 是按时间顺序输入的单个 episode：

- `exposed_ids`：实际进入 workspace 的 memory，不是 lexical overlap；
- `success`：统一 evaluator 的 episode success/failure；
- `cmi_scores`：CMI smoke run 的三路 evaluator 分数；
- `decision_label`/`conflict_feature`：DeMem 的决策证据与冲突细化证据；
- `probe_candidates`/`probe_observations`：Trivium 的 probe 和 causal/regret 观测；
- `write_evidence`：GovMem 写入时的 support/counterevidence。

CLI 示例：

```powershell
$env:PYTHONPATH='src'
python tools/run_faithful_baseline_reproduction.py `
  --input tests/fixtures/faithful_baseline_contract.json `
  --output results/faithful_baseline_smoke.json
```

输出中的每条决定包含 evidence level、状态、原始证据和 unresolved 列表。

## 关键实现核对

### CMI

对每个 episode 先取无记忆分数 `s_no`，再对每个 retrieved candidate 运行单条
`with_memory` 与 perturbed-memory 条件：

\[
U(m)=s_{with}(m)-s_{no},\qquad
S(m)=s_{with}(m)-s_{perturbed}(m).
\]

当 `U > utility_threshold` 且 `S >= stability_threshold`，并且不触发官方仓库
的 risky/harmful veto 时才选择。该逻辑与官方 `CMIAgent` 的选择路径一致；
当前 smoke runner 使用 caller-provided evaluator，不能等同于已调用真实 LLM。

### Memory Worth

每条 memory 保留 `hits_plus` 与 `hits_minus`。episode 决策发生在 outcome 更新
之前，只有实际 `exposed_ids` 才更新：

\[
MW_t(m)=\frac{hits^+_{<t}(m)+\alpha}
{hits^+_{<t}(m)+hits^-_{<t}(m)+\alpha+\beta}.
\]

因此不会看到未来 query，也不会把“相关词出现”伪装成 success。

### DeMem

状态是 memory partition。若同一 partition 在不同历史 episode 中出现互相冲突的
decision label，则只有在给定 `conflict_feature` 时执行 split/refinement，并记录
冲突 certificate；这保留了论文的 decision-centric distinction，而不是旧的
`abs(effect - mean(effect))`。

### Trivium

状态跨 episode 持久保存 causal log。每次只在预算内 probe 候选，并分别累加
outcome、temporal、epistemic regret；未知候选按 posterior uncertainty 排序，
而不是读取未来 query demand。精确 change-point detector 与 probe utility 参数
必须由目标论文配置或真实 agent 提供，当前输出明确为 partial。

### GovMem

它被实现为 write-time policy：support、counterevidence、dependencies 先组成
candidate evidence，再作 `promote`、`reject` 或 `needs-review`。依赖缺失默认进入
review。该 runner 不提供 access-time keep/archive 数字，因为那不是 GovMem 的论文
机制。

## 验证结果

- `pytest -q tests/test_faithful_baseline_reproduction.py`：5 passed。
- 相关回归：`tests/test_baseline_internal_gap_audit.py`、
  `tests/test_unified_baseline_runner.py`、`tests/test_cost_contract_experiment.py`：
  全部通过（本轮运行共 38 passed）。
- CLI smoke：成功生成 `results/faithful_baseline_smoke.json`，五个基线均输出独立结果。
- `python -m py_compile`：通过。
- `git diff --check`：无 whitespace error；仅报告工作树既有的 CRLF 转换警告。

## 不能过度宣称的部分

本轮完成的是可复核的机制级 faithful core，不是完整论文 benchmark 复现。要升级
到 `[实验] full reproduction`，还需要固定官方仓库 commit、retriever/model/config、
真实 LLM evaluator、数据集 split、seed、成本和 latency，并重新跑 paired lifecycle
实验。特别是 DeMem、Trivium 的 partial 项，不能把当前 runner 的结果写成论文作者
实现的最终性能。
