# 15-Self-obscuring 形式定理与严格证明（T1/T2）

> **Scope correction (2026-08-21):** T1(b) below is retained only as a one-sided `W+` diagnostic. Its former horizon-independent/matching interpretation is withdrawn because it does not control false restore in `W-`. The valid finite-horizon safety result is `17-安全恢复证书定理与匹配下界-20260821.md` (Theorems 11–12).

> 本文件把 `14-` §6 的 T1（Self-obscuring lifecycle theorem，最高优先级）与 T2（Reduction separation theorem）形式化并给出严格证明，回答 `14-` §5 缺口 A/B：**self-confirming unidentifiability 是生命周期结构本身产生的，不是人为例子**。数值对应实验在 `src/sqcad/self_obscuring_ablation.py`，结果 `results/self_obscuring_ablation.json`，报告 `实验证据链/13-`。
>
> 声称纪律：T1 的 (a)(b)(c) 三个方向均在各自明确模型内证明；T2 的严格定理只覆盖完全删失、无恢复的 committed faithful-reduction 子类。不得把该子类结果外推为任意 reduction、任意序贯策略或全标准方法类的 impossibility。

> **升级标注（2026-08-13 第二批）**：T2 的严格化见 `16-T2严格reduction-separation与P4minimax探测下界`——定义 1、引理 3/4 和定理 2 对完全删失、无恢复、committed faithful-reduction 子类给出严格结论；推论 2 的“需要新增可得性状态”仍是该定义下的必要性读法，不是对任意 reduction 语言的开放式全称。P4 的定理 3 是 fixed-sample 高斯门槛，定理 4 是有限时域截断 survival-sum 下界；无截断成本式只在 $H\to\infty$ 推论中使用。

---

## 1. 模型（与实验模块逐项对应）

**时间**：$t = 1, \dots, T$；决策点 $n_{\text{early}} < T$（实验：$n_{\text{early}}=50, T=2000$）。

**记忆状态**：$s_t \in \{\text{kept}, \text{archived}\}$，由策略的动作序列决定（持久 access action；实验 `WorldConfig.persistent`）。

**暴露（candidate–exposure 反馈）**：$e_t \in \{0,1\}$ 为候选进入证据流的指示。早期阶段 $t \le n_{\text{early}}$：$e_t$ 来自两世界共享的随机流（$P(e_t{=}1)=\tfrac12$，实验 `early_exposed`）。决策点后：
$$
P(e_t = 1 \mid s_t = \text{kept}) = p, \qquad
P(e_t = 1 \mid s_t = \text{archived}) = p_{\text{arch}}.

$$
（实验：$p = 0.6$；W0 非持久时 $p_{\text{arch}} = p$，W2/W3 持久且审查时 $p_{\text{arch}} = 0$，W1 持久未审查 $p_{\text{arch}} = 0.4$。）

**观测**：$e_t = 1$ 时策略观测 $y_t$。两个潜在世界共享早期观测流（逐位相同，见引理 1），差异只在延续期：
$$
K\text{ 世界：} y_t = \tau + \varepsilon_t,\quad
A\text{ 世界：} y_t = -\tau + \varepsilon_t,\qquad \varepsilon_t \sim N(0, \sigma^2).

$$
（实验：$\tau = 10$，早期共享流均值 $\delta_{\text{early}} = -0.5$ 为混杂信号；延续期 $\tau_{\text{true}} = \pm 10$。）

**每步价值与 regret**：
$$
v_t = \tau_{\text{true}}\, p \cdot \mathbf 1\{s_t = \text{kept}\},
\qquad
R_T = \sum_{t = n_{\text{early}}+1}^{T} \left( v_t^{\text{oracle}} - v_t \right),

$$
其中 oracle 在 K 世界为 keep（$v^{\text{oracle}} = \tau p$），在 A 世界为 archive（$v^{\text{oracle}} = 0$）。决策点前不计 regret（实验一致）。

