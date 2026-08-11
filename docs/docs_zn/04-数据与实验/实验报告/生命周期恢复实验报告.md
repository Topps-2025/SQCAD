# 长周期生命周期恢复实验报告

## 1. 实验定位

本实验是一个 synthetic mechanism stress test，用于检验最新版框架中 `archive → regime shift → recurrence → restore → reuse` 的生命周期链路。它不是 LongMemEval、LoCoMo、GoodAI-LTM 等公开 Agent Memory benchmark，也不支持 SOTA 或真实部署性能结论。

实验只检验一个明确问题：当记忆的有效性随 regime 改变、旧 regime 可能再次出现，并且 false forgetting 有代价时，可恢复治理是否比不可逆治理更能保留可复用证据。`one_way_obsolescence` 和 `weak_gap_stationary` 是预先保留的反例，不应被省略。

## 2. 固定协议

- 6 个命名场景，每个 50 seeds、每个 horizon 90；
- 120 个随机生命周期世界，随机化 recurrence、drift、confounding、coherence、decomposition accuracy、observation noise、干预成本、group count（4–10）和 items per group（2–5）；
- 4 个策略共享同一 world stream、任务、语义信号、潜在结果、评估器和成本合同：
  - `association_irreversible`；
  - `item_causal_irreversible`；
  - `hierarchical_irreversible`；
  - `recoverable_framework`；
- 无人工路径标签、privileged path-level cues、fine-tuning、learned parameters 和逐场景调参；
- group probe 是付费干预，不是免费真值标签；group evidence 只能作为可衰减先验；item-level negative lower bound 触发风险 veto；
- 所有策略均记录 candidate、selection、outcome、archive/restore 和 decision-log completeness。

正式结果文件：`results/lifecycle_restore_benchmark_v1.json`。

## 3. 命名场景结果

表中为 50 seeds 的 mean ± 95% CI。`FF` 为 false-forgetting rate，`R` 为平均 restore events，`L` 为 recovery latency；无 recurrence 时，`L=90` 表示在 horizon 内未恢复，而不是成功恢复。

| 场景 | 策略 | Utility | Regret | FF | R | L | Probe cost / episode |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| recurring regime shift | association irreversible | −0.7004 ± 0.0660 | 0.5833 ± 0.0303 | 0.3251 | 0.00 | 90.00 | 0.0000 |
|  | item causal irreversible | −0.0056 ± 0.0380 | 0.3701 ± 0.0243 | 0.0160 | 0.00 | 77.36 | 1.9850 |
|  | hierarchical irreversible | −0.1519 ± 0.0369 | 0.4096 ± 0.0236 | 0.0456 | 0.00 | 85.68 | 2.4028 |
|  | recoverable framework | −0.0165 ± 0.0305 | 0.3277 ± 0.0241 | **0.0009** | **3.88** | **62.26** | 2.8501 |
| one-way obsolescence | association irreversible | −0.6974 ± 0.0642 | 0.5630 ± 0.0223 | 0.3251 | 0.00 | 90.00 | 0.0000 |
|  | item causal irreversible | **0.0172 ± 0.0359** | 0.3416 ± 0.0263 | 0.0102 | 0.00 | 90.00 | 1.9956 |
|  | hierarchical irreversible | −0.0999 ± 0.0318 | 0.3758 ± 0.0255 | 0.0260 | 0.00 | 90.00 | 2.4776 |
|  | recoverable framework | −0.0458 ± 0.0224 | **0.3367 ± 0.0204** | **0.0024** | 1.88 | 90.00 | 2.8453 |
| weak gap stationary | association irreversible | −0.2907 ± 0.0311 | 0.6242 ± 0.0249 | 0.3789 | 0.00 | 90.00 | 0.0000 |
|  | item causal irreversible | **−0.0307 ± 0.0306** | **0.4346 ± 0.0280** | 0.0416 | 0.00 | 90.00 | 1.9947 |
|  | hierarchical irreversible | −0.1532 ± 0.0258 | 0.4927 ± 0.0225 | 0.0944 | 0.00 | 90.00 | 2.2162 |
|  | recoverable framework | −0.1619 ± 0.0278 | 0.4714 ± 0.0234 | 0.0611 | 0.00 | 90.00 | 2.7819 |
| noisy recurrence | association irreversible | −0.6424 ± 0.0759 | 0.5312 ± 0.0285 | 0.2993 | 0.00 | 90.00 | 0.0000 |
|  | item causal irreversible | −0.2927 ± 0.0427 | 0.4234 ± 0.0248 | 0.0989 | 0.00 | 79.96 | 1.9899 |
|  | hierarchical irreversible | −0.3207 ± 0.0423 | 0.4490 ± 0.0246 | 0.0967 | 0.00 | 77.98 | 2.0633 |
|  | recoverable framework | **−0.2030 ± 0.0351** | **0.3982 ± 0.0270** | **0.0318** | **4.82** | **56.76** | 2.8224 |
| high restore cost | association irreversible | −0.6778 ± 0.0555 | 0.5908 ± 0.0340 | 0.3176 | 0.00 | 90.00 | 0.0000 |
|  | item causal irreversible | **−0.0786 ± 0.0485** | **0.3852 ± 0.0283** | 0.0396 | 0.00 | 76.34 | 2.1797 |
|  | hierarchical irreversible | −0.2554 ± 0.0377 | 0.4800 ± 0.0300 | 0.0551 | 0.00 | 78.56 | 2.6580 |
|  | recoverable framework | −0.1654 ± 0.0410 | 0.4657 ± 0.0391 | **0.0196** | 3.72 | **65.82** | 2.6823 |
| stationary associational control | association irreversible | −0.2000 ± 0.0195 | 0.6451 ± 0.0238 | 0.3682 | 0.00 | 90.00 | 0.0000 |
|  | item causal irreversible | **0.1065 ± 0.0314** | **0.3539 ± 0.0294** | 0.0113 | 0.00 | 90.00 | 1.9878 |
|  | hierarchical irreversible | 0.0084 ± 0.0253 | 0.3866 ± 0.0278 | 0.0244 | 0.00 | 90.00 | 2.5628 |
|  | recoverable framework | −0.0070 ± 0.0278 | 0.3845 ± 0.0277 | 0.0098 | 0.00 | 90.00 | 2.8270 |

