# Gap 证明实验方案：命题 A / B / C

> 日期：2026-08-12
> 用途：为将 Research Gap 从研究假设升级为理论空白，设计三个命题的构造性证明实验。
> 核心原则：三个命题分别对应三类基线工作所走的路径——每类基线走了一条路径，每条路径对应一个命题说明为什么不够。
>
> 状态：实验方案设计。代码实现见 `src/sqcad/gap_proof_experiments.py`。

---

## 0. 命题与基线路径的对应关系

```text
基线路径                          命题                          证明目标
──────────────────────────────────────────────────────────────────────────
Memory Worth 类                   命题 A                        历史日志不可识别
(关联价值：success/failure         构造 M₁, M₂：               lifecycle value
 共现 → memory score)              P(O) 相同但 V^π(a) 不同
──────────────────────────────────────────────────────────────────────────
CMI 类                            命题 B                        局部效应不充分
(query-local intervention:        构造 Δ_t(i) 相同但           query-local effect
 force in/out → answer change)    V^π(archive)-V^π(keep) 相反   ≠ lifecycle value
──────────────────────────────────────────────────────────────────────────
通用 OPE/MSM 类                    命题 C                        笼统平均不可迁移
(序贯因果效应：source-scope        构造 E_s[τ(s)]≈0 但          source average
 平均 → 策略优化)                  τ(s*) 显著 ≠ 0               ≠ target scope value
──────────────────────────────────────────────────────────────────────────
```

三个命题合起来证明：**这三类基线工作各自正确估计了一个不同的 estimand，但没有一个能回答 SQCAD 定义的 persistent-access lifecycle value 问题。**

---

## 1. 命题 A：历史 observational logs 不足以识别生命周期价值

### 1.1 对应基线路径

Memory Worth 类方法：从历史检索-结果日志中构造 success/failure 共现信号作为 memory score。核心假设是"被检索后伴随成功的记忆是好的"。

### 1.2 命题陈述

仅观测 $O_{1:H} = (C_t, E_t, Y_t)$——candidate、exposure 和 outcome——通常无法识别 $V_s^\pi(a)$。

### 1.3 实验构造

**合成世界设计**：

两个结构模型 $M_1$（记忆真正有用）和 $M_2$（记忆被 confounded 共同暴露）：

| 要素 | 世界 M₁（有用世界） | 世界 M₂（混杂世界） |
| --- | --- | --- |
| 目标记忆 m* 的真实效应 | 对下游任务有正向因果作用 | 对下游任务无因果作用 |
| 共同暴露机制 | m* 独立被检索 | m* 只在另一条真正有用的记忆 m' 被检索时才被共同检索 |
| 任务难度 confounding | 无 | m* 被检索时恰逢简单任务 |
| 历史日志 $(C, E, Y)$ | 分布 $P_1$ | 分布 $P_2 = P_1$（构造使二者相等） |
| archive m* 后的未来效用 | 显著下降 | 不变或上升 |

**关键约束**：$P_{M_1}(C_{1:H}, E_{1:H}, Y_{1:H}) = P_{M_2}(C_{1:H}, E_{1:H}, Y_{1:H})$。

**数据生成过程**：

```
M₁（有用世界）：
  - m* 的 latent utility = +2.0
  - 当 task 需要 m* 时，m* 被检索（propensity = 0.7）
  - 检索 m* 后 outcome 改善 +2.0
  - m' 独立有用，在另一类 task 中被检索

M₂（混杂世界）：
  - m* 的 latent utility = 0.0
  - m* 只在 m' 被检索时才被共同检索（co-exposure rate = 0.7）
  - m' 真正有用（latent utility = +2.0）
  - 恰逢 m' 的 task 也是简单 task（difficulty confounding）
  - 因此 m* 在历史日志中也呈现"检索后伴随成功"

构造约束：
  - 校准 co-exposure rate 和 difficulty distribution
  - 使得两个世界产生完全相同的 (C_t, E_t, Y_t) 联合分布
```

### 1.4 基线方法在此世界上的行为

| 基线 | 在 M₁ 中对 m* 的评分 | 在 M₂ 中对 m* 的评分 | 问题 |
| --- | --- | --- | --- |
| Memory Worth (success/failure ratio) | 高 | 高（因 co-exposure confounding） | 无法区分 $M_1$ 和 $M_2$ |
| Recency / Frequency | 相同 | 相同 | 仅依赖时间/频率 |
| FadeMem-like decay | 相同 | 相同 | 仅依赖时间和频次衰减 |

### 1.5 验证指标

- **日志分布距离**：验证 $D_{KL}(P_1 || P_2) \approx 0$ 或统计检验不显著
- **基线评分一致性**：验证 Memory Worth 对 m* 的评分在 M₁ 和 M₂ 中无显著差异
- **lifecycle value 差异**：验证 $V_{s,M_1}^\pi(\text{archive}) - V_{s,M_1}^\pi(\text{keep}) \ll 0$ 但 $V_{s,M_2}^\pi(\text{archive}) - V_{s,M_2}^\pi(\text{keep}) \ge 0$
- **结论**：历史日志相同 + 基线评分相同 + lifecycle value 不同 → 不可识别性成立