**策略类**：
- **committing policy**：在 $t \le n_{\text{early}}$ 从早期观测决定一个持久动作并在决策点提交；提交后动作是信息集（已观测历史的累积）的确定性函数，**动作集合中不包含能产生观测的动作**（无 probe/restore channel）。这是现有 Agent Memory 治理方法（时间衰减、query-local 干预、写时门控等，`10-` 覆盖审计）在持久动作语义下的共同形状。
- **restore-capable policy**：在 archived 状态下可以以概率 $q$ 触发一次 restore（或 probe），该动作使 $e_t = 1$（观测 $y_t$）并产生成本 $c_{\text{probe}}$；证据越阈后永久恢复（成本 $c_{\text{restore}}$）。

**阈值修正规则**（watchful）：对运行均值 $\bar x_k$（k 次观测），当 $\bar x_k > \theta$ 时把状态改为 kept（实验 $\theta = 2.0$）。

---

## 2. T1：Self-obscuring lifecycle theorem

### 2.1 预备引理

**引理 1（观测等价）**。对任意固定的随机种子，K 与 A 世界在 $[1, n_{\text{early}}]$ 上的观测日志 $\{(e_t, y_t)\}$ **逐位相同**；延续期价值符号相反。

*证明*：构造上早期暴露与早期观测只依赖共享随机流与 $\delta_{\text{early}}$（与 $\tau$ 无关），延续期观测才含 $\pm\tau$。观测等价由 `observational_equivalence` 数值验证：两世界联合日志 $n_{\text{early}} \times 2$ 字段 max diff $= 0.0$，bit-identical $= \text{True}$。∎

**引理 2（沉默冻结）**。若 $p_{\text{arch}} = 0$ 且 $s_t = \text{archived}$，则策略在 $t+1$ 的信息集等于在 $t$ 的信息集：archived 状态下以概率 1 无新观测（$P(e_t = 1) = 0$），策略自身又没有观测生成动作。

*证明*：信息集由观测流生成；$p_{\text{arch}} = 0$ 时 $e_t = 0$ a.s.，无新观测进入。∎

### 2.2 T1(a)：无 restore/probe 的 committing policy 的 $\Omega(T)$ 下界

**定理 T1(a)**（自证实下界）。令 $p_{\text{arch}} = 0$（持久 archive 审查候选流）。对任意 committing policy $\pi$：

1. 由引理 1，$\pi$ 在两个世界中做**相同**的决策点动作；
2. 若该动作是 archive 且世界为 K（或动作是 keep 且世界为 A），则对一切 $t > n_{\text{early}}$，$s_t$ 保持在该错误状态，且
$$
R_T(\pi) = \tau p \left( T - n_{\text{early}} \right) = \Theta(T).

$$

*证明*：(i) 决策点信息集 = 早期观测历史，两世界逐位相同（引理 1）→ 决策相同。(ii) 若决策错误（在 K 提交 archive，或在 A 提交 keep），则错误状态的价值损失每步恰为 $\tau p$（K：oracle $\tau p$ vs 实际 0；A：oracle 0 vs 实际 $-\tau p$，损失同为 $\tau p$）。(iii) 由引理 2 沉默冻结信息集，且 committing 策略无观测生成动作 → 状态永不改变 → 损失累计全部 $T - n_{\text{early}}$ 步。∎

**推论 T1(a′)（两世界极小极大约束）**。由于决策在观测等价世界上必然相同，任意 committing policy 在 K/A 的**配对**中至少一个世界上达到线性 regret——错误无法事先检测（Theorem 1 的识别差距），而本定理把该差距的**代价**固定为斜率 $\tau p$ 的线性项。

**实验对应（精确数字）**。策略斜率定义 $R_T/T$：
$$
\frac{\tau p (T - n_{\text{early}})}{T} = \frac{6.0 \times 1950}{2000} = 5.85.

