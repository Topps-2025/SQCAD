# 39- badcase 驱动 paired 消融与 sentinel 成本门控（2026-08-21）

## 1. 目的与统计合同

本轮只检验自建机制世界，不把结果外推为公开数据或真实用户流量结论。每个 seed 生成一个完整的半合成触发世界；所有 policy 在同一世界和同一候选流上运行，配对键为 `scenario + seed + candidate_stream_sha256`。统计单元是独立 world seed，而不是 episode 或 task。每个差异使用 paired studentized bootstrap，`n_boot=2000`，预注册 seeds `20260812/20260817`，`alpha=0.05`。当 `n<2` 时只报告 insufficient，不生成置信区间。

实现和输出：

- `src/sqcad/minimal_framework_challenge_benchmark.py`
- `results/minimal_framework_challenge_triggered_guarded_v2_20260821.json`
- 代码源 SHA：`903F92B851E752682EE1CA3E26071B84E31744AF8D753FE714A8A3F75495D52C`
- 输出 SHA-256：`D655476133416730C81AEDBDC0AF9F753735EA71BC2233FED635FA89F2B2F97F`

## 2. badcase 发现

原 `hierarchical_sentinel_candidate` 无条件把高语义 sentinel 加入 item-level probe pool。64 个独立触发世界中，相对 `hierarchical_candidate`：

| 对比 | utility 差异 | regret reduction | probe-cost 差异 | 解释 |
|---|---:|---:|---:|---|
| 无条件 sentinel − hierarchical | `−0.121` [`−0.149`, `−0.087`] | `−0.094` [`−0.113`, `−0.071`] | `+0.193` [`+0.180`, `+0.203`] | 真实 sentinel badcase：额外探测成本和错误路径超过收益 |

该结果不是单条轨迹现象；CI 在两个 bootstrap seed 下均排除零。它不支持“sentinel 一定有益”，只支持“无条件 sentinel 在该触发构造上有害”。

## 3. 框架修改

新增 `hierarchical_sentinel_guarded`，只改变 sentinel 的纳入门控：

1. 先按原规则生成 group-level shortlist 和 sentinel 候选；
2. 计算 sentinel 的一步 qualification EVSI，相对于当前候选池的最优 fallback；
3. sentinel 是尚未授权的探索，因此 EVSI 必须覆盖**未折扣的完整干预成本**；
4. 不满足时 sentinel 不进入 item-level probe pool；主候选、恢复、因果资格和 reader 均不改变。

该规则没有使用 oracle effect、未来任务或结果标签，也没有按 64 个 seed 调参。它把主 probe 的 utility 折扣限定在已满足候选合同的 item probe，避免把探索性 sentinel 当成已授权动作。

## 4. paired 修复结果

相对原 `hierarchical_sentinel_candidate`，`hierarchical_sentinel_guarded`：

| 对比 | utility 差异 | regret reduction | probe-cost 差异 |
|---|---:|---:|---:|
| guarded − unguarded | `+0.121` [`+0.087`, `+0.149`] | `+0.094` [`+0.071`, `+0.113`] | `−0.193` [`−0.203`, `−0.180`] |

guarded 行的汇总与 `hierarchical_candidate` 完全一致（均值 utility `0.3359`、regret `0.5956`、mean probes `0.5`）；这表示 gate 在该 badcase 上选择不付出 sentinel 探索成本，而不是制造新的 privileged path。

## 5. 其他机制对照

同一 64-seed 合同下：

- `minimal_framework − item_causal_risk_no_restore` utility `+3.285`，95% CI `[+3.272, +3.297]`；regret reduction `+0.657`，CI `[+0.654, +0.659]`。
- `task_adaptive_cap_candidate − minimal_framework` utility `+0.262`，95% CI `[+0.256, +0.295]`；regret reduction `+0.173`，CI `[+0.169, +0.197]`。
- 这些是内部机制世界的配对结果，不是公开 benchmark 的 SOTA 比较。

## 6. 资格边界

本报告可支持：

- 该机制基准能稳定触发 recovery、adaptive-budget 和 sentinel 差异；
- sentinel 的无条件版本存在可重复 badcase；
- full-cost sentinel gate 在同一合同下修复该 badcase，并降低探测成本。

本报告不能支持：

- 公开 LoCoMo/LongMemEval 泛化；
- 真实 agent 流量上的最优性；
- 任意 sequential policy 的 minimax 或 coverage 定理；
- “sentinel 永远应被拒绝”或“guarded 全面优于所有基线”。
