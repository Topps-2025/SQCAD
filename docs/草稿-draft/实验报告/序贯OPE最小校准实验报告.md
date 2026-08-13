---
type: experiment-report
status: preliminary
tags:
  - sequential-decision
  - off-policy-evaluation
  - agent-memory
  - causal-inference
---

# 序贯 OPE 最小校准实验报告

## 1. 实验目的

该实验将静态因果校准推进到有限 horizon 的记忆治理：过去的记忆暴露会改变下一步任务难度，任务难度又影响后续暴露 propensity 与奖励。因此，静态单步效应不能直接等同于长期治理价值。实验比较 trajectory IS 和 tabular stepwise DR-OPE 是否能够在日志策略下恢复三种目标策略的真实累计价值并正确排序。

脚本：[[sequential_ope_sanity.py]]；结果：[[sequential_ope_sanity.json]]。

## 2. 协议

- 20 个随机种子，每个种子 5,000 条日志轨迹；
- horizon 为 5，折扣因子为 0.95；
- 状态为低/高任务难度，过去暴露影响下一步状态，构成时间变化混杂；
- 日志策略在低/高难度下的暴露概率分别为 0.2/0.8；
- 目标策略为 `never`、`high_only` 和 `always`；
- 真实策略值由独立 Monte Carlo 回放获得；OPE 只使用日志轨迹。

## 3. 结果

| 指标 | trajectory IS | stepwise DR-OPE |
| --- | ---: | ---: |
| 策略最优排序正确率 | 1.00 | 1.00 |
| 三策略平均绝对价值误差 | 0.086 ± 0.050 | **0.081 ± 0.045** |
| `high_only` 价值偏差 | -0.002 ± 0.022 | **-0.000 ± 0.018** |
| `always` 价值偏差 | -0.024 ± 0.220 | **-0.014 ± 0.196** |

表中“±”为跨种子标准差；最优策略在所有种子中均为 `high_only`。DR-OPE 在该设置下略降低绝对误差和长 horizon 的方差，但差距仍然有限，不能写成普遍优于 IS 的结论。

## 4. 研究判断

该实验支持将“长期治理策略价值”与“单步记忆效应”区分开，并说明在存在时间变化混杂时，日志 propensity 和序贯 OPE 是可实现的工程接口。与此同时，当前状态空间和策略集合很小，且是离散可控模拟器；真实 Agent Memory 还需要加入多记忆干扰、簇级 treatment、检索器变化、作用域迁移和有限 overlap。

后续长 horizon 实验必须增加：MSM/stabilized IPW、不同 horizon 与 propensity overlap、权重截断敏感性、策略部署回放值及 OPE 排序失误案例。若 OPE 在这些压力条件下不能稳定排序目标治理策略，则不能声称序贯因果治理有效。
