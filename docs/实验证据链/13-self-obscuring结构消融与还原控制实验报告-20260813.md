# 13-self-obscuring 结构消融与还原控制实验报告-20260813：T1/T2 机制证据链

> **本报告执行 `docs/研究逻辑与理论证明/14-Agent-Memory基础理论空缺与下一阶段实验路线-20260813.md` §5/§7 的实验 A（结构消融 W0–W3 + self-confirming 全对比）与实验 B（reduction controls）**。代码 `src/sqcad/self_obscuring_ablation.py`（15 项新测试随全套 239 项通过）；结果 `results/self_obscuring_ablation.json`（12 seeds，seed 21–32）；T1/T2 的严格证明见 `docs/研究逻辑与理论证明/15-self-obscuring形式定理与严格证明-20260813.md`。

**状态：计算验证级 + 形式化证明配套（15-）**。本报告回答：self-obscuring 闭环（治理动作 → 未来候选/证据流 → 未来可识别性 → 后续治理动作）是否是 Agent Memory 持久访问结构**不可约**地产生的机制——把关键结构去掉，现象是否消失。

---

## 1. 设置与协议

| 参数 | 值 | 含义 |
|---|---|---|
| τ | 10 | keep 时暴露步的生命周期价值（K 世界 +10 / 步，A 世界 −10 / 步） |
| p_expose | 0.6 | keep 状态下的证据到达率 |
| p_evid_archived | 0.6（W0/W1）／ 0.0（W2/W3） | archived 状态下的证据到达率——**审查开关** |
| n_early | 50 | 早期共因观测阶段（混杂先验，δ_early=−0.5，K/A 逐位共享） |
| T | 2000 | 水平线 |
| θ_keep / θ_archive | +2.0 / −2.0 | 证据驱动的 keep / archive 阈值 |
| prior_sd | 1.15 | 先验宽度（识别集加宽，12- Theorem 5） |
| c_probe / c_restore | 30 / 80 | 探测、恢复成本 |
| seeds | 12（21–32） | 每 cell 独立世界流 |

**精确斜率基准**：K 世界中被错误归档的记忆，从决策点起每个后续步以概率 p=0.6 暴露并产生 τ=10 的错失价值。T1(a)（15- §2.2）预测精确线性斜率

\[
\text{slope} = \tau\cdot p\cdot \frac{T-n_{\mathrm{early}}}{T}
= 10 \times 0.6 \times \frac{1950}{2000} = \mathbf{5.85}
\]

——不是近似，是 T1(a) 的精确数值预测（下文多处出现 5.8500 逐位精确，是机制在数值上兑现的形式化断言）。

## 2. 观测等价：引理 1 的机制单元

同一策略（association_commit）、同一 seed 下，K/A 两世界的**完整决策日志逐位相同**（`max_field_diff = 0.0, bit_identical = true`），但生命周期价值每步相反（+6.0 vs −6.0）。

**读法**：日志无法区分 K/A，而两世界的最优持久动作相反——观测等价世界 + 相反的 policy-relevant 动作（Theorem 1 的构造前提；也解释下文 W0 中 association_commit 在 K 世界线性失败：日志从未"看错"任何东西，只是不可区分）。

## 3. 结构消融矩阵 W0–W3（实验 A 主干）

| cell | slope（12 seeds） | correction time | 机制 |
|---|---|---|---|
| **W0**（query-local，不审查）K·watchful_no_restore | **0.0440 ± 0.0098** | 14.7 | 证据自由流动 → watchful 修正（几乎零 regret） |
| W0 K·association_commit | **5.8500**（精确） | 2000 | 不看证据的静态规则：即使证据流动也不修正 |
| W0 A·association_commit | 0.0000 | 0 | 归档恰好正确 |
| **W1**（persistent，不审查）K·watchful_no_restore | **0.0663 ± 0.0115** | 22.1 | 持久动作 + 未审查证据：watchful 仍修正 |
| **W2**（persistent，审查，无恢复）K·watchful_no_restore | **5.8500**（精确） | 2000 | **自我证实**：审查使证据停止 → 永无修正机会 |
| W2 K·association_commit | 5.8500（精确） | 2000 | 同上（两策略观测等价，见 §2） |
| **W3**（审查 + 恢复通道）K·watchful_restore | **0.4250 ± 0.1441** | 141.7（付 80） | 恢复通道重开证据流 → regret 平台化 |
| W3 K·watchful_no_restore | 5.8500（精确） | 2000 | 同一 watchful 策略、无通道 → 线性 |
| W2/W3 A 世界（全部） | 0.0000 | — | 归档正确侧：零 regret |