## 4. 随机生命周期世界

随机世界共 120 个，其中 74 个 recurrence worlds、46 个 non-recurrence worlds。

| 分层 | 策略 | Utility | Regret | FF | Restore | Recovery latency | Probe cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| recurrence (74) | association irreversible | −0.4592 | 0.5368 | 0.3014 | 0.00 | 90.00 | 0.0000 |
|  | item causal irreversible | **−0.1811** | **0.3994** | 0.0626 | 0.00 | 82.12 | 2.2393 |
|  | hierarchical irreversible | −0.2920 | 0.4595 | 0.0764 | 0.00 | 80.77 | 2.5236 |
|  | recoverable framework | −0.2327 | 0.4427 | **0.0329** | 3.31 | **71.74** | 2.8076 |
| non-recurrence (46) | association irreversible | −0.3680 | 0.5129 | 0.2459 | 0.00 | 90.00 | 0.0000 |
|  | item causal irreversible | **−0.1655** | **0.3815** | 0.0444 | 0.00 | 90.00 | 2.3607 |
|  | hierarchical irreversible | −0.2539 | 0.4346 | 0.0512 | 0.00 | 90.00 | 2.6370 |
|  | recoverable framework | −0.2494 | 0.4406 | **0.0355** | 1.59 | 90.00 | 2.7742 |

相对于 `item_causal_irreversible`，recoverable policy 在随机 recurrence worlds 的 paired utility delta 为 −0.0516 ± 0.0429，regret reduction 为 −0.0432 ± 0.0217；相对于 `hierarchical_irreversible`，utility delta 为 +0.0593 ± 0.0355，regret reduction 为 +0.0168 ± 0.0137。也就是说，恢复治理降低了 false forgetting 和恢复延迟，但它的额外探测/恢复成本使净 utility 不一定超过 item-level causal control。

## 5. 结果解释与对框架的修改

1. **恢复闭环在 recurrence 场景确实被触发。** `recurring_regime_shift` 中 recoverable policy 平均 restore 3.88 次，recovery latency 62.26；`noisy_recurrence` 中 restore 4.82 次、latency 56.76。两者的 false forgetting 分别为 0.0009 和 0.0318，明显低于不可逆策略。
2. **风险门控保留了核心思想。** noisy recurrence 的自动分组并不可靠，但 group evidence 只作为衰减先验；item-level negative lower bound veto 使框架的 FF 降至 0.0318，而 hierarchical irreversible 为 0.0967。这支持“结构用于探测和预算分配，不能直接替代证据”的设计约束。
3. **不能声称 recoverable framework 在所有场景都提升净 utility。** one-way obsolescence、weak-gap stationary、stationary associational control 和 high-restore-cost 都构成反例或成本边界。特别是 one-way obsolescence 中 item-level irreversible utility 最高，说明旧 regime 永不返回时，保留可恢复证据的机会成本可能不值得。
4. **工程方案因此采用条件性主张。** framework 的主要增益指标应是 false forgetting、regret、recovery latency、evidence survival 与 utility–cost frontier 的联合表现，而不是单一平均 utility。若恢复价值低或干预成本高，应选择 item-level irreversible 或 conservative keep。
5. **后续论文实验必须分层报告。** recurrence / non-recurrence、identifiable gap / weak gap、低成本 / 高成本应预先定义；不得把 recoverable policy 在某一层的胜出包装成全分布优势。

## 6. 结论边界

该实验支持一个受限但可检验的结论：当轨迹条件化关联过拟合导致生命周期误判、组件结构具有一定可恢复性、regime 可能复现且 false forgetting 成本较高时，`recoverable_framework` 具有结构性治理优势，尤其体现在证据存续、错误遗忘率和恢复延迟上。它不支持“天然 SOTA”“所有轨迹和数据分布都优于 baseline”或“模拟结果等同于真实 Agent Memory 性能”。

真实语义 Gate A、统一 reader 的公开 benchmark、长 horizon 真实 Agent Memory 部署和跨企业私有轨迹零样本迁移仍未完成。
