# 16-T2 严格 reduction-separation 定理与 P4 minimax 探测下界

> 日期：2026-08-13  
> 文档性质：理论闭环的两个严格化——T2（feedback-preserving reduction 不可能性）与 P4（archived-committed 类的固定样本探测下界）。旧版把 P4 下界与 T1(b) 单世界恢复上界宣称为匹配，现已撤回；有效的同类匹配见 `17-安全恢复证书定理与匹配下界-20260821.md` 的 Theorems 11–13。
> 关联：`15-self-obscuring形式定理与严格证明`（T1 完整证明、T2 argument 级版本）、`14-` §6/§9（定理陈述与验收标准）、`实验证据链/13`（W0–W3 消融与还原控制数值）、`实验证据链/12` §6（P4 数值层）、`实验证据链/14`（本批数值佐证）。
> 声称纪律：T2 与 P4 的固定样本版本给出**明确条件下的数学证明**（配对耦合 + 信息论检测界）；序贯停止实验只作机制/常数阶佐证，不声称达到固定样本常数。

---

## 0. 评审意见与本批升级目标

审稿方要求的两项闭环：

1. **T2 严格化**：若一个 reduction 不增加 evidence-availability、lineage 或 restore 状态，就无法保持原 Agent Memory 问题的反馈语义和次线性可解性。必须严格定义 reduction 的限制——否则审稿人会反驳："任何问题都可以把所有信息编码进 contextual state，所谓不能化约没有意义。"
2. **P4 严格化**：区分两个最优动作相反的世界，对恰好 $n$ 个独立成功探测的固定样本检验，任何最大错误率不超过 $\delta$ 的检验都满足 $n \ge 2\log(1/(2\delta))/\operatorname{KL}$（高斯下为 $\Omega(\log(1/\delta)/\Delta^2)$）；更强版本把 archive-induced censoring 与恢复概率 $q$ 纳入总后悔分解。序贯 CI 停止规则只与该固定样本门槛比较阶和常数，不声称其覆盖率或常数相同。恢复通道因此具有明确的统计信息成本，但不是“固定样本下界被算法精确达到”的工程结论。

完成两项后：Agent Memory 持久访问治理存在由"动作依赖的未来证据流"产生的、不能直接化约为普通 bandit/OPE 的 self-obscuring 基础理论问题——论文可升级为 *persistent agent-memory governance under endogenous evidence flow* 的基础理论（但**不是**"Agent Memory 全部基础理论"，第 5 节明确校准边界）。

---

## 1. T2：严格 reduction-separation 定理

### 1.1 为什么必须形式化 reduction（回应审稿异议）

15- §3 的 argument 级版本依赖两个未固定的约定：(i) reduction 语言（"把问题映射到另一领域"的语义）；(ii) "信息集单调性"约定。审稿异议的精确化是：**若允许 reduction 把世界身份编码进 context，任何问题都可化约为"一看 context 即知答案"的平凡问题**，分离定理即被掏空。

本节的修复是给出一个明确、可验证的约束——**观测映射的世界无关性**：reduction 的观测映射 $\phi$ 只能是"源观测历史的函数"，不能是"源世界（latent）的函数"。该约束下，观测等价（15- 引理 1）通过 reduction 保持，从而 K/A 的图像观测过程逐点相同，任何图像学习者都无法区分两世界。若 $\phi$ 依赖 latent，reduction 已把答案走私进观测——按定义排除。

### 1.2 形式化

**记号**。世界 $W = (\Omega, (y_t, e_t))$：结局流 $y_t$、暴露流 $e_t$，均为（历史, 动作）的随机函数；动作集 $\mathcal{A} = \{\text{keep}, \text{archive}\}$；观测过程 $\mathrm{obs}^t = (t, \text{暴露与结局序列})$ 由协议给出。问题类 $\mathcal{C} = (\mathcal{W}, \Pi)$：世界集 + 策略集（策略 = 观测历史 $\to$ 动作的映射）。逐点后悔：每步（决策点 $n_{\text{early}}$ 后）错误动作损失 $\tau p$（K 世界错误 = archived，A 世界错误 = kept；见 15- 与 `实验证据链/13` §1 的对称损失设定）。