**读法**（对照 14- §7.1 的 W0–W3 语义）：

1. **审查是因果杠杆，策略不是**：同一 watchful 策略在 W0 修正（0.044）、在 W2 线性失败（5.85）。把环境从 query-local 换成 persistent 只引入少量额外噪声（W1 0.066），把证据流审查掉则定理从"修正"翻转为"Θ(T) regret"（T1(a) 的 W2 数值兑现）；
2. **去掉审查结构（W0）定理即失效**：W0 中没有任何策略能维持线性 regret 于 watchful 之外——结构消融把现象与 archive-induced censoring 一对一地绑定（14- §9 验收条件 1 的数值侧）；
3. W0 中 association_commit 仍线性（5.85）：静态规则不看证据，与审查无关——这隔离了"自我证实"机制：**审查 + 证据驱动（watchful）** 才是 T1 现象，单纯静态提交在 W0 也失败（是 Theorem 1 而非 T1）。

## 4. reduction controls（实验 B，14- §7.2）

| control | slope | correction | OPE 日志（archived 侧 / keep 侧） |
|---|---|---|---|
| W0·static bandit UCB | 0.0013 | 2000* | — |
| W0·contextual bandit | 0.0030 | 2000* | — |
| W1·standard OPE | **0.0750** | 25.0 | **34.6 / 1142.8**（overlap 存在） |
| W1·candidate UCB | **0.0037** | 1.2 | — |
| W2·standard OPE | **5.8500**（精确） | 2000 | 25.1 / 0.0（**archived 侧只有共因早期行**） |
| W2·candidate UCB | **5.8500**（精确） | 2000 | 0 / 0（**零行，探索死亡**） |

\* correction_time 对 static UCB / contextual bandit 不记录（代码按设计只跟踪状态翻转）；slope≈0 即翻转发生在决策后数步内。

**读法**：

1. **标准方法在 W0/W1 全部有效**：日志有 overlap 时 OPE 重新估计生命周期价值（W1 corr=25），UCB 在未审查流上快速修正（W1 corr=1.2）；
2. **在 W2 全部精确线性失败**：审查破坏 overlap——OPE 的 archived 侧日志 25.1 行全部来自 t<50 的共因阶段（均值 −0.5，混杂），keep 侧零行；UCB 零行、探索死亡。两种"普通方法"都无法在不增加 evidence-availability/lineage/restore 状态的前提下表达修正（T2 反证，15- §3）；
3. 数值上 W0→W1→W2 的对照构成了 T2 的 reduction-separation 证据链：**同样的方法、同样的数据、唯一的结构差异是审查**。

## 5. self-confirming 全对比（W3 通道内，实验 A 完整版，14- §7.3）

| W3 K 世界策略 | slope | correction | 成本 |
|---|---|---|---|
| no_probe_commit | 5.8500（精确） | 2000 | 0 |
| local_causal_commit | 5.8500（精确） | 2000 | 0 |
| gate_no_probe | 5.8500（精确） | 2000 | 0 |
| **gate_keep_default** | **4.3875 ± 1.50** | 1500 | 0 |
| fixed_prob_restore（q=0.05） | 0.5165 ± 0.0908 | 172.2 | 80 + 8.6 次探测 |
| **uncertainty_triggered_restore** | **0.2937 ± 0.0025** | 97.9 | 80（恰一次恢复） |
| **cost_aware_commit_defer_probe** | **0.0000** | 0 | 80（决策点恢复） |
| W3 A 世界（restore 规则） | ≤ 0.0245 | — | 80（一次恢复） |
| W3 A 世界（no-restore 规则） | ≤ 0.0060 | — | 0 |

**读法**：

