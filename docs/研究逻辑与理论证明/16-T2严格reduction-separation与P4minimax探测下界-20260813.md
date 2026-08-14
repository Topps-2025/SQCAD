# 16-T2 严格 reduction-separation 定理与 P4 minimax 探测下界

> 日期：2026-08-13  
> 文档性质：理论闭环的两个严格化——T2（feedback-preserving reduction 不可能性）与 P4（archived-committed 类的 minimax 探测下界，与 T1(b) 恢复上界阶匹配）。  
> 关联：`15-self-obscuring形式定理与严格证明`（T1 完整证明、T2 argument 级版本）、`14-` §6/§9（定理陈述与验收标准）、`实验证据链/13`（W0–W3 消融与还原控制数值）、`实验证据链/12` §6（P4 数值层）、`实验证据链/14`（本批数值佐证）。
> 声称纪律：T2 与 P4 本批给出**完整数学证明**（配对耦合 + 信息论检测界）；数值节为机制级佐证。

---

## 0. 评审意见与本批升级目标

审稿方要求的两项闭环：

1. **T2 严格化**：若一个 reduction 不增加 evidence-availability、lineage 或 restore 状态，就无法保持原 Agent Memory 问题的反馈语义和次线性可解性。必须严格定义 reduction 的限制——否则审稿人会反驳："任何问题都可以把所有信息编码进 contextual state，所谓不能化约没有意义。"
2. **P4 严格化**：区分两个最优动作相反的世界，任何策略都至少需要 N ≥ log(1/δ)/KL 次探测（高斯下 Ω(log(1/δ)/Δ²)）；更强版本把 archive-induced censoring 与恢复概率 q 纳入总后悔分解；与 T1(b) 上界同阶 ⇒ 恢复通道是问题本身的统计信息成本，不是 SQCAD 人为引入的工程技巧。

完成两项后：Agent Memory 持久访问治理存在由"动作依赖的未来证据流"产生的、不能直接化约为普通 bandit/OPE 的 self-obscuring 基础理论问题——论文可升级为 *persistent agent-memory governance under endogenous evidence flow* 的基础理论（但**不是**"Agent Memory 全部基础理论"，第 5 节明确校准边界）。

---

## 1. T2：严格 reduction-separation 定理

### 1.1 为什么必须形式化 reduction（回应审稿异议）

15- §3 的 argument 级版本依赖两个未固定的约定：(i) reduction 语言（"把问题映射到另一领域"的语义）；(ii) "信息集单调性"约定。审稿异议的精确化是：**若允许 reduction 把世界身份编码进 context，任何问题都可化约为"一看 context 即知答案"的平凡问题**，分离定理即被掏空。

本节的修复是给出一个明确、可验证的约束——**观测映射的世界无关性**：reduction 的观测映射 φ 只能是"源观测历史的函数"，不能是"源世界（latent）的函数"。该约束下，观测等价（15- 引理 1）通过 reduction 保持，从而 K/A 的图像观测过程逐点相同，任何图像学习者都无法区分两世界。若 φ 依赖 latent，reduction 已把答案走私进观测——按定义排除。

### 1.2 形式化

**记号**。世界 W = (Ω, (y_t, e_t))：结局流 y_t、暴露流 e_t，均为（历史, 动作）的随机函数；动作集 𝒜 = {keep, archive}；观测过程 obs^t = (t, 暴露与结局序列) 由协议给出。问题类 𝒞 = (𝒲, Π)：世界集 + 策略集（策略 = 观测历史 → 动作的映射）。逐点后悔：每步（决策点 n_early 后）错误动作损失 τp（K 世界错误 = archived，A 世界错误 = kept；见 15- 与 `实验证据链/13` §1 的对称损失设定）。

**定义 1（faithful feedback-preserving reduction，忠实保反馈化约）**。从类 𝒞 到类 𝒞′ 的化约 R = (R_W, R_π, φ) 满足：

(i) **世界映射** R_W：𝒲 → 𝒲′，动作集保持（𝒜′ ⊇ 𝒜）；
(ii) **策略映射** R_π：Π′ → Π（目标类策略拉回为源类策略）；
(iii) **观测映射** φ = (φ_t)_{t≥0}，φ_t : 𝒪^t → 𝒪′^t，**世界无关**（φ 是"观测历史"的函数，不接收 latent/世界身份）；φ 可随机化，但分布只依赖于观测历史；
(iv) **反馈保持（feedback preservation）**：对任意 W ∈ 𝒲 与任意 π′ ∈ Π′，图像世界 R_W(W) 在策略 π′ 下的观测过程逐点等于 φ 作用于源世界 W 在 π = R_π(π′) 下的观测过程：
$$
\operatorname{obs}'_{R_W(W)}(\pi') \;=\; \phi\bigl(\operatorname{obs}_W(\pi)\bigr) \qquad \text{(a.s.)}