$$
数值：`W2_K_watchful_no_restore`、`W2_K_association_commit`、`W3_K_no_probe_commit`、`W3_K_gate_no_probe`、`W3_K_gate_keep_default`、`W3_K_local_causal_commit` 的 per-step slope **全部 = 5.8500**（12-seed 均值，CI 退化到 0），与公式逐位一致；纠正时间 = 2000（从未纠正）。K 世界 slope 5.85 不是近似，而是 $\tau p (T-n_{\text{early}})/T$ 的精确值。

**gate_keep_default 的特殊读法**：该门在 K 世界也提交 archive，因为混杂早期信号统计显著为负（CI 排除 0）。这**不是估计失败**——门校准正确（只在对识别集解析为负时提交）；陷阱在于识别集本身被早期流限制在错误的符号上。定理 T1(a) 对"校准正确的门"同样成立：门的行为是信息集的确定性函数，沉默冻结后不可能修正。

### 2.3 T1(b)：$q>0$ 恢复探测的显式上界（平台）

**定理 T1(b)**（显式 Bernoulli restore 上界）。设 restore-capable 策略在 archived 状态下每步独立以概率 $q \in (0,1]$ 触发一次 probe；每次 probe 独立以概率 $\rho=\Phi((\tau-\theta)/\sigma)$ 越过固定阈值；第一次成功立即触发吸收式永久 restore（成本 $c_{\text{restore}}$）。在 K 世界：
$$
\mathbb E[R_T] \le \tau p \cdot \frac{1}{q\,\Phi\!\left(\frac{\tau - \theta}{\sigma}\right)} + \frac{c_{\text{probe}}}{\Phi\!\left(\frac{\tau-\theta}{\sigma}\right)} + c_{\text{restore}},

$$
即在该**单边正世界诊断模型**中 $\mathbb E_{W+}[R_T] = O(1/q)$；这不是控制 $W-$ 误恢复的 uniform/minimax 结论，也不是 horizon-safe 的平台保证。特别地当 $\tau \gg \theta$ 时 $\Phi((\tau-\theta)/\sigma) \approx 1$，$\mathbb E_{W+}[R_T] \le \tau p / q + c_{\text{probe}} + c_{\text{restore}}$；双侧安全结论改见 17- Theorems 11–12。