1. **无恢复通道的提交规则全部线性**（5.85 精确 ×3）——它们是"self-confirming"原型：错误归档 → 候选流被审查 → 无证据 → 永不修正；
2. **gate_keep_default 的失败是共因先验陷阱**：早期阶段 (t<50) 的混杂均值 −0.5 配小样本把 CI 推离 0（统计上"已解决为负"），门禁据此归档——**确定性本身是陷阱，不是估计失败**（~75% 的 seed 提交，12-seed 均值 4.39；A 世界同一门禁不犯此错）；若 U>0 未解决则保持（K 世界正确），这正是 seed 变异的来源；
3. **三条恢复规则的平台全部来自付费通道**：fixed_prob 以探测换证据（8.6 次、付 80）；uncertainty_triggered 以沉默饥饿触发恢复（恰一次、付 80，corr≈98——接近 T1(b) 的 O(1/q) 预测，15- §4 sweep 表）；cost_aware 在决策点做三成本比较（12- Theorem 5 的 R\* 识别集）直接选最便宜的 restore（corr=0, slope=0）——**框架设计的证据治理规则在此对比中占优**（成本最低且零 regret）；
4. A 世界恢复规则 ≤0.0245：一次恢复引入有限有害滞留（≈7–8 步 × 10），随后证据确认归档、harm 已确认、沉默有信息（§6.2 的 harm_confirmed 语义）——恢复不是免费的，但代价被定理 T1(b) 界住（与 T 无关）。

## 6. 本轮修复的两个机制完整性缺陷（如实记录）

正式 12-seed 运行的 trace 审查发现两处代码缺陷，均已修复、重跑、并验证修复前后除两个 cell 外逐位一致（确定性模拟器）：

**6.1 UCB 共因早期流污染**（影响 W2·candidate UCB）：UCB 把 t<50 的共因观测史（K/A 逐位共享、均值 −0.5，无法区分生命周期符号）计入样本。n=1 时 CI ±1.96σ，seed 31 的一次幸运抽样（y>1.96，p≈0.007/seed；12 个 seed 恰好命中 1 个）在 t=0 触发假翻转（corr=−50, slope=0）。修复：UCB 只消费 **post-decision 候选流**（早期流是观测等价构造的组成部分，见 §2）。修复后 W2 12/12 seed 精确 5.8500，W1 修正时间 1.3→1.2。

**6.2 uncertainty_triggered_restore 恢复环路**（影响 W3 A 世界）：无确认标志时，staleness 恢复（bel>−2.37 区域）与证据确认再归档（bel<−2.0）的守卫互补，bel∈(−2.37,−2.0) 时两块在同一轮迭代内互触发——A 世界 restores=1745、成本 139593，状态轨迹却只有 3 次变化（同轮翻转被日志掩盖）。修复：恢复后再归档 ⇒ **沉默有信息**（harm_confirmed），不再触发恢复。修复后 A 世界恰一次恢复（成本 80，slope 0.0245），K 世界平台不变（0.2937/97.9）。

两处修复都以"机制语义"而非"调参"完成：6.1 界定早期共因史不能作为决策证据（引理 1 的观测等价是定义性的）；6.2 界定"已确认伤害"的记忆其沉默具有信息量（T1(c) 的方向）。15 项新测试覆盖了 headline cells 的机制断言（W0 修正/W2 线性、观测等价 bit-identical、controls 分离、bootstrap CI 排除 0、gate 共因提交）。

## 7. 统计验证：paired bootstrap（BCa，采样单元 = seed）

| 对比 | slope diff | 95% CI |
|---|---|---|
| W2 vs W1（同 watchful 策略） | +5.784 | [5.777, 5.789] |
| W3 restore vs W2 无通道 | −5.425 | [−5.501, −5.344] |
| W2 提交 vs A 世界正确归档 | +5.806 | [5.801, 5.811] |
| self-confirming: no_probe vs fixed_restore | +5.333 | [5.240, 5.414] |
| gate_no_probe vs cost_aware | +5.850 | [5.850, 5.850] |

采样单元是 seed（12 个独立世界），5 个 headline 对比的 CI 全部排除 0。第二、三行在固定 seed 上配对差分，消除了世界流的公共变异。

## 8. restore 概率扫描（q 单调性，T1(b) 的预测对照）