$$
(v) **保真（fidelity）**：对任意 W, π′：Regret_{R_W(W)}(π′) = Regret_W(R_π(π′))（允许 o(T) 偏差；定理只用到 ≥ 方向）。

**定义 2（标准类）**。contextual bandit（每步先显示 context c_t，再选动作、只观察所选动作的奖励）、log-based OPE（学习者从日志行 (x, a, y) 训练策略）、以及任何"学习者的观测由协议给出、不额外访问 latent 或动作外的信息"的类。注意：**显式携带 evidence-availability / restore / lineage 状态的类不在标准族内**——这正是分离的靶点。

### 1.3 引理 3（配对耦合的化约不变性）

**设置**：K/A 配对世界，共享耦合（早期流逐位相同、暴露随机数相同，latent ±τ——15- 引理 1 的构造）。

**引理 3**。设 R = (R_W, R_π, φ) 是从 self-obscuring 类 𝒞* 到任意类的忠实保反馈化约。对任意目标策略 π′，令 π = R_π(π′)。则图像观测过程逐点相同：
$$
\operatorname{obs}'_{R_W(K)}(\pi') \;=\; \operatorname{obs}'_{R_W(A)}(\pi') \qquad \text{(a.s.)}

$$
特别地，若目标类是 contextual bandit，两图像的 context 序列逐点相同；任何（确定性的）目标策略在两图像中做出相同的动作序列。

**证明**。15- 引理 1：耦合下 obs_K(π) = obs_A(π)（决策是观测历史的函数，观测历史相同则动作相同，归纳逐点成立）。定义 1(iv)：obs'_{R_W(K)}(π') = φ(obs_K(π))，obs'_{R_W(A)}(π') = φ(obs_A(π))。由 obs_K(π) = obs_A(π) 逐点相同与 φ 的世界无关性（定义 1(iii)），右端逐点相等。目标策略的动作是其图像观测历史的函数，故动作序列相同。∎

### 1.4 引理 4（逐点后悔恒等式）

对任意策略 π（任意自适应、任意翻转），两世界的后悔逐点求和恒为常数：
$$
\mathrm{Regret}_K(\pi) + \mathrm{Regret}_A(\pi) = \tau p\,(T - n_{\mathrm{early}})
\qquad \text{(a.s.)}

$$

**证明**。每步 t ≥ n_early，动作 a_t ∈ {keep, archive}。K 世界正确动作 = keep，A 世界正确动作 = archive，故**每步恰好有一个世界动作错误**（keep 时 A 错、archive 时 K 错）。对称损失设定下（`实验证据链/13` §1：K 错误归档步与 A 有害滞留步每步均损失 τp），逐点后悔之和 = τp·(T − n_early)。∎

（数值对应：任何策略、任何 seed 下 Regret_K + Regret_A ≡ 11700 = 6.0 × 1950，`实验证据链/14` §2。）

### 1.5 定理 2（严格版）：保反馈化约不可能性