---

## 2. 命题 B：query-local causal effect 仍不足以识别 lifecycle value

### 2.1 对应基线路径

CMI 类方法：在固定 query 上运行 no-memory / with-memory / perturbed-memory，估计当前答案的局部 intervention effect $\Delta_t(i)$。

### 2.2 命题陈述

即使 $\Delta_t(i)$ 被无偏估计，也不能推出 $V_s^\pi(a_1) - V_s^\pi(a_0)$。

### 2.3 实验构造

**合成世界设计**：

构造两个记忆 $m_1$ 和 $m_2$，它们的 query-local intervention effect 相同，但 persistent access 改变后的未来轨迹价值相反。

| 要素 | 记忆 $m_1$（短期有用，长期有害） | 记忆 $m_2$（短期无用，长期有用） |
| --- | --- | --- |
| query-local effect $\Delta_t(i)$ | +1.5（当前答案改善） | +1.5（当前答案改善） |
| 对未来 candidate stream 的影响 | 增加 noise candidate | 引入 rare but critical 后续候选 |
| 对 co-memory 的影响 | 挤占 workspace，排挤关键记忆 | 不挤占（token-light） |
| 对 policy update 的影响 | 使 policy 偏向检索 noise | 使 policy 保留 rare task 的检索路径 |
| persistent rollout $V^\pi(\text{keep}) - V^\pi(\text{archive})$ | 负值（应 archive） | 正值（应 keep） |

**数据生成过程**：

```
时间线：
  t=1..T₀：source period，两条记忆都被检索，都产生 +1.5 的局部效应
  t=T₀+1..T：future period

m₁（短期有用，长期有害）：
  - 每次被检索，当前 answer quality +1.5
  - 但 keep 状态使后续 candidate stream 中被注入 3× noise candidates
  - noise candidates 挤占 workspace budget，排挤 rare_critical 记忆
  - 累计 lifecycle utility 下降

m₂（短期无用，长期有用）：
  - 每次被检索，当前 answer quality +1.5（因恰逢 easy task）
  - keep 状态维持了一条 rare task 的检索路径
  - 在 future period 中 rare task 出现时，该路径被激活
  - 累计 lifecycle utility 上升

关键约束：
  - source period 中 Δ_t(m₁) = Δ_t(m₂) = +1.5
  - 但 V^π(keep) - V^π(archive) 符号相反
```

### 2.4 基线方法在此世界上的行为

| 基线 | 对 m₁ 的建议 | 对 m₂ 的建议 | 问题 |
| --- | --- | --- | --- |
| CMI ($\Delta_t > 0 \to$ keep) | keep | keep | 对 $m_1$ 错误（应 archive） |
| CMI ($\Delta_t >$ threshold $\to$ keep) | keep | keep | 同上 |
| Memory Worth | keep（高共现） | keep（高共现） | 两条都错或对一错一 |

### 2.5 验证指标

- **局部效应等价性**：验证 source period 中 $\Delta(m_1) = \Delta(m_2)$（统计不显著差异）
- **lifecycle value 符号相反**：验证 $V^\pi(\text{keep}) - V^\pi(\text{archive})$ 对 m₁ < 0，对 m₂ > 0
- **CMI 决策遗憾**：若 CMI 对两者都建议 keep → 对 $m_1$ 产生 regret > 0
- **结论**：query-local effect 相同 + lifecycle value 相反 → 局部效应不足以支撑生命周期决策

---

## 3. 命题 C：笼统作用域下的平均因果效应不等于目标作用域价值

### 3.1 对应基线路径

通用 OPE/MSM 类方法：在 source scope(s) 上估计平均处理效应，用于指导未来策略。核心假设是"source 中估计的因果效应可以推广到 target"。

### 3.2 命题陈述

$\mathbb{E}_{s \sim P_{\text{source}}}[\tau(s)]$ 一般不能替代 $\tau(s^*)$。

### 3.3 实验构造

**合成世界设计**：

构造三个作用域：$s_1$（常规任务）、$s_2$（高风险任务）、$s^*$（目标部署环境）。

| 要素 | $s_1$（常规任务） | $s_2$（高风险任务） | $s^*$（目标环境） |
| --- | --- | --- | --- |
| 记忆 m 的真实 $\tau(s)$ | +0.8 | -2.0（保留会触发有害行为） | +1.5 |
| scope 在 source 中的权重 | 0.6 | 0.4 | — |
| source 加权平均 $\tau$ | $0.6\times 0.8 + 0.4\times(-2.0) = -0.32$ | — | +1.5 |

**数据生成过程**：

