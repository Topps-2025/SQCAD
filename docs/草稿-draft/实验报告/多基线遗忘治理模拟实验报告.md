---
type: experiment-report
status: preliminary
scope: mechanism-stress-test
---

# 多基线遗忘治理模拟实验：解构质量压力测试

## 1. 实验目的与边界

本实验用于检验“证据分组/机制抽象质量下降时，联合解构—抽象—因果治理是否出现可测量的负迁移”。它是具有已知机制分组的 synthetic mechanism stress test，不是公开 Agent Memory benchmark，也不能支持 SOTA 或真实任务泛化主张。

## 2. 固定协议

- 记忆池：120 条；其中 `rare_critical=12`、`common_useful=24`、`stale=24`、`noise=60`；
- 训练环境：2 个；测试环境：1 个；
- 保留预算：36 条；每个噪声水平 50 个随机种子；每个环境每 seed 12,000 个样本；
- 组噪声：0.0、0.1、0.2、0.4；
- risk-gated 置信门槛：0.75；item-level 负效应 veto：稳定下界≤−0.25；四档实验使用同一预先固定门槛；
- 评价：测试 utility、归一化 utility、rare-critical recall、stale retention、保留正记忆 precision；
- 比较方法：recency、frequency、fade-like、Memory Worth-like、item-level causal stable、decomposition–abstraction causal，以及加入表示置信度、跨层效应符号一致性和 item-level 负效应 veto 的 risk-gated 联合方法。

模拟器将暴露与难度/流行度混杂，并为低频关键记忆设置“降低损失但不必然扭转二元成败”的保护性效应；因此，成功共现不是其真实效应的充分统计量。组噪声用于模拟解构或机制归类错误，而不是对真实语义解析器的直接估计。

## 3. 主要结果

下表为 `decomp_abstract_causal` 在四个组噪声水平的均值；括号内为归一化 utility 的 95% CI 半宽度。

| 组噪声 | 归一化 utility | rare-critical recall | stale retention | retained positive precision |
| ---: | ---: | ---: | ---: | ---: |
| 0.0 | 1.000 (±0.000) | 1.000 | 0.000 | 1.000 |
| 0.1 | 0.867 (±0.010) | 0.945 | 0.063 | 0.849 |
| 0.2 | 0.720 (±0.020) | 0.872 | 0.146 | 0.696 |
| 0.4 | 0.482 (±0.028) | 0.690 | 0.254 | 0.474 |

在最高噪声水平 0.4 下，联合方法不再优于 `causal_item_stable`（后者归一化 utility=0.493），说明其收益依赖于解构/机制分组质量，而不是来自“抽象”这一标签本身。

在噪声 0.4 下的完整基线对照如下：

| 方法 | 归一化 utility | rare-critical recall | stale retention | retained positive precision |
| --- | ---: | ---: | ---: | ---: |
| recency | 0.042 | 0.063 | 0.731 | 0.377 |
| frequency | -0.088 | 0.000 | 1.000 | 0.333 |
| fade-like | -0.083 | 0.000 | 0.993 | 0.338 |
| Memory Worth-like | 0.235 | 0.000 | 0.000 | 0.381 |
| causal item stable | 0.493 | 0.138 | 0.000 | 0.713 |
| decomposition–abstraction causal | 0.482 | 0.690 | 0.254 | 0.474 |

以 `causal_item_stable` 为逐 seed 配对强基线，联合方法的差值（均值 ± 95% CI 半宽）如下：

| 组噪声 | Δ normalized utility | Δ rare-critical recall | Δ stale retention | Δ positive precision |
| ---: | ---: | ---: | ---: | ---: |
| 0.0 | +0.507 ± 0.017 | +0.862 ± 0.028 | +0.000 ± 0.000 | +0.287 ± 0.009 |
| 0.1 | +0.374 ± 0.020 | +0.807 ± 0.034 | +0.063 ± 0.013 | +0.136 ± 0.016 |
| 0.2 | +0.227 ± 0.028 | +0.733 ± 0.046 | +0.146 ± 0.017 | −0.017 ± 0.026 |
| 0.4 | −0.011 ± 0.033 | +0.552 ± 0.069 | +0.254 ± 0.025 | −0.239 ± 0.029 |

这组配对结果比单独比较均值更重要：在噪声 0.4 时 utility 差值的区间跨过 0，不能声称联合方法仍然优于 item-level causal；其主要剩余优势是 rare-critical recall，而 precision 与过时记忆控制已明显恶化。