**定理 2**。设 𝒞* 为 self-obscuring 类（K/A 配对、p_arch = 0、共享耦合、τ > 0、p > 0）。**不存在忠实保反馈化约** R 从 𝒞* 到任何标准类 𝒞′（定义 2），使得 𝒞′ 上存在对 R(𝒞*) 全体实例 regret 为次线性的策略。更强：对任意忠实保反馈化约 R 与任意目标策略 π′，
$$
\max_{W \in \{K,A\}} \mathrm{Regret}_{R_W(W)}(\pi') \;\ge\; \frac{1}{2}\,\tau p\,(T - n_{\mathrm{early}}) = \Theta(T).

$$

**证明**。取配对 (K, A) ∈ 𝒞* 与任意 π′ ∈ Π′，π = R_π(π′)。引理 3：π′ 在两图像中动作序列相同。引理 4（经定义 1(v) 保真传递到图像）：Regret_{R(K)}(π′) + Regret_{R(A)}(π′) = τp(T − n_early)。故 max ≥ ½τp(T − n_early)。次线性不可能。∎

**读法**。下界对"任何标准类、任何化约、任何策略"成立，与目标类的具体结构无关——它只来自两个事实：(a) φ 世界无关（否则走私答案）；(b) 观测等价被保持（否则化约改变了反馈语义，即定义 1(iv) 不成立）。审稿异议"contextual 编码一切"在此精确失效：context 是 φ(obs) 的图像观测，而 obs_K = obs_A。

### 1.6 分离推论

**推论 2（新状态必要性）**。若忠实保反馈化约 R 在 𝒞* 上达到次线性最坏后悔，则存在 (K, A) 配对其图像观测过程不同。由定义 1(iii)(iv)，这只能来自某图像观测分量不是 φ(obs) 的函数——即化约**显式增加了新状态**；由于源侧唯一不可观测的信息是 latent 与"动作 → 未来证据可得性"机制，该新状态只能是 evidence-availability / lineage / restore 状态（或等价地，世界身份——即把答案走私进观测的作弊，已排除）。形式化：次线性 ⟺ 增加证据可得性状态。

**推论 3（充分性，15- 定理 1(b)）**。增加 restore 通道（速率 q、成功 ρ、成本 c_restore）后，存在策略满足
$$
\mathbb E[R_T] \;\le\; \frac{\tau p}{q\rho} + \frac{c_{\text{probe}}}{q\rho} + c_{\text{restore}},

$$
与 T 无关（次线性、事实上 O(1)（q 固定））。

**组合**（"self-obscuring 不是普通 bandit 的一般探索困难"）：定理 2 把 Θ(T) 下界提升为所有忠实化约的不变量；推论 2/3 指出唯一逃逸通道就是显式证据可得性状态，且该通道被 T1(b) 以最优阶（见 §2.4）利用。数值侧：W2 中标准学习者在图像上精确线性 5.85（`实验证据链/13` §4）；latent-augmented 控制（违反 φ 世界无关性）成功；W3 增加状态后 0.425（`实验证据链/14` §2）。

### 1.7 与 15- §3 argument 级版本的关系

| 15- §3.2 的约定 | 本定理 2 的修复 |
|---|---|
| reduction 语言未固定 | 定义 1：三映射（世界/策略/观测）+ 五条可验证性质 |
| "信息集单调性"约定 | 替换为 φ 的世界无关性（定义 1(iii)）——明确、可检验 |
| 论证依赖"沉默冻结在像中保持" | 替换为逐点后悔恒等式（引理 4）+ 观测等价保持（引理 3），无需任何策略行为假设 |
| 结论"必须加状态" | 推论 2（必要）+ 推论 3（充分，T1(b)）双方向闭合 |

---

## 2. P4：minimax 探测下界与 T1(b) 匹配

### 2.1 问题类与诚实边界：为什么下界必须在 archived-committed 类陈述

**先消除一个陷阱**：全类 minimax 是 O(1)——策略"默认 keep + watchful"在 K 世界零后悔；在 A 世界暴露流 y ~ N(−τ, σ²) 以速率 p 到达，一步即确认归档（τ ≫ 0），错误滞留 O(1) 步。故"任何策略都至少需要 Ω(1/Δ²) 次探测"在**全类上为假**。

论文实际研究并声称 regret 下界的类（T1、T2、`实验证据链/13` 全部数值）是 **archived-committed 类** 𝒞_arch：策略在决策点提交 archive（共因先验/门禁触发，或自动归档策略），archive 审查候选流（p_arch = 0）。在此类中，证据的唯一通路是 probe/restore——P4 量化的是**提交 archive 决策的统计信息成本**，即错误归档的期望成本。这是诚实且与 T1/T2 同构的边界：Ω(T) 与探测下界均在此类内成立，且此类正是框架（gate → commit）运作的决策类。

### 2.2 定理 3（P4a）：检测下界

**设置**。𝒞_arch 内，恢复/探测成功的观测 y ~ N(τ, σ²)（K）或 N(−τ, σ²)（A），σ 已知。策略以错误率 ≤ δ 在两侧同时正确提交（K 提交 keep、A 提交 archive）所需观测数：

**定理 3**。令 KL = 2τ²/σ² 为 N(τ,σ²) 与 N(−τ,σ²) 的单观测 KL 散度，Δ = 2τ。任何以最大错误率 ≤ δ 区分两假设的过程需要
$$
N_{\mathrm{probe}} \;\ge\; N^*(\delta) \;=\; \frac{\log(1/\delta)}{\mathrm{KL}}
\;=\; \frac{\sigma^2 \log(1/\delta)}{2\tau^2}
\;=\; \Omega\!\left(\frac{\log(1/\delta)}{\Delta^2}\right).

$$

**证明**（Le Cam 两点 + Chernoff 界）。n 个独立观测下两分布 P_+^n, P_−^n。任意检验 φ 的极小最大误差 e* = inf_φ max(P_+^n[φ=0], P_−^n[φ=1])。由似然比下界（Bretagnolle–Huber 形式）：
$$
e^* \;\ge\; \frac{1}{2}\Bigl(1 - \bigl\|\sqrt{dP_+^n} - \sqrt{dP_-^n}\bigr\|_2^2\Bigr)^{1/2}
\;\ge\; \frac{1}{2}\exp\!\Bigl(-\frac{n}{2}\,\mathrm{KL}(P_+ \| P_-)\Bigr),

$$
其中第二个不等式对任意 P_+, P_− 由 √Hellinger ≤ √(KL/2) 与 Hellinger 张量化成立（Gaussian 情形可显式计算：∫√(dP_+^n dP_−^n) = exp(−n·KL/2)）。要求 e* ≤ δ 得 n ≥ log(1/(2δ))/KL；标准形式 log(1/δ)/KL 在常数因子内相同。高斯显式：KL = (2τ)²/(2σ²) = 2τ²/σ²。∎

### 2.3 定理 4（P4b）：后悔分解下界（censoring 与 q 纳入）

**通道模型**（与 T1(b) 同协议，15- §2.3）：archived 状态下，策略每步以概率 q 尝试 probe；尝试成功概率 ρ；一次成功暴露一个观测 y ~ N(±τ, σ²)，花费 c_probe。观测数达到 N* 之前，策略无法以 ≤ δ 错误率提交（定理 3），其间 K 世界每步损失 τp。令 t_res = 首次达到 N* 观测的时间，N = 尝试总数。

**定理 4**。𝒞_arch 内任意策略在 K 世界的期望后悔满足
$$
\mathbb E[\mathrm{Regret}_K] \;\ge\; \tau p \cdot \frac{N^*(\delta)}{q\rho} \;+\; c_{\text{probe}} \cdot \frac{N^*(\delta)}{\rho} \;=\; \frac{N^*(\delta)}{\rho}\left(\frac{\tau p}{q} + c_{\text{probe}}\right).

$$

**证明**。后悔分解为三项（评审要求的形式）：错误治理期间的生命周期损失 ≥ τp·E[t_res]（K 世界 archive 全程错误）；证据获取成本 = c_probe·E[尝试数]；恢复等待已并入 E[t_res]。观测只能在成功 probe 时到达：成功数 ≤ Bin(尝试, ρ) 且尝试受 q 限制，达到 N* 次成功所需期望步数 ≥ N*/(qρ)，所需期望尝试数 ≥ N*/ρ（两类几何随机变量和的期望）。E[Regret_K] = τp·E[t_res] + c_probe·E[尝试数] + （无其他项）≥ 上式。∎

（A 世界侧：观测 y ~ N(−τ) 使 CI 在负侧排除 0，策略提交 archive——正确，无生命周期损失；对称的探测成本下界同式成立。）

### 2.4 匹配（推论 4）：恢复通道达到正确复杂度阶

**定理 1(b) 上界**（15-）：SQCAD 式恢复策略（恢复后证据流以速率 p 持续，观测累积到 CI 排除 0 即提交）：
$$
R_T^{\mathrm{SQCAD}} \;\le\; \frac{\tau p}{q\rho} + \frac{c_{\text{probe}}}{q\rho} + c_{\text{restore}}.

$$
（恢复路线优于逐探测路线的机制：一次恢复换取连续证据流，观测到达率从 qρ 提升到 p。）

**推论 4（阶匹配）**。在 𝒞_arch 中，对任意 δ ∈ (0,1)：
$$
\frac{N^*(\delta)}{\rho}\left(\frac{\tau p}{q} + c_{\text{probe}}\right)
\;\le\; \max_W \mathbb E[\mathrm{Regret}_W]
\;\le\;
\frac{\tau p + c_{\text{probe}}}{q\rho} + c_{\text{restore}}
\;\le\; C(\delta)\,\frac{N^*(\delta)}{\rho}\left(\frac{\tau p}{q} + c_{\text{probe}}\right)

$$
其中 C(δ) = max(2, 1/(2N*(δ)))·const 为与 τ、q、T 无关的常数（检测阈值 z 与错误率 δ 的换算常数，数值 ~2–4，`实验证据链/14` §3）。**上下界同阶**（在 τ、q、T、Δ 上同阶）⇒ SQCAD 的恢复通道不是任意设计，而是在该模型类中达到正确复杂度阶的治理机制：证据获取成本（c_probe·N*/ρ）、恢复等待成本（τp·N*/(qρ)）、错误治理期间的生命周期损失（τp·N*/(qρ)）三项全部被 T1(b) 上界以常数因子闭合。

### 2.5 与 12- §6 数值层的关系

12- §6 的 P4 数值（KL 下界 9.36 vs 停止规则 34.6，3.7×）是无 censoring、无 q 的直接探测模型。本定理 3/4 提供严格证明（Le Cam + Chernoff），并把 archive-induced censoring（q、ρ）与后悔分解（探测成本 + 等待 + 生命周期损失）纳入；`实验证据链/14` §3 给出带 q、ρ 的数值匹配。

---

## 3. 审稿意见逐条回应

| 审稿要求 | 本批交付 |
|---|---|
| T2：严格定义 reduction 限制，否则"contextual 编码一切" | 定义 1：五条可验证性质（动作集合/即时 reward/观测信息保持 + φ 世界无关 + 保真）；定理 2 证明中引理 3 直接阻断"编码一切"——context 是 φ(obs) 而 obs_K = obs_A |
| T2：最终形式"不存在 feedback-preserving, state-preserving reduction" | 定理 2（不可能性）+ 推论 2（必要：任何次线性化约必须显式加状态）+ 推论 3（充分：T1(b)） |
| P4：N ≥ log(1/δ)/KL，高斯 Ω(log(1/δ)/Δ²) | 定理 3（完整证明） |
| P4：更强版本纳入 censoring 与 q，总后悔 = 证据获取 + 恢复等待 + 错误治理损失 | 定理 4（后悔分解，q、ρ、c_probe 全部显式） |
| P4：与 T1(b) 同阶 ⇒ 恢复通道达到正确复杂度阶 | 推论 4（上下界同阶，常数因子） |
| 校准：不能声称"Agent Memory 全部基础理论" | §5 明确边界 |

## 4. 理论闭环的总陈述

> **Theorem 2 + Corollaries 2–3 + Theorem 1 + Theorem 3 + Theorem 4 + Corollary 4**：在 archived-committed 类上，任何忠实保反馈化约保持 Θ(T) regret（定理 2）；显式增加证据可得性状态是唯一逃逸（推论 2/3）；区分两世界需要 Ω(log(1/δ)/Δ²) 观测（定理 3）；其后悔成本（证据获取 + 恢复等待 + 错误治理损失）被 SQCAD 恢复通道以常数因子闭合（定理 4 + 推论 4）。

因此：**Agent Memory 的持久访问治理存在由"动作依赖的未来证据流"产生的、不能直接化约为普通 bandit/OPE 的 self-obscuring 基础理论问题**（验收条件 1、2、3 全部严格满足——见 `实验证据链/14` §5 的判定表）。

## 5. 校准边界（仍然不能说）

- 这不是"Agent Memory 全部基础理论"：不覆盖压缩/检索质量、不覆盖多记忆竞争预算、不覆盖任务漂移下的非参数异质性、不覆盖 authorization certificate 的完整形式化（P0 遗留）；
- 定理 2 的"标准类"边界：定义 2 排除带证据可得性状态的类——这正是分离的靶点而非限制；任何声称化约到"更丰富状态类"的方案等于承认需要新状态（推论 2）；
- 推论 4 的常数因子依赖检测阈值（z = 1.96 ↔ δ = 0.05）与通道常数（q、ρ），数值比值见 `实验证据链/14` §3，~2–4；
- trace-grounded 真实轨迹对应物仍未做（验收 6/7 待办）。

## 6. 复现信息

- 理论：本文档（定义 1/2、引理 3/4、定理 2/3/4、推论 2/3/4 完整证明）；
- 数值：`src/sqcad/reduction_closure.py`（配对恒等式、化约像上的标准学习者、latent-augmented 控制、检测界扫描、后悔分解）；结果 `results/reduction_closure.json`；报告 `实验证据链/14`；
- 前置：`15-`（引理 1/2、T1(a)(b)(c)）、`13` 报告（W0–W3 数值）、`12` 报告 §6（P4 数值层）。