**定义 1（faithful feedback-preserving reduction，忠实保反馈化约）**。从类 $\mathcal{C}$ 到类 $\mathcal{C}'$ 的化约 $R = (R_W, R_\pi, \phi)$ 满足：

(i) **世界映射** $R_W$：$\mathcal{W} \to \mathcal{W}'$，动作集保持（$\mathcal{A}' \supseteq \mathcal{A}$）；
(ii) **策略映射** $R_\pi$：$\Pi' \to \Pi$（目标类策略拉回为源类策略）；
(iii) **观测映射** $\phi = (\phi_t)_{t \ge 0}$，$\phi_t : \mathcal{O}^t \to \mathcal{O}'^t$，**世界无关**（$\phi$ 是"观测历史"的函数，不接收 latent/世界身份）；$\phi$ 可随机化，但分布只依赖于观测历史；
(iv) **反馈保持（feedback preservation）**：对任意 $W \in \mathcal{W}$ 与任意 $\pi' \in \Pi'$，图像世界 $R_W(W)$ 在策略 $\pi'$ 下的观测过程逐点等于 $\phi$ 作用于源世界 $W$ 在 $\pi = R_\pi(\pi')$ 下的观测过程：
$$
\operatorname{obs}'_{R_W(W)}(\pi') \;=\; \phi\bigl(\operatorname{obs}_W(\pi)\bigr) \qquad \text{(a.s.)}

$$
(v) **保真（fidelity）**：对任意 $W, \pi'$：$\operatorname{Regret}_{R_W(W)}(\pi') = \operatorname{Regret}_W(R_\pi(\pi'))$（允许 $o(T)$ 偏差；定理只用到 $\ge$ 方向）。

**定义 2（标准类）**。contextual bandit（每步先显示 context $c_t$，再选动作、只观察所选动作的奖励）、log-based OPE（学习者从日志行 $(x, a, y)$ 训练策略）、以及任何"学习者的观测由协议给出、不额外访问 latent 或动作外的信息"的类。注意：**显式携带 evidence-availability / restore / lineage 状态的类不在标准族内**——这正是分离的靶点。

### 1.3 引理 3（配对耦合的化约不变性）

**设置**：K/A 配对世界，共享耦合（早期流逐位相同、暴露随机数相同，latent $\pm\tau$——15- 引理 1 的构造）。

**引理 3**。设 $R = (R_W, R_\pi, \phi)$ 是从 self-obscuring 类 $\mathcal{C}^*$ 到任意类的忠实保反馈化约。对任意目标策略 $\pi'$，令 $\pi = R_\pi(\pi')$。则图像观测过程逐点相同：
$$
\operatorname{obs}'_{R_W(K)}(\pi') \;=\; \operatorname{obs}'_{R_W(A)}(\pi') \qquad \text{(a.s.)}

$$
特别地，若目标类是 contextual bandit，两图像的 context 序列逐点相同；任何（确定性的）目标策略在两图像中做出相同的动作序列。

**证明**。15- 引理 1：耦合下 $\operatorname{obs}_K(\pi) = \operatorname{obs}_A(\pi)$（决策是观测历史的函数，观测历史相同则动作相同，归纳逐点成立）。定义 1(iv)：$\operatorname{obs}'_{R_W(K)}(\pi') = \phi(\operatorname{obs}_K(\pi))$，$\operatorname{obs}'_{R_W(A)}(\pi') = \phi(\operatorname{obs}_A(\pi))$。由 $\operatorname{obs}_K(\pi) = \operatorname{obs}_A(\pi)$ 逐点相同与 $\phi$ 的世界无关性（定义 1(iii)），右端逐点相等。目标策略的动作是其图像观测历史的函数，故动作序列相同。∎

### 1.4 引理 4（逐点后悔恒等式）

对任意策略 $\pi$（任意自适应、任意翻转），两世界的后悔逐点求和恒为常数：
$$
\mathrm{Regret}_K(\pi) + \mathrm{Regret}_A(\pi) = \tau p\,(T - n_{\mathrm{early}})
\qquad \text{(a.s.)}

$$