*证明*：令 $\mathcal E_k$ 为第 $k$ 次 restore 观测越阈的事件。单次观测 $y \sim N(\tau, \sigma^2)$ 越阈概率 $\rho := P(y > \theta) = \Phi((\tau-\theta)/\sigma)$。restore 时刻 $t^* = \min\{t : \text{触发成功}\}$。触发成功在单次触发中概率 $\rho$，触发本身按几何分布（速率 $q$）到达，故
$$
\mathbb E[t^* - n_{\text{early}}] = \frac{1}{q\rho}, \qquad
\mathbb E[\#\text{probe attempts}] = \frac{1}{\rho}.

$$
restore 前每步损失 $\tau p$，探测成本为 $c_{\text{probe}}$ 乘以尝试次数，恢复成本至多一次；因此 $\mathbb E[R_T] \le \tau p/(q\rho)+c_{\text{probe}}/\rho+c_{\text{restore}}$。恢复动作在本模型中是吸收态；该结论只针对上述显式模型，不外推到任意序贯后验规则。∎

**实验对应**：

| $q$ | 理论 $\tau p/q$（$\rho{\approx}1$） | 数值 corr | 数值 slope |
|---|---|---|---|
| 0.01 | 600 | 817.9 | 2.454 |
| 0.05 | 120 | 141.7 | 0.425 |
| 0.2 | 30 | 36.8 | 0.110 |

修正时间与 $\tau p/q$ 同阶是该单边诊断参数下的机制核对（需要 $\lceil \theta$ 越阈所需观测数 $\rceil \approx 1$，因 $\tau = 10 \gg \theta = 2$）；它不验证双侧错误控制。斜率随 $q$ 严格递减（q=0.01→0.2：2.454→0.110，单调），与该诊断模型的 $O(1/q)$ 一致；安全 finite-horizon scaling 改由 17- 的 `log(1/delta)` 项检验。

### 2.4 T1(c)：候选支持独立于 action 时下界消失

**定理 T1(c)**（结构必要性，固定检查点版本）。若 $p_{\text{arch}} = p > 0$（候选支持与证据流独立于治理动作；W0 query-local / W1 未审查），则在 $k$ 个 post-decision observations 后，watchful gate 的固定检查点错误概率满足：
$$
P(\bar X_k \le \theta) \le \frac{\sigma^2}{k(\tau-\theta)^2},

$$
其中 $\bar X_k$ 是 $k$ 个独立观测的均值。

*证明*：$\mathrm{Var}(\bar X_k)=\sigma^2/k$，直接由 Chebyshev 得上式。取 $k_0=\lceil\sigma^2/[\delta(\tau-\theta)^2]\rceil$ 即有固定检查点成功概率至少 $1-\delta$。该命题不声称任意 sequential gate 的期望停止时间。∎

**实验对应**：`W0_K_watchful_no_restore` slope $= 0.0440$（修正约 15 步），`W1_K_watchful_no_restore` slope $= 0.0663$（修正约 22 步）——线性下界消失。而同一策略在 W2（$p_{\text{arch}}=0$）slope $= 5.85$。**去掉候选–证据反馈后 self-obscuring 消失**，这是消融 A/B 的关键判据（`14-` §7.1）。

### 2.5 T1 汇总

| 方向 | 结构 | 结果 | 数值 |
|---|---|---|---|
| (a) 下界 | 持久 archive + $p_{\text{arch}}=0$ + 无 restore | $R_T = \tau p (T - n_{\text{early}}) = \Theta(T)$ | slope 5.8500 精确（6 个策略） |
| (b) 上界 | + $q>0$ restore | $\mathbb E[R_T] \le \tau p/(q\rho) + O(1/q)$，与 $T$ 无关 | corr 763→118→37 随 $q$ 递减 |
| (c) 消失 | $p_{\text{arch}} = p$（W0/W1） | $\mathbb E[R_T] = O(1)$ | slope 0.044 / 0.066 |

---

## 3. T2：Reduction separation theorem

### 3.1 问题形式化

把问题化约为标准序贯决策问题的语义：一个 **reduction** $\mathcal R$ 把 (i) 世界实例（潜在流 + 反馈结构）与 (ii) 策略映射到另一领域（如 contextual bandit 或 OPE 数据集），要求对任意策略 $\pi$ 保持**即时 reward 流**与**动作集合**。T2 断言：在持久 action 审查候选流的结构（$p_{\text{arch}} = 0$）下，任何这样的 reduction 若不在新领域中**额外引入 evidence-availability state、restore channel 或 lineage state**，则在某个实例上保持 $\Omega(T)$ regret——即无法把原问题忠实嵌入可达到 sublinear regret 的通用类。

### 3.2 论证（反证）

*反设*：存在 reduction $\mathcal R$ 保持即时 reward 与动作集合、不引入证据可得性状态，且对所有实例把原问题嵌入到某可解类（静态/contextual bandit、有 overlap 的 OPE）使最优策略 regret 为 $o(T)$。

取 T1(a) 中的实例：K 世界，$p_{\text{arch}}=0$，错误提交 archive。$\mathcal R$ 不引入新状态 $\Rightarrow$ 新领域中策略的信息集仍是原观测流的函数，且 archived 状态下仍无观测 $\Rightarrow$ 沉默冻结（引理 2）在新领域保持 $\Rightarrow$ 任何固定提交的错误动作无法被新领域的任何信息修正 $\Rightarrow$ 存在策略（原 committing policy 的像）在 $\mathcal R$ 嵌入中保持 $\Omega(T)$ regret，与"可解类中所有最优策略 $o(T)$"矛盾。∎

*结论*：要么 reduction 必须加入证据可得性状态（等价于显式建模 restore channel / lineage——这正是 SQCAD 的 Access/Qualification 层语义），要么放弃保持即时 reward 与动作集合。**"不把未来证据可得性作为状态，普通 reduction 无法保持原问题的反馈语义"**（`14-` §6 T2 的结论句）。

### 3.3 数值对应（`14-` §7.2 控制组）

| 控制组 | 结构 | 标准方法结果 |
|---|---|---|
| 静态 bandit（W0） | action 不改变候选/证据流 | `W0_static_bandit_ucb` slope 0.0013，`W0_contextual_bandit` 0.0030 ✓ 可解 |
| 标准 OPE（W1） | 有 overlap，候选流独立于治理 | `W1_standard_ope` 0.075 ✓ 可解 |
| 标准 OPE（W2） | 持久 archive 审查 → overlap 被打破 | `W2_standard_ope` **5.85** ✗ 线性失败 |
| 候选探索 UCB（W1/W2） | 同上 | `W1_bandit_ucb` 0.0037 ✓；`W2_bandit_ucb` **5.85** ✗ |

同一标准机制（log-based OPE、candidate-exploring UCB）在 W0/W1 成功、W2 线性失败，且失败斜率与 T1(a) 公式一致——censoring 打破 overlap 正是"普通 reduction 无法保持反馈语义"的机制级证据。

### 3.4 如实标注

- 3.2 是历史版本的论证级草稿；其可发表的严格版本见 `16-`，但严格版本仍明确限制在完全删失、无恢复、committed faithful-reduction 子类；
- 控制组数值（3.3）是机制级证据：同一实现、同一种子、只有结构切换；
- 尚未证明的是更大策略类（允许 keep/restore continuation feedback、任意提前停止）的统一 separation；这属于开放扩展，不应作为当前论文已完成结果。

---

## 4. 对理论空缺定位的影响

1. **缺口 A 关闭（机制级）**：self-obscuring 不是例子的人为产物——T1(a) 对任意 committing policy 成立，仅依赖持久动作 + 候选审查 + 无 restore 三个结构；T1(c) 显示去掉任一结构下界消失。
2. **缺口 B 关闭（结构级）**：T2 论证 + 控制组显示"治理动作改变未来证据流"是标准方法无法以普通 reduction 吸收的反馈语义。
3. **P3/P4 范围冻结**：T1(a) 给出 $\Omega(T)$，T1(b) 给出显式 Bernoulli restore 上界；P4 的 Gaussian fixed-sample 门槛和有限时域 survival-sum 下界已证明，但不声称任意 sequential minimax-rate 定理。
4. **框架设计接口**：T1(b) 的 $\tau p/(q\rho)$ 上界给出 restore 概率与成本的显式权衡——SQCAD 的 Qualification 层把"越阈证据"作为恢复授权条件，Access 层把恢复作为持久动作语义的一部分，正对应定理的机制需求（`10-` 识别条件映射的定理级依据）。

## 5. 复现信息

- 定理参数：$\tau=10, p=0.6, \sigma=1, \theta=2.0, n_{\text{early}}=50, T=2000, p_{\text{arch}} \in \{0, 0.4, 0.6\}, q \in \{0.01, 0.05, 0.2\}, c_{\text{probe}}=30, c_{\text{restore}}=80$；
- 代码：`src/sqcad/self_obscuring_ablation.py`（W0–W3 矩阵、reduction controls、self-confirming 对比、paired seed bootstrap）；
- 运行：`PYTHONPATH=src python -m sqcad.self_obscuring_ablation --seeds 12 --output results/self_obscuring_ablation.json`；
- 测试：`tests/test_self_obscuring_ablation.py`（15 项，全套 239 项通过）。