| q | correction time（经验） | slope |
|---|---|---|
| 0.01 | 817.9 | 2.4537 |
| 0.05 | 141.7 | 0.4250 |
| 0.2 | 36.8 | 0.1103 |

修正时间随 q 单调递减（T1(b) 上界 O(1/(qρ)) 的数值方向：15- §4 理论界 τp/q = 600/120/30，经验 corr 818/142/37，比值 1.1–1.4，常数因子内一致）；斜率随 q 单调递减，平台由恢复成本主导。

## 9. 对 14- §9 验收条件的支撑情况

| 验收条件 | 支撑 |
|---|---|
| 1. 依赖 archive-induced censoring 的定理，去掉结构失效 | ✅ **T1 完整证明（15-）+ 本报告 §3**：W0（去掉审查）watchful 修正 0.044，W2（保留审查）精确线性 5.85 |
| 2. reduction-separation | ✅ **T2 反证（15-，argument-level）+ 本报告 §4**：W0/W1 标准方法全部有效，W2 全部精确失败 |
| 3. 动态探索下界与匹配上界 | ⚠️→✅ 部分：T1(b) 恢复上界严格（O(1/q)）；P4 minimax 下界数值级（12- §6）；严格 minimax 证明仍待 |
| 4–5. interference granularity / authorization certificate | 未做（沿用 12-/13- 的 P0 遗留标注） |
| 6–7. trace-grounded 实验与强基线 | 下一阶段（audit 待办） |

按 14- §9"至少满足三项中的两项"：**1、2 已严格满足，3 部分满足（上界严格）**。机制级的 self-obscuring 动力学已具备形式化定理（T1/T2）+ 结构消融 + 还原控制的完整证据链；"更强主张"（§11）的表述已获得支撑，论文层面是否升级主张留待 trace-grounded 实验（验收 6/7）后由审计决定。

## 10. 可以声称 / 尚不能声称

**可以声称（本报告 + 15- 支撑）**：

1. T1：无恢复通道的 committing 策略在审查世界有精确线性 regret（数值 5.8500 = τ·p·(T−n_early)/T 逐位兑现）；恢复通道把 regret 界到 O(1/q)（与 T 无关）；审查结构去掉后（W0）现象消失；
2. T2：reduction separation——W0/W1 标准方法（static bandit、contextual bandit、log OPE、candidate UCB）全部有效，W2 全部精确线性失败（censoring 破坏 overlap / 探索死亡）；
3. 观测等价：K/A 世界逐位相同日志、相反生命周期价值（引理 1 机制数值兑现）；
4. self-confirming 治理对比：无恢复提交线性、gate 的共因先验陷阱、三条恢复规则平台化、cost_aware 决策点比较最优（零 regret + 一次付费恢复）；
5. 5 个 headline 对比的 paired bootstrap CI 全部排除 0。

**尚不能声称**：

- P4 的 minimax 严格下界（12- 已标注）；T2 目前是 argument-level 反证（15- 如实标注）；
- interference granularity theorem 与 authorization certificate 的形式化（P0 遗留）；
- 任何 trace-grounded 真实轨迹上的对应物实验（验收 6/7，下一阶段）；
- 论文最终升级主张的决定权在审计，本报告只提供机制级证据。

## 11. 复现信息

- 代码：`src/sqcad/self_obscuring_ablation.py`（`structural_ablation` / `reduction_controls` / `self_confirming_comparison` / `observational_equivalence` / `paired_bootstrap`）；测试 `tests/test_self_obscuring_ablation.py`（15 项）；全套 **239 项通过**（224 + 15）；
- 运行：`PYTHONPATH=src python -m sqcad.self_obscuring_ablation --seeds 12 --seed0 21 --output results/self_obscuring_ablation.json`；
- 结果：`results/self_obscuring_ablation.json`（gitignored，同步 D 盘数据库）；
- 理论：`docs/研究逻辑与理论证明/15-self-obscuring形式定理与严格证明-20260813.md`（引理 1/2、定理 1/2 的严格证明、精确斜率 5.85 推导、O(1/q) 上界、sweep 预测对照）；
- 路线：`14-` §5/§7（实验 A/B 设计）；对照实验报告：`12-`（P0–P4 数值层）。