```
scope s₁（常规任务，权重 0.6）：
  - task difficulty 低，memory m 提供 marginal improvement
  - τ(s₁) = +0.8

scope s₂（高风险任务，权重 0.4）：
  - task 涉及安全约束，memory m 是过时的安全规则
  - 保留 m 导致遵循过时规则，产生 harmful outcome
  - τ(s₂) = -2.0

source 加权平均：
  - E_s[τ(s)] = 0.6 × 0.8 + 0.4 × (-2.0) = -0.32
  - 若系统只看平均值 → 建议 archive m（因为平均效应为负）

target scope s*（新部署环境）：
  - task distribution 变化：高风险任务比例降低
  - m 在 s* 中是 valuable resource
  - τ(s*) = +1.5
  - 正确决策：keep m
```

### 3.4 基线方法在此世界上的行为

| 基线 | 对 m 的建议 | 问题 |
| --- | --- | --- |
| OPE/MSM (source average) | archive（平均 $\tau < 0$） | target scope 中应 keep，产生 regret |
| Memory Worth (overall) | 取决于整体共现 | 不区分 scope |
| CMI (source average) | archive | 同 OPE |

### 3.5 验证指标

- **source 平均效应**：验证 $\mathbb{E}_s[\tau(s)] < 0$（建议 archive）
- **target scope 效应**：验证 $\tau(s^*) > 0$（实际应 keep）
- **scope 异质性**：验证 $\tau(s_1) \neq \tau(s_2) \neq \tau(s^*)$
- **决策 regret**：使用 source 平均值做决策在 target scope 中产生 regret > 0
- **结论**：source 平均效应为负 + target 效应为正 → 笼统平均不能替代作用域条件决策

---

## 4. 决策遗憾集成实验：证明 estimand 对 Agent Memory 管理有作用

### 4.1 实验目标

在前三个命题各自的反例世界基础上，构造一个**统一的决策遗憾评估**：

- 使用关联价值（Memory Worth 路径）做决策 → 在命题 A 的世界中产生 regret
- 使用局部效应（CMI 路径）做决策 → 在命题 B 的世界中产生 regret
- 使用 scope 平均效应（OPE/MSM 路径）做决策 → 在命题 C 的世界中产生 regret
- 使用 lifecycle value 做决策 → 在三个世界中 regret 均为零（或最小）

### 4.2 决策协议

```
对每条记忆 m：
  1. 关联基线：score_assoc(m) > threshold → keep, else archive
  2. 局部因果基线：Δ(m) > 0 → keep, else archive
  3. scope 平均基线：E_s[τ_s(m)] > 0 → keep, else archive
  4. lifecycle oracle：V^π(keep) - V^π(archive) > 0 → keep, else archive

比较 1/2/3 与 4 的决策差异，计算 regret：
  Regret = V^π(a*_oracle) - V^π(a*_baseline)
```

### 4.3 期望输出

| 基线路径 | 命题 A 世界 regret | 命题 B 世界 regret | 命题 C 世界 regret | 综合 |
| --- | --- | --- | --- | --- |
| 关联价值 (Memory Worth) | **> 0** | ≥ 0 | ≥ 0 | 命题 A 成立 |
| 局部效应 (CMI) | ≥ 0 | **> 0** | ≥ 0 | 命题 B 成立 |
| scope 平均 (OPE/MSM) | ≥ 0 | ≥ 0 | **> 0** | 命题 C 成立 |
| lifecycle oracle | 0 | 0 | 0 | oracle baseline |

---

## 5. 实验输出与论文主张的对应关系

| 实验结果 | 论文可以主张 |
| --- | --- |
| 命题 A 反例成立 | "历史 observational logs 不足以识别 persistent-access lifecycle value" |
| 命题 B 反例成立 | "query-local intervention effect 不能替代 lifecycle policy value" |
| 命题 C 反例成立 | "笼统作用域平均效应不能替代 target-scope 条件决策" |
| 三项 + 决策遗憾全部成立 | **Research Gap 从假设升级为理论空白** |
| 任意一项不成立 | 收缩对应假设，重新检查文献覆盖边界 |

---

## 6. 实现计划

### 6.1 代码结构

```
src/sqcad/gap_proof_experiments.py   — 三个命题的合成世界 + 基线评估 + 决策遗憾
tests/test_gap_proof_experiments.py   — 验证实验正确性
```

### 6.2 基线复现

将以下基线代码 clone 到 `D:\Engineering\SQCAD\database\upstream\baselines\`：
- Oblivion（已注册）
- SimpleMem（已注册）
- Memory Worth（待添加）
- CMI（待添加）

### 6.3 运行顺序

1. 复现基线代码（命题 A/B/C 对应的三类基线）
2. 实现命题 A 合成世界 + 验证
3. 实现命题 B 合成世界 + 验证
4. 实现命题 C 合成世界 + 验证
5. 集成决策遗憾实验
6. 生成实验报告