原始联合方法的逐 seed 结果说明，高关键召回并不自动形成全指标帕累托优势。为回应这一 bad case，新增 `decomp_abstract_risk_gated`：只有表示置信度达到0.75、且抽象组效应未与可估计 item-level 效应发生符号冲突时，才使用组级分数；item-level 稳定效应的 LCB≤−0.25 时触发负效应 veto，否则回退到 `causal_item_stable`。门槛在四档联合重跑前固定，不按测试噪声单独调节。

| 组噪声 | risk-gated utility | rare-critical recall | stale retention | positive precision |
| ---: | ---: | ---: | ---: | ---: |
| 0.0 | 1.000 | 1.000 | 0.000 | 1.000 |
| 0.1 | 0.951 | 0.922 | 0.003 | 0.971 |
| 0.2 | 0.904 | 0.838 | 0.003 | 0.946 |
| 0.4 | 0.815 | 0.690 | 0.007 | 0.896 |

相对 `causal_item_stable`，risk-gated 方法在四档噪声上的 utility 配对增量依次为 +0.507±0.017、+0.458±0.018、+0.411±0.021、+0.322±0.022，逐 seed utility 胜率均为1.00。噪声0.4时，rare-critical recall 增量为+0.552±0.038，positive precision 增量为+0.183±0.013；stale retention 仅增加0.007±0.005，86%的 seeds 与 item-level baseline 持平。该风险门控显著缓解了原始联合方法在噪声0.4下的 stale retention 0.254 和 utility 0.482，但尚未在 stale-retention 上严格优于本来就为0的 item-level baseline。

### 风险门控消融（组噪声0.4，50 seeds）

| 变体 | normalized utility | rare-critical recall | stale retention | positive precision |
| --- | ---: | ---: | ---: | ---: |
| 仅置信度门控 | 0.788 | 0.682 | 0.028 | 0.867 |
| 仅跨层符号门控 | 0.862 | 0.828 | 0.044 | 0.904 |
| 仅 item-level 负效应 veto | 0.801 | 0.888 | 0.058 | 0.774 |
| 三者联合 risk-gated | **0.815** | 0.690 | **0.007** | **0.896** |

这组消融表明三个门控并非冗余：置信度门控主要控制表示错误，符号一致性门控改善抽象与局部效应的冲突，负效应 veto 更偏向保护低频关键项；联合版本在 stale 风险和 precision 之间取得最稳健的折中，但仍未在 stale retention 上严格击败零风险的 item-level control。

## 4. 解释与否证边界

结果支持三个有限判断：

1. 在模拟器给出的正确机制分组下，联合方法能够保留低频关键组并抑制过时组；
2. 机制归类噪声增加会同时降低效用和关键记忆召回，并增加 stale retention，因而“解构—抽象必然提升”被否定。
3. 将表示置信度、跨层效应一致性和负效应 veto 纳入治理资格，可以在该受控置信校准模型中显著缓解抽象误差传播；该增益依赖置信度具有校准信息，必须由真实 Gate A 与 calibration curve 验证。

结果不支持以下主张：

- 联合方法已经在 LongMemEval、GoodAI-LTM 或 LoCoMo 上超过强基线；
- 组噪声可直接等同于真实 LLM 解构器的准确率；
- 已知机制分组下的上界式表现可代表端到端 Agent 的泛化。

## 5. 对论文设计的直接影响

1. 将 `decomposition quality` 作为主实验变量，而不是只报告单一最好点；至少报告 factor precision/recall、provenance coverage 和 scope completeness。
2. 把 `causal_item_stable` 作为必须保留的强基线；当解构质量不足时，系统应退回因子级或原始证据级治理，而不是继续提升抽象层。
3. 将 risk-gated fallback 升级为正式方法模块，并增加“去掉置信门控”“去掉跨层符号检查”“去掉负效应 veto”的独立消融；必须报告 coverage–risk 曲线，防止通过大量回退获得表面安全。
4. 在公开 benchmark 上使用“原始证据主索引 + 因子/规则 sidecar + 证据回退”，并通过人工审计或扰动叠加构造对解构与作用域的可复核评价。
5. 主结果只在固定候选流、检索器、模型、token/存储预算和 evaluator 下比较；本报告所有数字均标为模拟机制压力测试。

## 6. 可复现文件

- 运行脚本：`governance_baseline_simulator.py`；
- 输出：`governance_group_noise_00.json`、`governance_group_noise_01.json`、`governance_group_noise_02.json`、`governance_group_noise_04.json`；
- 每个 JSON 保存协议、逐 seed 结果和汇总统计。

## 相关文档

[[../06-解构抽象能力的学术化界定与因果架构融合|解构—抽象能力的学术化界定]]、[[../05-解构抽象因果遗忘框架阶段性可行性判断|阶段性可行性判断]]、[[../03-因果推断驱动的Agent Memory遗忘框架论文方案|方法与实验蓝图]]