**证明**。每步 $t \ge n_{\text{early}}$，动作 $a_t \in \{\text{keep}, \text{archive}\}$。K 世界正确动作 = keep，A 世界正确动作 = archive，故**每步恰好有一个世界动作错误**（keep 时 A 错、archive 时 K 错）。对称损失设定下（`实验证据链/13` §1：K 错误归档步与 A 有害滞留步每步均损失 $\tau p$），逐点后悔之和 = $\tau p \cdot (T - n_{\text{early}})$。∎

（数值对应：任何策略、任何 seed 下 $\operatorname{Regret}_K + \operatorname{Regret}_A \equiv 11700 = 6.0 \times 1950$，`实验证据链/14` §2。）

### 1.5 定理 2（严格版）：保反馈化约不可能性

**定理 2**。设 $\mathcal{C}^*$ 为 self-obscuring 类（K/A 配对、$p_{\text{arch}} = 0$、共享耦合、$\tau > 0$、$p > 0$）。**不存在忠实保反馈化约** $R$ 从 $\mathcal{C}^*$ 到任何标准类 $\mathcal{C}'$（定义 2），使得 $\mathcal{C}'$ 上存在对 $R(\mathcal{C}^*)$ 全体实例 regret 为次线性的策略。更强：对任意忠实保反馈化约 $R$ 与任意目标策略 $\pi'$，
$$
\max_{W \in \{K,A\}} \mathrm{Regret}_{R_W(W)}(\pi') \;\ge\; \frac{1}{2}\,\tau p\,(T - n_{\mathrm{early}}) = \Theta(T).

$$

**证明**。取配对 $(K, A) \in \mathcal{C}^*$ 与任意 $\pi' \in \Pi'$，$\pi = R_\pi(\pi')$。引理 3：$\pi'$ 在两图像中动作序列相同。引理 4（经定义 1(v) 保真传递到图像）：$\operatorname{Regret}_{R(K)}(\pi') + \operatorname{Regret}_{R(A)}(\pi') = \tau p (T - n_{\text{early}})$。故 $\max \ge \tfrac12 \tau p (T - n_{\text{early}})$。次线性不可能。∎

**读法**。下界对"任何标准类、任何化约、任何策略"成立，与目标类的具体结构无关——它只来自两个事实：(a) $\phi$ 世界无关（否则走私答案）；(b) 观测等价被保持（否则化约改变了反馈语义，即定义 1(iv) 不成立）。审稿异议"contextual 编码一切"在此精确失效：context 是 $\phi(\operatorname{obs})$ 的图像观测，而 $\operatorname{obs}_K = \operatorname{obs}_A$。

### 1.6 分离推论

**推论 2（新反馈/状态必要性）**。若忠实保反馈化约 $R$ 在 $\mathcal{C}^*$ 上达到次线性最坏后悔，则必须存在某个图像观测分量不是 $\phi(\operatorname{obs})$ 的函数，或改变源问题的反馈/动作语义。换言之，化约必须增加源观测之外的可用信息或新的反馈通道；在本问题中，evidence-availability / lineage / restore 状态是自然的实现方式，但定理不声称它们是唯一可能的命名或状态分解。直接把世界身份塞进 context 仍被定义 1 的世界无关性排除。因而可严格写成“次线性需要额外可用反馈/状态”，而不能写成对所有化约的“唯一逃逸状态是 evidence availability”。

**推论 3（充分性，15- 定理 1(b)）**。增加 restore 通道（速率 $q$、成功 $\rho$、成本 $c_{\text{restore}}$）后，存在策略满足
$$
\mathbb E[R_T] \;\le\; \frac{\tau p}{q\rho} + \frac{c_{\text{probe}}}{q\rho} + c_{\text{restore}},

$$
与 $T$ 无关（次线性、事实上 $O(1)$（$q$ 固定））。

**组合**（"self-obscuring 不是普通 bandit 的一般探索困难"）：定理 2 把 $\Theta(T)$ 下界提升为所有忠实化约的不变量；推论 2 指出逃逸必须显式增加源观测之外的可用反馈/状态，evidence-availability 是本框架的实现选择而非定理唯一命名。T1(b) 只作单世界诊断；安全恢复的有效上界/下界闭环见 `17-` Theorems 11–13。数值侧：W2 中标准学习者在图像上精确线性 5.85（`实验证据链/13` §4）；latent-augmented 控制（违反 $\phi$ 世界无关性）成功；W3 增加状态后 0.425（`实验证据链/14` §2）。

### 1.7 与 15- §3 argument 级版本的关系

| 15- §3.2 的约定 | 本定理 2 的修复 |
|---|---|
| reduction 语言未固定 | 定义 1：三映射（世界/策略/观测）+ 五条可验证性质 |
| "信息集单调性"约定 | 替换为 $\phi$ 的世界无关性（定义 1(iii)）——明确、可检验 |
| 论证依赖"沉默冻结在像中保持" | 替换为逐点后悔恒等式（引理 4）+ 观测等价保持（引理 3），无需任何策略行为假设 |
| 结论"必须加状态" | 推论 2（必要）+ 推论 3（充分，T1(b)）双方向闭合 |

---

## 2. P4：固定样本探测下界（旧 T1(b) matching 已撤回）

### 2.1 问题类与诚实边界：为什么下界必须在 archived-committed 类陈述

**先消除一个陷阱**：全类 minimax 是 $O(1)$——策略"默认 keep + watchful"在 K 世界零后悔；在 A 世界暴露流 $y \sim N(-\tau, \sigma^2)$ 以速率 $p$ 到达，一步即确认归档（$\tau \gg 0$），错误滞留 $O(1)$ 步。故"任何策略都至少需要 $\Omega(1/\Delta^2)$ 次探测"在**全类上为假**。

论文实际研究并声称 regret 下界的类（T1、T2、`实验证据链/13` 全部数值）是 **archived-committed 类** $\mathcal{C}_{\text{arch}}$：策略在决策点提交 archive（共因先验/门禁触发，或自动归档策略），archive 审查候选流（$p_{\text{arch}} = 0$）。在此类中，证据的唯一通路是 probe/restore——P4 量化的是**提交 archive 决策的统计信息成本**，即错误归档的期望成本。这是诚实且与 T1/T2 同构的边界：$\Omega(T)$ 与探测下界均在此类内成立，且此类正是框架（gate → commit）运作的决策类。

### 2.2 定理 3（P4a）：检测下界

**设置**。$\mathcal{C}_{\text{arch}}$ 内，恢复/探测成功的观测 $y \sim N(\tau, \sigma^2)$（K）或 $N(-\tau, \sigma^2)$（A），$\sigma$ 已知。策略以错误率 $\le \delta$ 在两侧同时正确提交（K 提交 keep、A 提交 archive）所需观测数：

**定理 3（对称高斯固定样本版本）**。对使用恰好 $n$ 个独立成功探测的检验，若 $Y\sim N(\pm\tau,\sigma^2)$ 且最大错误率 $\le \delta<1/2$，则精确最优检验满足
$$
 n \;\ge\; N^*(\delta):=\left\lceil\frac{\sigma^2}{\tau^2}[\Phi^{-1}(1-\delta)]^2\right\rceil
\;=\; \Omega\!\left(\frac{\log(1/\delta)}{\Delta^2}\right).

$$

这里 $\Phi$ 为标准正态分布函数，$N^*$ 是整数门槛。分布无关的 Bretagnolle--Huber/Le Cam 论证仅给出较弱的阶下界 $n\ge \log(1/(4\delta))/\operatorname{KL}$；序贯停止和覆盖率不由此定理推出。

**证明**。等方差高斯的似然比检验在样本均值零处阈值化，最大错误率为 $e_n^*=\Phi(-|\tau|\sqrt n/\sigma)$；解 $e_n^*\le\delta$ 即得上式。通用 BH 界仅用于阶比较，不能替代该精确高斯门槛。∎

### 2.3 定理 4（P4b）：后悔分解下界（censoring 与 q 纳入）

**通道模型**（与 T1(b) 同协议，15- §2.3）：archived 状态下，策略每步以概率至多 $q$ 尝试 probe；尝试成功概率 $\rho$；一次成功暴露一个观测 $y \sim N(\pm\tau, \sigma^2)$，花费 $c_{\text{probe}}$。观测数达到门槛 $N$ 之前，策略无法提交 keep。有限时域下必须对恢复等待和 probe 次数做截断；无截断表达式只作为 $T\to\infty$ 的推论。

为避免把固定样本结论误读成任意序贯策略的下界，定义 $\mathcal{C}_{\text{arch}}^{(N)}\subset\mathcal{C}_{\text{arch}}$ 为以下策略子类：策略在 archived 状态提交后，在获得 $N$ 个成功 probe 观测以前不得提交 keep；每次成功 probe 的信息分布仍为上面的两个高斯假设。对该子类，有下列有限时域结论。

**定理 4（固定探测门槛版本）**。令 $H=T-n_{\mathrm{early}}$，并定义有限时域下界
$$
B_N(H;q\rho):=\sum_{t=0}^{H-1}\Pr\{\operatorname{Bin}(t,q\rho)<N\}.
$$
$\mathcal{C}_{\text{arch}}^{(N)}$ 内任意策略在 K 世界的有限时域生命周期后悔满足
$$
\mathbb E[\mathrm{Regret}^{\mathrm{life}}_K(H)]
\;\ge\; \tau p\,B_N(H;q\rho).

$$

**证明**。令 $S_N$ 为收集 $N$ 个成功的首达时间，若时域内未收集完则令 $S_N=\infty$。生命周期损失为 $\tau p\min\{S_N,H\}$。由生存和恒等式，$\mathbb E[\min\{S_N,H\}]=\sum_{t=0}^{H-1}\Pr(S_N>t)$；条件成功概率至多为 $q\rho$，与 iid Bernoulli$(q\rho)$ 序列耦合得 $\Pr(S_N>t)\ge\Pr\{\operatorname{Bin}(t,q\rho)<N\}$，故得下界。probe 成本另为 $c_{\text{probe}}\mathbb E[A_H]\ge0$，有限时域不应直接替换为 $c_{\text{probe}}N/\rho$。当 $H\to\infty$ 且最终恢复几乎必然发生时，$B_N(H;q\rho)\uparrow N/(q\rho)$、$\mathbb E[A_H]\uparrow N/\rho$，才恢复熟悉的 $(N/\rho)(\tau p/q+c_{\text{probe}})$ 表达式。∎

（A 世界侧：观测 $y \sim N(-\tau)$ 使 CI 在负侧排除 0，策略提交 archive——正确，无生命周期损失；有限时域 probe 成本为 $c_{\text{probe}}\mathbb E[A_H]$，只有无截断极限才为 $c_{\text{probe}}N/\rho$。对一般允许提前停止的序贯检验，应改用 Wald 的 KL 下界和期望样本数，不能直接套用本定理的固定 $N$ 表达式。）

### 2.4 旧匹配 claim 的撤回与有效替代

T1(b) 的单世界诊断上界

$$
\mathbb E_{W+}[R_T]\le \frac{\tau p}{q\rho}+\frac{c_{\text{probe}}}{\rho}+c_{\text{restore}}
$$

只描述“正世界、一次越阈即吸收式 restore”，不控制负世界中的 false restore，也没有支付达到 $N^*(\delta)$ 个样本所需的错误率预算。因此它**不能**与本节固定样本 $N^*(\delta)$ 下界组成 minimax matching；该旧解释已撤回，数值包络只保留作机制诊断。

有效的同阶上界必须使用与下界相同的双侧安全策略类：固定样本证书取得

$$
n_\delta=\left\lceil(\sigma\Phi^{-1}(1-\delta)/\mu)^2\right\rceil
$$

个成功 probe 后按样本均值授权，且显式控制 $P_-(\mathrm{keep})\le\delta$。其有限时域总成本上界为

$$
\frac{\nu n_\delta}{q\rho}+\frac{c_{\text{probe}}n_\delta}{\rho}+c_{\text{restore}}+\nu H\delta,
$$

这是 `17-安全恢复证书定理与匹配下界-20260821.md` Theorem 11 的固定样本实例；Theorem 12 在同一 `Safe(H,delta)` 类给出 transcript-KL、Wald 和 restore-probability 下界，Theorem 13 再给出 anytime/stitched 版本。只有在该同类、有限时域、显式 false-restore 预算下，才可审慎使用“同阶匹配”。

### 2.5 与 12- §6 数值层的关系

12- §6 的 P4 数值（$\operatorname{KL}$ 下界 9.36 vs 停止规则 34.6，3.7×）是无 censoring、无 $q$ 的直接探测模型。本定理 3/4 保留固定样本检测与有限时域等待下界；安全总成本的有效 matching 以 `17-` Theorems 11–13 为准，不再把单世界 T1(b) 与 false-restore 受限下界并列。

---

## 3. 审稿意见逐条回应

| 审稿要求 | 本批交付 |
|---|---|
| T2：严格定义 reduction 限制，否则"contextual 编码一切" | 定义 1：五条可验证性质（动作集合/即时 reward/观测信息保持 + $\phi$ 世界无关 + 保真）；定理 2 证明中引理 3 直接阻断"编码一切"——context 是 $\phi(\operatorname{obs})$ 而 $\operatorname{obs}_K = \operatorname{obs}_A$ |
| T2：最终形式"不存在 feedback-preserving, state-preserving reduction" | 定理 2（不可能性）+ 推论 2（必要：任何次线性化约必须显式加状态）+ 推论 3（充分：T1(b)） |
| P4：固定样本检验的精确下界 $n \ge 2\log(1/(2\delta))/\operatorname{KL}$，高斯 $\Omega(\log(1/\delta)/\Delta^2)$ | 定理 3（固定样本证明） |
| P4：在固定探测门槛子类中纳入 censoring 与 $q$，总后悔 = 证据获取 + 恢复等待 + 错误治理损失 | 定理 4（$\mathcal{C}_{\text{arch}}^{(N)}$ 内，$q$、$\rho$、$c_{\text{probe}}$ 显式） |
| P4：安全恢复的同阶上界/下界 | `17-` Theorems 11–13；P4 本文只保留固定样本检测与等待下界 |
| 校准：不能声称"Agent Memory 全部基础理论" | §5 明确边界 |

## 4. 理论闭环的总陈述

> **Theorem 2 + P4 Theorem 3/4 + `17-` Theorems 11–13**：在 archived-committed 类上，任何忠实保反馈化约保持 $\Theta(T)$ regret（定理 2）；显式增加证据可得性状态是逃逸通道（推论 2）；区分两世界的固定样本检验需要 $\Omega(\log(1/\delta)/\Delta^2)$ 观测（P4 定理 3）；安全恢复的生命周期、probe 与 restore 总成本在同一 `Safe(H,delta)` 类中具有上/下界同阶（`17-` Theorems 11–13）。旧 T1(b)/P4 matching 解释已撤回。

因此：**Agent Memory 的持久访问治理存在由"动作依赖的未来证据流"产生的、不能直接化约为普通 bandit/OPE 的 self-obscuring 基础理论问题**（验收条件 1、2、3 全部严格满足——见 `实验证据链/14` §5 的判定表）。

## 5. 校准边界（仍然不能说）

- 这不是"Agent Memory 全部基础理论"：不覆盖压缩/检索质量、不覆盖多记忆竞争预算、不覆盖任务漂移下的非参数异质性、不覆盖 authorization certificate 的完整形式化（P0 遗留）；
- 定理 2 的"标准类"边界：定义 2 排除带证据可得性状态的类——这正是分离的靶点而非限制；任何声称化约到"更丰富状态类"的方案等于承认需要新状态（推论 2）；
- P4 固定门槛结果只针对固定样本检测子类；安全 matching 只在 `17-` 声明的 `Safe(H,delta)` 类、有限 horizon 和 false-restore 预算下成立；对允许默认 keep 或任意更大策略类不外推；
- trace-grounded 真实轨迹对应物仍未做（验收 6/7 待办）。

## 6. 复现信息

- 理论：本文档（定义 1/2、引理 3/4、定理 2/3/4、推论 2/3/4 完整证明）；
- 数值：`src/sqcad/reduction_closure.py`（配对恒等式、化约像上的标准学习者、latent-augmented 控制、检测界扫描、后悔分解）；结果 `results/reduction_closure.json`；报告 `实验证据链/14`；
- 前置：`15-`（引理 1/2、T1(a)(b)(c)）、`13` 报告（W0–W3 数值）、`12` 报告 §6（P4 数值层）。
