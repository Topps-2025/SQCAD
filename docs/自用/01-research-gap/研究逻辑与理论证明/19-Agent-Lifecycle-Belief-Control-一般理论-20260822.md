# Agent lifecycle belief control：一般理论与强证明底稿

> **定位。** 本文档把 SQCAD 的主理论从“逐条修补 Theorem 5 之后的受限证书”提升为一个 Agent-specific 的 belief-state control 框架。核心不是重新证明一般 POMDP 的 Bellman 方程，而是形式化持久记忆动作如何同时改变未来状态、候选暴露、证据生成和恢复通道；这些作用构成 action-dependent censoring。Theorem 1–13 在本文中作为特例、反例或 contract-level corollary，而不是并列的主线定理。

## 1. 一句话主张与边界

在具有持久外部记忆的有限时域 Agent 中，`keep/archive/probe/defer` 不只是当前检索动作，而是改变未来候选生成、有限工作区竞争和可观测证据的控制动作；因此，任何 score-based lifecycle rule 只有在完整 belief-state 上的 keep/archive action-value difference 对该 score 可测时才可能在所有阈值下最优，否则 action-dependent censoring 会产生不可由该 score 解决的反例。若 `keep` 提供 Blackwell 更强的恢复/观测实验，则其额外价值可以严格写成可恢复性价值，并与当前生命周期效用和访问成本分离。

本文只证明有限时域、已定义的潜在世界和转移/观测核下的 Bayes-optimal 结论。它不声称真实 LLM 自动满足先验、独立性、sub-Gaussian certificate 或 Blackwell 支配条件；这些是需要独立校准的实验 contract。

## 2. Agent-specific 生命周期过程

### 定义 1（持久记忆生命周期过程）

固定有限时域 $t=1,\ldots,H$。潜在世界为 $\theta\in\Theta$，它至少包含：记忆的长期任务效用、未来任务分布、候选生成机制、有限工作区中的竞争机制、暴露/采用/结果反馈机制，以及持久动作对这些机制的影响。

Agent 在时刻 $t$ 的物理状态记为

$$
s_t=(m_t,w_t,\mathcal C_t,e_t,z_t),
$$

其中 $m_t$ 是持久记忆状态（包括 scope/version），$w_t$ 是剩余工作区和存储预算，$\mathcal C_t$ 是候选池，$e_t$ 是 provenance/evidence 状态，$z_t$ 是 recoverability 状态（例如 archived 项是否仍可 probe/restore）。历史为

$$
h_t=(s_1,a_1,o_1,\ldots,s_t),\qquad
b_t(\theta)=P(\theta\mid h_t).
$$

动作空间包含 $\mathcal A=\{K,A,P,D\}$，分别表示 `keep`、`archive`、`probe` 和 `defer`。给定 $(s,\theta,a)$，一次执行同时产生下一状态和观测，其联合核写为

$$
\mathsf K_a(ds',do\mid s,\theta).
$$

该联合核必须允许 $a$ 改变未来候选和观测，而不是只改变当前 reward。即时净效用为

$$
g_\theta(s,a)=r_\theta(s,a)-\kappa(s,a),
$$

其中成本可以包含暴露、probe、存储、延迟和错误采用。

`keep/archive` 的持久性由状态转移而不是名称保证：执行后，$m_{t+1}$ 必须记录授权状态、有效 scope/version、承诺期限以及 restore/reversal cost；后续 kernel 以该状态为输入。若一个实现允许下一时刻无成本、无痕地重选动作，则它退化为普通一步 retrieval control，不属于本文的 persistent lifecycle class。

### 定义 2（行动依赖删失）

若存在 $a,a'\in\{K,A\}$、状态 $s$ 和潜在世界集合 $B\subseteq\Theta$，使得在未来某个时刻的观测/候选事件 $E$ 上

$$
P_\theta(E\mid s,a)\neq P_\theta(E\mid s,a')\quad\text{for some }\theta\in B,
$$

且该差异来自持久动作对 $\mathcal C_{t+1:H}$、$e_{t+1:H}$ 或 $z_{t+1:H}$ 的影响，则称该过程存在 **action-dependent censoring**。`archive` 可能使一部分未来证据根本无法生成，或使其只能通过付费 probe 恢复；这不是普通的 query-local missingness。

### 定义 3（生命周期 action value 与三项 continuation 分解）

令 $V_{H+1}(b,s)=0$。假设联合核可按“先产生下一物理状态、再产生该状态下的证据”分解为

$$
\mathsf K_a(ds',do\mid s,\theta)
=P_a^S(ds'\mid s,\theta)P_a^O(do\mid s',s,\theta).
$$

这里 $s'$ 包含 candidate regeneration、scope/version、workspace budget、provenance 和 recoverability 状态；$o$ 是在该状态下真正可见的 task/evidence/probe observation。记 $b^{a,s'}$ 为只使用 $s'$ 后的 Bayes posterior，记 $b^{a,s',o}$ 为再使用 $o$ 后的 posterior。对任意 belief-state $x=(b,s)$，定义

这个拆分遵循 Agent 的 canonical execution filtration：

$$
\mathcal F_t
\subset
\mathcal F_t\vee\sigma(a_t,s_{t+1})
\subset
\mathcal F_{t+1}=\mathcal F_t\vee\sigma(a_t,s_{t+1},o_{t+1}).
$$

也就是先更新持久状态并完成 candidate/workspace transition，再观察由该状态允许生成的 evidence。若把某个变量在人为表示中从 $s'$ 移到 $o$，$A_t^a$ 与 $I_t^a$ 的数值会随 filtration 改变，但二者之和 $C_t^a$ 与总 lifecycle contrast $\Delta_t$ 不变；投稿时必须按实际 Agent 执行顺序固定这一 contract。

$$
Q_t(x,a)=\ell_t(b,s,a)+\gamma C_t^a(b,s),
\qquad
\ell_t(b,s,a)=\mathbb E_{\theta\sim b}[g_\theta(s,a)],
$$

并递归定义完整 Bayes-optimal value

$$
V_t(b,s)=\max_{a\in\mathcal A}Q_t((b,s),a).
$$

其中

$$
C_t^a(b,s)=\mathbb E_{\theta\sim b,s',o\sim\mathsf K_a}
\left[V_{t+1}(b^{a,s',o},s')\right].
$$

进一步定义动作 $a$ 的 state/access continuation value 与 conditional information value：

$$
A_t^a(b,s)=\mathbb E_{\theta\sim b,s'\sim P_a^S}
\left[V_{t+1}(b^{a,s'},s')\right],
$$

$$
I_t^a(b,s)=C_t^a(b,s)-A_t^a(b,s).
$$

因此 $A_t^a$ 记录动作改变 candidate/state transition、budget competition 和未来访问机会的价值，$I_t^a$ 记录在给定 next state 后，由证据、probe 和 recoverability 实验带来的额外价值。对 keep/archive 的 lifecycle contrast 记

$$
\Delta_t(b,s)=Q_t((b,s),K)-Q_t((b,s),A).
$$

并定义

$$
\Delta_t^{\mathrm{imm}}=\ell_t(b,s,K)-\ell_t(b,s,A),
$$

$$
\Delta_t^{\mathrm{access}}=A_t^K(b,s)-A_t^A(b,s),
\qquad
\Delta_t^{\mathrm{info}}=I_t^K(b,s)-I_t^A(b,s).
$$

## 3. Lifecycle Bellman Decomposition

### 定理 A（Lifecycle Bellman Decomposition）

在定义 1 和定义 3 的可测性、有限时域、$0\le\gamma\le1$ 以及 Bayes 更新良定义条件下，对任意 $x=(b,s)$ 和任意持久动作 $a\in\{K,A\}$，有

$$
Q_t(x,a)
=\underbrace{\ell_t(b,s,a)}_{\text{即时生命周期价值}}
+\gamma\underbrace{A_t^a(b,s)}_{\text{未来访问/状态迁移价值}}
+\gamma\underbrace{I_t^a(b,s)}_{\text{未来信息/可恢复性价值}}.
$$

因此 keep 相对于 archive 的最优价值差严格满足

$$
\boxed{
\Delta_t
=\Delta_t^{\mathrm{imm}}
+\gamma\Delta_t^{\mathrm{access}}
+\gamma\Delta_t^{\mathrm{info}}
}.
$$

定义一般的 continuation value difference（不预设其符号）为

$$
\operatorname{VoR}^{\mathrm{cont}}_{t,K:A}
:=\gamma\left[C_t^K(b,s)-C_t^A(b,s)\right]
=\gamma\,\mathbb E_{\theta\sim b,(s',o)\sim\mathsf K_K(\cdot\mid s,\theta)}\left[V_{t+1}(b^{K,s',o},s')\right]
-\gamma\,\mathbb E_{\theta\sim b,(s',o)\sim\mathsf K_A(\cdot\mid s,\theta)}\left[V_{t+1}(b^{A,s',o},s')\right],
$$

则

$$
\operatorname{VoR}^{\mathrm{cont}}_{t,K:A}
=\gamma\Delta_t^{\mathrm{access}}
+\gamma\Delta_t^{\mathrm{info}}.
$$

在两动作具有共同 next-state kernel 时，定义条件 information/recoverability value

$$
\operatorname{VoR}^{\mathrm{info}}_{t,K:A}
:=\gamma\left[I_t^K(b,s)-I_t^A(b,s)\right].
$$

此时 $\operatorname{VoR}^{\mathrm{cont}}_{t,K:A}=\operatorname{VoR}^{\mathrm{info}}_{t,K:A}$。前者是完整 future-state/evidence value difference；后者才是可由 Blackwell/Jensen 单独定号的 conditional information 项。

**证明。** 由定义，$Q_t(x,a)=\ell_t(b,s,a)+\gamma C_t^a(b,s)$。对 $C_t^a$ 按 next state $s'$ 条件化，并使用 Bayes 后验的 tower property，得到

$$
C_t^a
=\mathbb E_{s'}\left[V_{t+1}(b^{a,s'},s')\right]
+\mathbb E_{s',o}\left[
V_{t+1}(b^{a,s',o},s')-V_{t+1}(b^{a,s'},s')
\right]
=A_t^a+I_t^a.
$$

代回 $Q_t$ 即得第一式；分别对 $a=K$ 和 $a=A$ 相减即得 boxed contrast decomposition。最后一式只是 $C_t^a=A_t^a+I_t^a$ 的差分。证毕。

**凸性引理。** 对有限动作、期望 reward 对 belief 仿射的有限时域控制问题，$V_t(\cdot,s)$ 是 belief 上凸函数。证明可对 horizon 反向归纳：固定任一可执行 policy tree，其从 $(b,s)$ 出发的期望总回报是 $b$ 的线性函数；$V_t$ 是所有 policy-tree 线性回报的逐点上确界，因此凸。有限动作和有限时域保证 Bellman maximum 与该上确界一致。

**信息项的基本性质。** 由于 $b^{a,s'}=\mathbb E[b^{a,s',o}\mid s']$，凸性引理和条件 Jensen 不等式给出

$$
I_t^a(b,s)\ge0.
$$

这表示每个动作自己的可见证据通常具有非负 information value；但 $\Delta_t^{\mathrm{info}}=I_t^K-I_t^A$ 可以为正、为零或为负，因为 archive 的实验也可能更有信息。Agent-specific 的问题正是：持久动作同时改变 $P_a^S$ 和 $P_a^O$，所以不能把当前采用率或 query-local gain 直接当作 $\Delta_t$。

**贡献边界。** 定理 A 的 Bellman 代数部分本身不是新贡献；可挑战现有工作的内容是三项中后两项依赖于 persistent action 改变的 candidate/state/observation kernel，并且可被定理 B–D 逐项识别或证伪。

### 推论 A.1（区间授权、probe 与 defer 是 Bellman 框架的决策投影）

设证据只识别出 keep/archive contrast 的集合

$$
\mathcal I_t=[L_t,U_t]\ni\Delta_t(b,s),
$$

并令 $Q_t^P$、$Q_t^D$ 分别为 probe 与 defer 的完整 Bellman action values（已经包含 probe cost、延迟成本和后续 continuation value）。则：

1. 若 $L_t>0$，keep 严格优于 archive；若 $U_t<0$，archive 严格优于 keep；
2. 若 $L_t\le0\le U_t$，仅由当前证据无法在 keep 与 archive 之间作 uniform dominance 结论；
3. 在跨零情形，Bayes-optimal 或 minimax-optimal 的完整动作是

$$
\arg\max_{a\in\{K,A,P,D\}}Q_t^a,
$$

而不是把任一 score 强行阈值化。特别地，只要 $Q_t^P>\max(Q_t^K,Q_t^A,Q_t^D)$，probe 是 Bayes-optimal；只要 $Q_t^D$ 最大，defer 是 Bayes-optimal。

**证明。** 对任意 $\Delta\in[L_t,U_t]$，$\Delta>0$ 意味着 $Q_t^K>Q_t^A$，$\Delta<0$ 意味着 $Q_t^A>Q_t^K$，故前两点成立。若区间跨零，则两个符号都与当前证据相容，当前证据不能给出 keep/archive 的 uniform dominance；此时四动作的最优性必须由其完整 Bellman action values 比较决定。证毕。

该推论把现有 Theorem 5–6 的 interval minimax、probe/defer 规则嵌入定理 A，而不再把某个固定 probe model 当作主理论。

## 4. Score 充分性的充要条件

### 定义 4（固定决策充分性与阈值一致充分性）

设 $\mathcal X_t$ 与 score codomain $\mathcal Z$ 均为 standard Borel 空间，给定可测 score $S_t:\mathcal X_t\to\mathcal Z$，并假设 $\Delta_t:\mathcal X_t\to\mathbb R$ 可测。若存在只依赖 $S_t(x)$ 的可测规则 $\delta_0$，能在当前成本合同下复现零阈值 Bayes 动作，即

$$
\delta_0(S_t(x))=K
\quad\Longleftrightarrow\quad
\Delta_t(x)\ge0,
$$

则称 $S_t$ **zero-action-sufficient**。进一步地，若对每个切换阈值 $\lambda\in\mathbb R$，都存在只依赖 $S_t(x)$ 的可测规则 $\delta_\lambda$，并且

$$
\delta_\lambda(S_t(x))=K
\quad\Longleftrightarrow\quad
\Delta_t(x)\ge\lambda
$$

对所有兼容 belief-state $x$ 成立。阈值可吸收存储成本、风险厌恶和错误动作惩罚；因此该定义比只对一个固定数据集调一个阈值强。

### 定理 B（Score sufficiency iff action-value measurability）

在 $\mathcal X_t$ 为标准 Borel 空间时：

1. $S_t$ zero-action-sufficient 当且仅当符号决策集合 $\{x:\Delta_t(x)\ge0\}$ 属于 $\sigma(S_t)$；等价地，最优零阈值动作在每个 score fiber 上恒定。
2. $S_t$ uniformly threshold-sufficient 当且仅当存在可测函数 $g_t$ 使

$$
\Delta_t(x)=g_t(S_t(x))\qquad\forall x\in\mathcal X_t.
$$

特别地，若存在 $x_1,x_2$ 满足 $S_t(x_1)=S_t(x_2)$ 但 $\Delta_t(x_1)\neq\Delta_t(x_2)$，则该 score 不可能在所有阈值下充分；但只要二者符号相同，它仍可能对当前零阈值动作充分。若进一步 $\Delta_t(x_1)>0>\Delta_t(x_2)$，则它连 zero-action-sufficiency 也不满足。

**证明。** 第一部分中，存在 $\delta_0$ 当且仅当 $\{\Delta_t\ge0\}$ 是 $S_t$ 的 Borel 逆像，即属于 $\sigma(S_t)$；这立即推出同一 score fiber 上的动作恒定。反过来，若 Borel keep 集合在每个 fiber 上恒定，则该集合及其补集都是 saturated sets，它们在 $S_t$ 下的像是 $\mathcal Z$ 中互不相交的 analytic sets。由 Lusin separation，存在一个 Borel score 集合将二者分开，其逆像恰是 keep 集合，故存在可测 $\delta_0$。第二部分中，若 $\Delta_t=g_t\circ S_t$，取 $\delta_\lambda(z)=K$ 当且仅当 $g_t(z)\ge\lambda$，即得充分性。反之，对每个有理数 $q$，阈值一致性意味着集合

$$
\{x:\Delta_t(x)\ge q\}=S_t^{-1}(B_q)
$$

属于 $\sigma(S_t)$。有理数阈值生成实数上的 Borel $\sigma$-代数，因此 $\Delta_t$ 是 $\sigma(S_t)$-可测函数。标准 Borel 条件下由 Doob–Dynkin 引理存在可测 $g_t$ 使 $\Delta_t=g_t\circ S_t$。最后两句分别由同一 score fiber 上函数值不同和符号相反得到。证毕。

### 推论 B.1（当前 score 的识别限制）

历史 association、query-local intervention、单次 retrieval gain 或只依赖当前候选池的分数，只有在它们对完整 belief-state 的 $\Delta_t$ 满足定理 B 的可测性条件时，才是 lifecycle governance 的充分统计量。仅证明它们与当前任务成功相关，不足以证明 keep/archive 最优。

### 推论 B.2（Agent-specific 的一个可验证充分条件）

令 $S_t$ 为一个当前 score。假设在所有属于同一 $S_t$ fiber 的 belief-state 上：

1. $P_K^S(\cdot\mid s,\theta)=P_A^S(\cdot\mid s,\theta)$，即 keep/archive 不改变未来 candidate/state transition；
2. $P_K^O(\cdot\mid s',s,\theta)=P_A^O(\cdot\mid s',s,\theta)$，即不发生 action-dependent observation censoring；
3. workspace/storage budget 不产生动作依赖的 crowding externality，或者该 externality 已被 $S_t$ 编码；
4. continuation value 对 belief 不敏感，即 $V_{t+1}(b,s')=\bar V_{t+1}(s')$，或者其对两动作的共同部分已被 $S_t$ 编码；
5. $\Delta_t^{\mathrm{imm}}(b,s)=g_t(S_t(b,s))$。

则 $\Delta_t(b,s)=g_t'(S_t(b,s))$，因此由定理 B，$S_t$ uniformly threshold-sufficient。

**证明。** 条件 1 和 3 使 $A_t^K-A_t^A$ 在同一 score fiber 内为零或成为 $S_t$ 的函数；条件 2 和 4 使 $I_t^K-I_t^A$ 为零或成为 $S_t$ 的函数。由定理 A，三项差分之和仍是 $S_t$ 的可测函数，再应用定理 B。证毕。

**必要性边界。** 推论 B.2 只是一个透明的 sufficient route，不声称四个机制条件分别都是定理 B 的逻辑必要条件。真正的必要充分条件仍是 $\Delta_t$ 对 $S_t$ 可测；例如 action-dependent kernel 在特殊对称性下可能恰好相互抵消。定理 C 给出非退化删失或 crowding 时的必然不足性条件。

### 命题 B.2a（动态 score quotient / Agent control homomorphism）

令 $X_u$ 是时刻 $u$ 的完整 post-observation belief-state 空间，动作集有限，$T_u^a(dx'\mid x)$ 是执行动作 $a$ 后、完成 state transition 和 evidence update 所诱导的下一 belief-state kernel。对每个 $u=t,\ldots,H+1$，给定 standard Borel quotient map

$$
\phi_u:X_u\to Z_u,
$$

其中 $Z_u$ 是 score-only 控制器实际保留的状态，可以包含当前 score、scope/version、workspace occupancy、candidate summary 和 recoverability flag。假设存在可测 $\bar\ell_u$ 和 quotient kernel $\bar T_u^a$，使对所有动作 $a$ 和状态 $x$：

$$
\ell_u(x,a)=\bar\ell_u(\phi_u(x),a),
$$

$$
(\phi_{u+1})_\#T_u^a(\cdot\mid x)
=\bar T_u^a(\cdot\mid\phi_u(x)).
$$

并假设终端值因子化为 $V_{H+1}=\bar V_{H+1}\circ\phi_{H+1}$。则存在可测 $\bar Q_u,\bar V_u$ 使

$$
Q_u(x,a)=\bar Q_u(\phi_u(x),a),
\qquad
V_u(x)=\bar V_u(\phi_u(x))
$$

对所有 $u=t,\ldots,H$ 成立。因此存在只依赖 quotient state 的 Bayes-optimal policy；特别地，keep/archive contrast 对 $\phi_u$ 可测，定理 B 的 uniform threshold sufficiency 成立。

**证明。** 对 $u$ 反向归纳。终端结论由假设成立。若 $V_{u+1}=\bar V_{u+1}\circ\phi_{u+1}$，则

$$
Q_u(x,a)
=\bar\ell_u(\phi_u(x),a)
+\gamma\int\bar V_{u+1}(z')\,\bar T_u^a(dz'\mid\phi_u(x)),
$$

故 $Q_u$ 只依赖 $\phi_u(x)$；对有限动作取最大值得到 $V_u$ 也只依赖 $\phi_u(x)$。证毕。

这个命题把用户所列的 Agent 条件统一成 kernel 语言：candidate/state transition、workspace/budget externality、observation/recovery channel 和 continuation belief effect 必须在 quotient 上闭合。它们不必逐项 action-independent，但任何 action dependence 都必须被 $\phi_u$ 保留。

**Universal converse.** 设 $\gamma>0$，固定 $u,a$ 和同一 fiber 中的 $x,x'$。若要求对每个有界可测 quotient terminal payoff $f:Z_{u+1}\to\mathbb R$，一步 action value

$$
\ell_u(x,a)+\gamma\int f(\phi_{u+1}(y))T_u^a(dy\mid x)
$$

都在该 fiber 上相同，则即时项必须在 fiber 上相同，且两个 push-forward 概率核必须相同。否则 standard Borel 空间上存在 Borel 集合 $B$ 区分两概率测度；取 $f=\mathbf1_B$ 即得到不同 action value。这个 converse 针对 universal action-value factorization，而不是只针对某一个固定任务的最优动作，因此不会把偶然 cancellation 误称为 kernel invariance。

### 推论 B.2b（Agent value-separating signed kernel 导致相反动作构造）

设 $\gamma>0$，$x_1,x_2$ 位于同一当前 score fiber。令下一 quotient state 上的 signed action kernel 为

$$
\nu_i
:=(\phi_{t+1})_\#T_t^K(\cdot\mid x_i)
-(\phi_{t+1})_\#T_t^A(\cdot\mid x_i),
\qquad i\in\{1,2\}.
$$

令 $\mathcal V_{t+1}$ 表示该 Agent model class 中可由后续 reward/control problem 实现的有界可测 continuation values。若存在 $v\in\mathcal V_{t+1}$ 使

$$
h_i:=\int v(z')\,\nu_i(dz'),
\qquad h_1\ne h_2,
$$

则存在一个在两个状态上相同的 immediate keep--archive contrast，使最优 persistent action 在 $x_1,x_2$ 上相反。特别地，若 model class 对所有 bounded measurable quotient terminal payoffs 闭合，则 $\nu_1\ne\nu_2$ 已足够，因为 Borel indicators 分离 standard-Borel signed measures。

**证明。** 取上述可实现 continuation value $v$，并令共同即时 contrast

$$
d=-\frac{\gamma}{2}(h_1+h_2).
$$

则一步 lifecycle contrasts 为

$$
\Delta_t(x_1)=\frac{\gamma}{2}(h_1-h_2),
\qquad
\Delta_t(x_2)=-\frac{\gamma}{2}(h_1-h_2),
$$

严格异号。证毕。

这里的 $T^K-T^A$ 同时容纳 candidate regeneration、workspace occupancy、scope/version 和 evidence/recovery 的 action-dependent 差异。推论要求这些差异能被至少一个 admissible continuation value 感知；如果所有可实现价值都对差异正交，则 kernel 虽不同却与当前任务类 decision-equivalent。该推论是 Agent model class 的存在性结论；固定论文任务是否已经跨零，仍必须由真实 $\Delta_t$ audit 判定。

### 推论 B.3（近似 score 充分性与 fiber minimax regret）

对每个 score 值 $z$，定义兼容 lifecycle contrast 的闭包区间

$$
L_t(z)=\inf_{x:S_t(x)=z}\Delta_t(x),
\qquad
U_t(z)=\sup_{x:S_t(x)=z}\Delta_t(x),
$$

并假设 $L_t,U_t$ 有限且可测。若 $L_t(z)\ge0$，该 fiber 上统一选择 keep 的 regret 为零；若 $U_t(z)\le0$，统一选择 archive 的 regret 为零；特别地，$L_t(z)=U_t(z)=0$ 时任意混合动作的 regret 都为零。对真正跨零的 fiber $L_t(z)<0<U_t(z)$，只观察 $z$ 的随机规则以概率

$$
p_t^*(z)=\frac{U_t(z)}{U_t(z)-L_t(z)}
$$

选择 keep，可达到 fiber 上的 minimax action regret

$$
R_t^*(z)
=\frac{U_t(z)(-L_t(z))}{U_t(z)-L_t(z)}
\le\frac{U_t(z)-L_t(z)}{4}.
$$

因此若所有 score fiber 的 lifecycle contrast 振幅至多为 $\varepsilon$，即

$$
\sup_z\{U_t(z)-L_t(z)\}\le\varepsilon,
$$

则存在 score-only 随机规则，其全局最坏 action regret 至多为 $\varepsilon/4$。精确可测性是 $\varepsilon=0$ 的特例；旧 Theorem 5–6 的 interval minimax rule 是单个 fiber 的特例。

**证明。** 真正跨零的 fiber 上，以概率 $p$ 选择 keep 时，正端点 $U$ 的 regret 为 $(1-p)U$，负端点 $L$ 的 regret 为 $p(-L)$；任意区间内部点的 regret 不超过对应端点。令两端 regret 相等得到 $p^*=U/(U-L)$ 及 $R^*=U(-L)/(U-L)$。令 $a=U>0$、$b=-L>0$，则 $ab/(a+b)\le(a+b)/4$，得振幅上界。非跨零和零宽度 tie 情形由确定性选择或任意混合直接得到零 regret。证毕。

## 5. Action-dependent censoring 的不足性定理

### 定义 5（删失诱导的 Jensen gap）

令 $\mathcal E_a(x)$ 表示在动作 $a$ 下从 $x$ 到下一次可决策 belief-state 的实验，并定义完整 future-kernel gap

$$
J_t(x)=C_t^K(b,s)-C_t^A(b,s)
=\Delta_t^{\mathrm{access}}(b,s)+\Delta_t^{\mathrm{info}}(b,s).
$$

当 archive 把 keep 下的未来证据映射为常数或更粗的观测时，$\Delta_t^{\mathrm{info}}$ 是删失造成的信息差；若 keep 还改变候选再生和工作区竞争，则 $\Delta_t^{\mathrm{access}}$ 记录相应的状态/访问差。$J_t$ 是二者的总 future-kernel gap，而不是把所有差异都称为信息价值。

### 定理 C（删失导致 score 不足的可检验条件）

设 $S_t$ 是任意当前治理 score，并把决策问题限制为二动作集合 $\{K,A\}$。若存在两个兼容的 belief-state $x_1,x_2$，满足：

1. $S_t(x_1)=S_t(x_2)$；
2. 即时差 $\Delta_t^{\mathrm{imm}}(x_1)=\Delta_t^{\mathrm{imm}}(x_2)=d$；
3. 两个状态的删失 gap 不同，$J_t(x_1)\ne J_t(x_2)$；
4. 差异来自未来候选、证据或恢复核，并且这些核的相关状态未被 $S_t$ 编码；形式上，$x_1,x_2$ 位于同一个 $S_t$ fiber，但 $\mathsf K_K(\cdot\mid x_i)$ 与 $\mathsf K_A(\cdot\mid x_i)$ 的 continuation-value 差异不同。

则 $\Delta_t(x_1)\ne\Delta_t(x_2)$，故由定理 B，$S_t$ 不是 uniformly threshold-sufficient。若

$$
d+\gamma J_t(x_1)>0>d+\gamma J_t(x_2),
$$

则不存在任何只看 $S_t$ 的零阈值确定性规则能在这两个状态上同时最优；任意随机规则在至少一个状态上也有严格正的 action regret。

**证明。** 由定理 A 和定义 5，$\Delta_t(x_i)=d+\gamma J_t(x_i)$。由第 3 条，两值不同，先得 score 不足。若符号相反，零阈值最优动作相反，而两状态给出相同 score，因此确定性 score-only 规则至少错一个状态。设该规则以 keep 的概率为 $p$；两状态的期望 action regret 分别为

$$
(1-p)\,|\Delta_t(x_1)|,\qquad p\,|\Delta_t(x_2)|,
$$

其在这两个状态上的最大值至少为

$$
\frac{|\Delta_t(x_1)|\,|\Delta_t(x_2)|}
 {|\Delta_t(x_1)|+|\Delta_t(x_2)|}>0.
$$

证毕。

**显式 Agent 反例。** 取 $\gamma>0$、$\Theta=\{-1,+1\}$，下一步任务奖励为 $R\max\{b,1-b\}$。在 $x_1$，`keep` 以概率 $1$ 暴露一个完全识别 $\theta$ 的未来证据，`archive` 只给常数观测；于是 $J_t(x_1)=R/2$。在 $x_2$，有限工作区或 scope mismatch 使两动作都只能给常数观测，于是 $J_t(x_2)=0$。令当前 score 对两个状态均为 $s_0$，即时差 $d=-\gamma R/4$，则

$$
\Delta_t(x_1)=\gamma R/4>0,\qquad
\Delta_t(x_2)=-\gamma R/4<0.
$$

该构造只使用 Agent 的未来候选暴露/恢复差异；若把未来观测核固定为 action-independent，$J_t$ 的这一来源消失，反例也不再成立。

### 推论 C.1（从 score-fiber 反例到 least-favorable Bayes 下界）

在定理 C 的符号反转条件下，记

$$
d_1=\Delta_t(x_1)>0,\qquad d_2=-\Delta_t(x_2)>0.
$$

在只观察到共同 score $S_t(x_1)=S_t(x_2)$ 的策略类中，取两点先验

$$
\pi^*(x_1)=\frac{d_2}{d_1+d_2},\qquad
\pi^*(x_2)=\frac{d_1}{d_1+d_2}.
$$

则任意 score-only 随机规则（以概率 $p$ 选择 `keep`）的 Bayes action regret 满足

$$
\mathbb E_{\pi^*}[\operatorname{Regret}_t]
\ge \frac{d_1d_2}{d_1+d_2}.
$$

该下界等于两个状态上 minimax regret 的值；因此引入一个未被证据识别的 Bayesian prior 不会修复 score insufficiency。先验只是在不可识别 fiber 内选择风险权重，不能创造缺失的 action-value information。

**证明。** 规则在 $x_1$ 上以概率 $1-p$ 选错，在 $x_2$ 上以概率 $p$ 选错，故

$$
R_{\pi^*}(p)=\pi^*(x_1)(1-p)d_1+\pi^*(x_2)p d_2
=\frac{d_1d_2}{d_1+d_2}
$$

对所有 $p\in[0,1]$ 恒成立。另一方面，定理 C 中的两状态最大 regret 的最小值由令 $(1-p)d_1=pd_2$ 得到，同样为 $d_1d_2/(d_1+d_2)$。证毕。

**解释。** 推论 C.1 是一个 Bayes-to-minimax bridge，而不是把先验当成答案来源：$\pi^*$ 在看到 score-only 策略前固定，只使用两个兼容状态的 action-value gap；它可作为 challenge 现有工作的 least-favorable prior。若允许完整 belief-state 或额外 probe，$x_1,x_2$ 的 fiber 会被拆开，下界不再针对扩展后的策略类成立。

## 6. 可恢复性价值与 Blackwell 支配

### 定义 6（条件 Blackwell 支配）

固定 $(b,s)$。假设两动作的 state kernel 相同：

$$
P_K^S(ds'\mid s,\theta)=P_A^S(ds'\mid s,\theta)
\quad\text{for $b$-almost every $\theta$},
$$

从而诱导相同的 next-state marginal $\mu(ds'\mid b,s)$ 和相同的 state-level posterior $b^{K,s'}=b^{A,s'}$。在此条件下，称 `keep` 的 conditional experiment $\mathcal E_K^{s'}$ Blackwell 支配 `archive` 的 conditional experiment $\mathcal E_A^{s'}$，若对 $\mu$-几乎处处的 $s'$，存在不依赖 $\theta$ 的 garbling kernel $G_{s'}$，使

$$
P_A^O(do\mid s',s,\theta)
=\int G_{s'}(do\mid z,s)P_K^O(dz\mid s',s,\theta).
$$

这表示 archived 轨迹得到的证据可由 kept 轨迹的证据后处理得到；反方向不一定成立。若 archive 后执行付费 probe，则把 probe 结果并入 archive 侧的观测 $O$，并在实际发生时把价格记入 Bellman cost ledger；此时 Blackwell 支配可能成立，也可能因 probe 足够强而不成立。定义 6 只比较 conditional information experiment；candidate regeneration、scope/version 和 workspace crowding 若不同，应由定理 A 的 $\Delta^{\mathrm{access}}$ 单独计入，而不能偷换成 Blackwell 信息价值。

### 定理 D（可恢复性：价值单调性与信息预算必要性）

**(a) 条件信息价值。**

假设：

1. `keep` 和 `archive` 的 state kernel 在 $\theta$ 上相同，或已经条件化到具有相同 state-level posterior 的同一个 $s'$；
2. 对该 $s'$，$\mathcal E_K^{s'}$ Blackwell 支配 $\mathcal E_A^{s'}$；
3. $V_{t+1}(b,s')$ 对 $b$ 凸。有限动作、期望 reward 对 $b$ 仿射时，该凸性由有限时域归纳自动成立。

则

$$
\Delta_t^{\mathrm{info}}(b,s)=I_t^K(b,s)-I_t^A(b,s)\ge0,
\qquad
\operatorname{VoR}^{\mathrm{info}}_{t,K:A}
=\gamma\Delta_t^{\mathrm{info}}(b,s)\ge0.
$$

若还满足 $\gamma>0$，并存在一组正概率的 next-state/观测分支，使 archive 后验是 keep 后验的非平凡条件平均，并出现严格 conditional Jensen gap：

$$
\operatorname{E}\left[V_{t+1}(b_Z^K,s')\mid O=o\right]
>
V_{t+1}\left(\operatorname{E}[b_Z^K\mid O=o],s'\right),
$$

则

$$
\operatorname{VoR}^{\mathrm{info}}_{t,K:A}>0.
$$

有限时域、有限 POMDP 中，每个固定 continuation policy tree 的值对 belief 仿射，最优值是这些仿射函数的逐点最大值。此时一个透明的严格性充分条件是：keep posterior 的条件 support 跨越不同 continuation-policy regions，不存在同一个 continuation policy 在该 support 上几乎处处同时最优。定理 D 只确定信息项的符号，不单独决定总动作。即时效用、probe/storage/exposure cost 以及有限工作区产生的 $\Delta_t^{\mathrm{access}}$ 仍按定理 A 相加；付费 restore/probe 的成本在实际发生时进入 Bellman reward/cost ledger，不能吸收到 Blackwell experiment ordering 中。

**(a) 的证明。** 固定一个满足条件的 $s'$，设 $Z$ 为 keep 观测，$O=G_{s'}(Z)$ 为 archive 观测。对每个 archive 观测 $o$，Bayes 后验满足

$$b^A_o=\mathbb E[b^K_Z\mid O=o].$$

由 $V_{t+1}(\cdot,s')$ 的凸性和条件 Jensen 不等式，

$$V_{t+1}(b^A_o,s')\le \mathbb E[V_{t+1}(b^K_Z,s')\mid O=o].$$

对 $o$ 积分并再对 $s'\sim\mu$ 积分，得到 $I_t^K\ge I_t^A$，即上述非负性。若存在正 $\mu$-概率的 $s'$ 和正概率的严格 Jensen 分支，积分后严格大于。最后把即时 reward、访问/拥挤项和显式 probe/storage cost 加回定理 A 的分解即可。证毕。

**(b) 可恢复信息预算下界。** 考虑任意自适应 lifecycle policy $\pi$。它可以在授权前执行 `probe/defer` 或其他允许的诊断动作，并在 canonical filtration $\{\mathcal F_u\}$ 的 stopping time $\tau\le H$ 输出持久授权 $D\in\{K,A\}$。令 $R_\tau(\pi)$ 表示该授权的终端动作后悔，即在剩余生命周期上，较优持久动作与实际输出动作 $D$ 之间的价值差。取两个具有相同决策前历史（因而没有 initial-history KL）的 Agent 世界 $M_+$、$M_-$；它们尤其具有相同当前 score。假设在每个具有正概率的授权历史上，$M_+$ 中错误 archive 的 action regret 至少为 $d_+>0$，$M_-$ 中错误 keep 的 action regret 至少为 $d_->0$。

对 $u<\tau$，令 $A_u$ 是策略选择的诊断动作，$W_{u+1}$ 是该动作后实际观察到的完整增量，包括 candidate、state transition、probe 或 restore 结果。定义随机长度 transcript

$$
Y_\tau=(A_0,W_1,\ldots,A_{\tau-1},W_\tau,\tau),
$$

并令 $T_\tau=(Y_\tau,D)$。动作选择、随机停止和终端授权都由两世界共享的 policy kernels 产生；环境差异只进入 $W_{u+1}$ 的 action-dependent kernel。把 $\tau$ 后的 action/observation slots 用与世界无关的 absorbing symbol $\dagger$ 补齐，即得到固定时域、$\mathcal F_H$-可测的 augmented transcript。两世界使用同一个 terminal decision kernel $\pi(D\mid Y_\tau)$，故 $T_\tau$ 与 $Y_\tau$ 的两世界 KL 相同。令 $\mathbb P_+^\pi$、$\mathbb P_-^\pi$ 表示该 padded augmented transcript 的分布，并定义

$$
B_\pi=\operatorname{KL}(\mathbb P_+^\pi\Vert\mathbb P_-^\pi).
$$

则任意策略都满足

$$
\boxed{
\max\left\{\mathbb E_+R_\tau(\pi),\mathbb E_-R_\tau(\pi)\right\}
\ge
\frac{d_+d_-}{2(d_++d_-)}e^{-B_\pi}
}.
$$

若 $\mathbb P_+^\pi\ll\mathbb P_-^\pi$，且两世界运行同一个 adaptive policy，使 action-selection kernel 本身相同，则相对熵 chain rule 给出

$$
B_\pi
=\mathbb E_+^\pi\left[
\sum_{u<\tau}
\operatorname{KL}\left(
\mathsf K_{A_u,+}(\cdot\mid H_u)
\Vert
\mathsf K_{A_u,-}(\cdot\mid H_u)
\right)
\right].
$$

因此，若 archived 状态在 probe 前完全删失区分两世界的事件，则这些 archived/defer 时段的 conditional KL 为零。若每次临时 keep/exposure 最多提供 $\kappa_K$ KL、每次 probe 最多提供 $\kappa_P$ KL，且其余授权前动作的 conditional KL 为零，则

$$
B_\pi\le
\kappa_K\mathbb E_+N_K+
\kappa_P\mathbb E_+N_P.
$$

在对称 gap $d_+=d_-=d$ 下，下界化为 $de^{-B_\pi}/4$。若错误持久授权会在之后 $L$ 个任务中造成每步至少 $\nu$ 的损失，则 $d\ge\nu L$；只要可恢复 transcript 的 KL 预算保持有界，最坏 lifecycle regret 就是 $\Omega(L)$。反过来，对 $0<r<d_+d_-/[2(d_++d_-)]$，要把上述下界压到 $r$ 以下，必要条件是

$$
B_\pi\ge
\log\frac{d_+d_-}{2r(d_++d_-)}.
$$

**(b) 的证明。** 由于 $D$ 被纳入 augmented transcript，$E=\{D=A\}$ 是其可测事件。对两分布应用 Bretagnolle--Huber 不等式：

$$
\mathbb P_+^\pi(E)+\mathbb P_-^\pi(E^c)
\ge \frac12e^{-B_\pi}.
$$

左侧两项恰是 $M_+$ 与 $M_-$ 中的授权错误概率；由统一的 branchwise gap 假设，其 regret 分别至少为 $d_+\mathbb P_+^\pi(E)$ 和 $d_-\mathbb P_-^\pi(E^c)$。在两错误概率之和固定时，令两个加权 regret 相等可使最大值最小，从而得到 boxed 下界。对补齐后的固定时域 transcript 使用 KL chain rule：共同 initial history 提供零 KL；同一策略在两世界的诊断 action-selection、随机 stop/continue 与 terminal decision factors 都相消；停止后的 absorbing factors 也提供零 KL。因而只剩 $u<\tau$ 时实际 action-dependent transition/observation kernel 的 conditional KL；逐动作应用 $\kappa_K,\kappa_P$ 上界即得预算式。若初始历史分布不同，右侧必须另加它们的 KL；若绝对连续性不成立，则 $B_\pi=+\infty$，下界仍成立但退化为零。证毕。

**Agent-specific 含义。** (a) 不说 keep 总是正确，它只在共同 state kernel 下隔离“可恢复性/信息”这一项的符号；(b) 不要求共同 state kernel，而是直接对完整 action-dependent Agent transcript 计量信息。两者合在一起给出价值和必要性两面：Blackwell 更强的恢复实验有非负 option value，但一旦持久 archive 删失区分性事件，Bayesian prior 不会自行产生信息，策略必须用 exposure/probe/restore 购买足够 KL，或者承担显式 regret floor。实际动作应比较 $\Delta_t^{\mathrm{imm}}+\operatorname{VoR}^{\mathrm{cont}}_{t,K:A}$；在共同 state kernel 下，这等于 $\Delta_t^{\mathrm{imm}}+\operatorname{VoR}^{\mathrm{info}}_{t,K:A}$。存储、crowding 和错误采用成本不得遗漏。

### 推论 D.1（信息/可恢复性价值可以推翻即时 archive 优势）

在定理 D 的共同 state-kernel 条件下，若 archive 的即时净效用更高，即

$$
\Delta_t^{\mathrm{imm}}<0,
$$

但

$$
\gamma\Delta_t^{\mathrm{info}}
>-\Delta_t^{\mathrm{imm}},
$$

则 $\Delta_t>0$，所以 keep 仍是二动作问题中的 Bayes-optimal persistent action。更一般地，若 keep 还承受负的 access/crowding 项，则充分条件为

$$
\gamma\left(\Delta_t^{\mathrm{access}}+\Delta_t^{\mathrm{info}}\right)
>-\Delta_t^{\mathrm{imm}}.
$$

这精确表达了“当前不采用或当前存储成本更低”不能推出“长期应 archive”。

### 推论 D.2（付费 probe/defer 的 Bayes 阈值）

考虑一个不改变当前物理状态、成本为 $c_P>0$ 的 probe，观测 $Z$ 后在下一决策点重新选择动作。记

$$
\operatorname{EVI}_t(P)
=\mathbb E_Z[V_{t+1}(b^Z,s)]-V_{t+1}(b,s).
$$

若 probe 的 Bellman value 为

$$
Q_t^P=-c_P+\gamma\mathbb E_Z[V_{t+1}(b^Z,s)],
$$

而不 probe 的可逆 defer value 为 $Q_t^D=\gamma V_{t+1}(b,s)$，则

$$
Q_t^P>Q_t^D
\quad\Longleftrightarrow\quad
\gamma\operatorname{EVI}_t(P)>c_P.
$$

若进一步 $Q_t^P>\max\{Q_t^K,Q_t^A\}$，则 probe 在四动作问题中严格 Bayes-optimal；若 probe 太贵但 $Q_t^D>\max\{Q_t^K,Q_t^A\}$，则 defer 严格 Bayes-optimal。证明由四个 Bellman action values 直接相减得到。该推论只要求 probe 的后验实验和成本可定义；Theorem 11–13 的 Gaussian/sub-Gaussian certificate 是它的一个受限可计算实例。

### 推论 D.3（Priced recoverability frontier）

沿用定理 D(b)，记

$$
\alpha:=\frac{d_+d_-}{2(d_++d_-)}.
$$

设所有能够重新打开区分通道的授权前动作总次数为 $N$；每次动作的 conditional KL 至多为 $\kappa>0$，直接诊断成本至少为 $c>0$，其余动作 conditional KL 为零。定义相对于“知道正确世界并立即授权”的总授权损失

$$
\widetilde R_\tau(\pi)=R_\tau(\pi)+C_\tau(\pi),
$$

其中 $C_\tau$ 是授权前累计诊断成本。令 $n=\mathbb E_+N$。则

$$
\max_{w\in\{+,-\}}\mathbb E_w\widetilde R_\tau(\pi)
\ge
\max\left\{cn,\alpha e^{-\kappa n}\right\}
\ge
\frac{c}{\kappa}
W_0\!\left(\frac{\kappa\alpha}{c}\right),
$$

其中 $W_0$ 是 principal Lambert-$W$ branch。等价地，若要使最坏总授权损失不超过 $r<\alpha$，必要条件同时包括

$$
n\ge\frac1\kappa\log\frac{\alpha}{r},
\qquad
cn\le r,
$$

因而必须有

$$
\frac{c}{\kappa}\log\frac{\alpha}{r}\le r.
$$

**证明。** 由定理 D(b) 和 $B_\pi\le\kappa n$，最坏世界的 terminal authorization regret 至少为 $\alpha e^{-\kappa n}$。另一方面，$M_+$ 中的期望诊断成本至少为 $cn$，故最坏总损失同时不小于 $cn$ 和前述 terminal-regret 下界。对 $n\ge0$ 最小化两者最大值时，最优交点满足 $cn=\alpha e^{-\kappa n}$；令 $x=\kappa n$，得到 $xe^x=\kappa\alpha/c$，从而得到 Lambert-$W$ 闭式。目标 $r$ 的必要条件由两个分量分别不超过 $r$ 直接得到。证毕。

这个推论把“恢复有价值”推进为 Agent-specific 的 no-free-recovery 结论：持久 archive 若使非探测分支失去区分信息，策略只能支付 channel-opening 成本，或保留一个不可消除的错误授权项。它不是一般 Bayesian uncertainty 的新定理；特殊性来自 Agent 授权内生地决定后续哪些 transcript 分支携带 KL，以及恢复动作具有显式执行价格。

## 7. 架构无关的生命周期三分定理与最小充分统计量

前述定理使用 belief-state 表示，但最终决策对象可以脱离 external、retrieval、prompt、cache 或 parameterized memory 的具体实现。令 $\mathcal Z$ 为 standard-Borel 任务空间，$\Omega$ 为完整未来 Agent transcript 空间；transcript 可包含未来 query、检索结果、LLM 输出、tool call、memory update、环境状态和任务结果。对 $a\in\{K,A\}$，定义干预后的未来 transcript law：

$$
P^a(dy\mid x,z)
:=\mathcal L(Y_{t:H}\in dy\mid x,\operatorname{do}(a),z).
$$

该干预必须具有明确、持久的执行语义。若某个不可变模型参数不存在 retain/suppress/update 的反事实接口，它不属于本定理的 keep/archive 动作；若 adapter、cache 或参数化记忆存在该接口，则与外部记忆使用同一定理。定义 signed future-transcript kernel：

$$
\nu_{x,z}
:=P^K(\cdot\mid x,z)-P^A(\cdot\mid x,z).
$$

对有界可测任务效用 $u:\Omega\to\mathbb R$ 和 $0<\gamma\le1$，生命周期 contrast 为

$$
\Delta_{z,u}(x)
=d_z(x)+\gamma\int_\Omega u(y)\,\nu_{x,z}(dy),
$$

其中 $d_z(x)$ 是即时 keep--archive contrast。为把 future-memory insufficiency 与普通的当前成本遗漏分开，假设即时 contrast 已被 score 编码：

$$
d_z(x)=\bar d(S(x),z).
$$

同时假设 $S$ 是 regular standard-Borel quotient：任何有界可测且在 $S$ fiber 上恒定的函数都能可测地通过 $S$ 因子化。有限/可数审计直接满足该条件。

对每个任务 $z$，令 $\mathcal U_z$ 是包含零效用的、统一有界的可测 transcript utility class，即存在声明的 $U_{\max}<\infty$ 使 $\sup_{z,u\in\mathcal U_z}\lVert u\rVert_\infty\le U_{\max}$。若对所有相关 signed kernels $\nu\ne\nu'$ 都有

$$
\exists u\in\mathcal U_z:
\int u\,d\nu\ne\int u\,d\nu',
$$

则称 $\mathcal U_z$ 对 Agent kernels **具有分离性**。有界 Borel utilities 的单位球由 indicator separation 自动具有分离性；自然任务类可能不具有，因此必须显式声明任务边界。统一包络固定了效用尺度，避免后文 $\varepsilon_{\mathrm{LC}}$ 仅因任意放大 $u$ 而发散；包含零效用则保证最小性证明可以单独识别即时项 $d_z$。

### 定理 E（Architecture-agnostic lifecycle trichotomy）

对任意具有上述干预语义的 LLM-Agent memory 和治理 score $S$，以下三种情况恰有一种成立：

1. **Future-null memory。** 对所有 $x,z$，$\nu_{x,z}=0$。keep/archive 的未来 transcript law 完全相同，因此对所有 $u$，$\Delta_{z,u}(x)=d_z(x)$；问题退化为即时成本治理。
2. **Non-null but lifecycle-complete score。** 至少一个 $\nu_{x,z}\ne0$，且对所有任务和同 score 状态，

   $$
   S(x_1)=S(x_2)
   \Longrightarrow
   \nu_{x_1,z}=\nu_{x_2,z}.
   $$

   此时对每个 $z,u$ 都存在可测 $g_{z,u}$ 使 $\Delta_{z,u}=g_{z,u}\circ S$，所以 score 对声明任务类和所有标量 cost shifts 统一充分。
3. **Non-null and future-lossy score。** 存在 $x_1,x_2,z$ 使

   $$
   S(x_1)=S(x_2),
   \qquad
   \nu_{x_1,z}\ne\nu_{x_2,z}.
   $$

   若 $\mathcal U_z$ 能分离这两个 kernels，则存在 $u\in\mathcal U_z$ 使两个 lifecycle values 不同。施加共同标量 cost shift

   $$
   \lambda^*
   :=\frac{\Delta_{z,u}(x_1)+\Delta_{z,u}(x_2)}{2}
   $$

   后，两状态的 contrast 严格异号，任意 score-only 随机规则的两状态最坏 regret 至少为

   $$
   \boxed{
   \frac14
   \left|\Delta_{z,u}(x_1)-\Delta_{z,u}(x_2)\right|
   =
   \frac{\gamma}{4}
   \left|
   \int u\,d(\nu_{x_1,z}-\nu_{x_2,z})
   \right|
   >0
   }.
   $$

   若未平移的两个 contrasts 已经异号，则原 fixed-cost contract 下直接得到同一结论。

**证明。** 若所有 $\nu_{x,z}$ 为零，得到分支 1。否则 memory channel 非空；此时 signed kernel 要么在所有 score fibers 和任务上恒定，得到分支 2，要么存在违反恒定性的 $x_1,x_2,z$，得到分支 3。因此三分穷尽且互斥。

分支 1 由 contrast 定义直接得到。分支 2 中，kernel fiber constancy、regular quotient 与即时项的 score factorization 共同推出 $\Delta_{z,u}$ 对 $S$ 可测；应用定理 B 得统一阈值充分性。分支 3 中，分离性给出 $u$ 使

$$
q_i:=\int u\,d\nu_{x_i,z},
\qquad q_1\ne q_2.
$$

同 score 状态的即时 contrast 相同，故

$$
\Delta_{z,u}(x_1)-\Delta_{z,u}(x_2)
=\gamma(q_1-q_2)\ne0.
$$

减去 midpoint $\lambda^*$ 后，两个 gap 为 $g$ 与 $-g$，其中 $g=|\Delta_{z,u}(x_1)-\Delta_{z,u}(x_2)|/2$。定理 B 的二状态 minimax 计算在对称 gap 下给出 $g/2$，即 boxed 下界。证毕。

该定理没有声称每个 LLM 都读取每条 memory，也没有声称每个自然任务都能感知所有 transcript 差异。它给出更严格的全架构结论：任何声称 task-universal 的 memory score，要么治理的是 future-null channel，要么必须保存完整的 task-relevant signed future-transcript kernel；除此之外必然存在失败任务/成本条件。

### 推论 E.1（Task drift 不是必要条件，但扩大 challenge class）

若未来任务 $z\sim\mu$，并使用联合可测的任务效用选择 $z\mapsto u_z$，则

$$
\Delta_\mu(x)
=\int_{\mathcal Z}
\left[
d_z(x)+\gamma\int_\Omega u_z(y)\,\nu_{x,z}(dy)
\right]\mu(dz).
$$

若允许的 drift family 包含所有 point masses $\delta_z$，则对全部 $\mu$ 的 score 充分性蕴含对每个任务 $z$ 的逐点充分性；反之，若逐点 contrast 能联合可测地通过 $(S,z)$ 因子化，则其对任意 $\mu$ 的积分也因子化。分支 3 的固定任务 witness 可取 $\mu=\delta_z$，因此 task drift 会扩大可能失败的任务类，但固定专用 Agent 同样可能落入分支 3。

### 定义 7（Lifecycle sufficient statistic）

定义 task-relative lifecycle equivalence：

$$
\begin{aligned}
x\equiv_{\mathrm{LC}}x'
\quad\Longleftrightarrow\quad
&d_z(x)=d_z(x')\\
&\text{且 }\int u\,d\nu_{x,z}=\int u\,d\nu_{x',z}
\quad\text{对所有 }z\text{ 和 }u\in\mathcal U_z.
\end{aligned}
$$

定义 partition-order 意义下最小的 task-relative lifecycle sufficient information object：

$$
T_{\mathrm{LC}}^*(x):=[x]_{\equiv_{\mathrm{LC}}}.
$$

任何对全部声明任务效用和标量 cost shifts 充分的统计量 $T$ 都必须细化这一 partition：

$$
T(x)=T(x')
\Longrightarrow
x\equiv_{\mathrm{LC}}x'.
$$

**证明。** lifecycle-equivalent 状态在所有 $z,u$ 下具有相同 contrast，所以 quotient statistic 充分。若某个充分统计量合并了违反 equivalence 的状态，则即时项或某个允许 utility 会分离两状态的 action value；在二者 midpoint 施加共同 cost shift 后得到相反动作，与 uniform sufficiency 矛盾。证毕。

等价地，可使用坐标映射

$$
\Phi_{\mathrm{LC}}(x)
:=
\left(
(d_z(x))_{z\in\mathcal Z},
\left(\int u\,d\nu_{x,z}\right)_{z\in\mathcal Z,\,u\in\mathcal U_z}
\right),
$$

其 codomain 取 product sigma-field，且 fibers 恰好等于上述 equivalence classes。因此 $T_{\mathrm{LC}}^*$ 总能作为可测信息 partition 理解，但 quotient 本身不必自动是 standard Borel。只有当该 equivalence relation 是 smooth 的，例如存在可数 determining task/utility subfamilies 生成同一 fibers 时，才能保证存在 standard-Borel controller-state representation。后续算法必须估计这样的 regular representation 或近似，而不能把抽象 quotient 直接当成有限维特征。

当 $\mathcal U_z$ 包含有界 Borel utilities 的单位球时，上述 equivalence 等价于对每个任务同时保持 $d_z$ 和完整 signed kernel $\nu_{x,z}$。当自然任务类更小时，框架不需要估计无限维完整分布，而应估计该 utility class 能感知的 kernel quotient。

对近似统计量 $T$，定义 lifecycle oscillation：

$$
\varepsilon_{\mathrm{LC}}(T)
:=
\sup_{T(x)=T(x')}
\sup_{z,\,u\in\mathcal U_z}
\left|\Delta_{z,u}(x)-\Delta_{z,u}(x')\right|.
$$

在 fiber endpoints 有限且可测时，对每个已观测任务与成本合同，推论 B.3 给出最坏 action regret 不超过 $\varepsilon_{\mathrm{LC}}(T)/4$ 的 fiber-wise 随机规则。该界是逐任务、逐成本合同的；除非任务 $z$ 是控制器输入，不能把它误写成同一个随机规则同时覆盖所有任务。因此，后续 SQCAD 创新框架真正需要估计和压缩的对象不是 current retrieval relevance，而是 $T_{\mathrm{LC}}^*$ 或其可审计近似，并直接最小化 $\varepsilon_{\mathrm{LC}}$。这不是“标量一定不够”的维数论断：若存在 smooth standard-Borel representation，理论上可以把它单射编码为实数；真正需要检验的是现有 score 是否携带了这种信息。

## 8. 与现有 Theorem 1–13 的嵌入关系

### 三条基础定理与一个总括定理的创新债务

| 主结果 | 标准数学成分 | 本文必须承担的新内容 | 不能声称 |
|---|---|---|---|
| 定理 A | belief-MDP Bellman recursion、tower property | 把 persistent memory 的 candidate/workspace transition 与 action-dependent evidence experiment 放入同一 lifecycle contrast，并按真实 Agent filtration 分成 immediate/access/information 三项 | “发明了 Bellman equation” |
| 定理 B | Doob–Dynkin 可测性刻画 | 把现有 memory score 的充分性转化为对 lifecycle action-value difference 的可证伪条件，并连接 action-dependent kernel | “任意标量 score 都不可能充分” |
| 定理 D | Blackwell dominance、conditional Jensen、Bretagnolle--Huber、adaptive KL chain rule、Lambert-$W$ 优化 | 一方面把 recovery experiment 的 option value 与 candidate crowding/访问项分账；另一方面对一般 action-dependent Agent transcript 证明信息预算不足时的持久授权 regret floor，并把 channel-opening KL 与显式恢复成本合并为 priced frontier | “Blackwell/VOI/KL/Lambert-$W$ 工具本身是本文原创” |
| 定理 E | measure separation、Doob--Dynkin/quotient factorization、两点 minimax | 对所有 intervention-defined LLM-Agent memory 架构给出 future-null / lifecycle-complete / future-lossy 三分，并定义后续框架必须估计的最小 task-relative lifecycle information partition | “所有 LLM Agent、所有自然任务都必然失败” |

因此真正能被 ICLR reviewer 认可的理论贡献不是标准工具各自存在，而是它们在 Agent memory lifecycle 中形成一个闭合论证：定理 A 指出遗漏项，定理 B 给出 score-only 方法成立的必要充分条件，定理 C/C.1 给出忽略 Agent kernel 时的反例与 regret 下界，定理 D(a) 给出恢复实验的价值符号与严格性条件，定理 D(b) 进一步证明一般 adaptive policy 必须从 action-dependent transcript 获得足够 KL 才能消除错误授权下界，A.1/D.2 再把 SQCAD 的 probe/defer rule 嵌回一般控制问题。

| 现有结果 | 在一般框架中的位置 | 可保留的严格表述 |
|---|---|---|
| Theorem 1 | 定理 B 的 prior-free 观测等价反例 | 同一可观测 log 可对应不同 $\Delta_t$，所以 log-measurable rule 不能识别动作 |
| Theorem 2 | 定理 B/C 的固定 score fiber 反例 | query-local effect 相同不推出 lifecycle value 相同 |
| Theorem 3 | 定理 C 的 horizon-special case | archive 使未来候选/证据自我删失，承诺且无恢复通道时产生线性损失 |
| Theorem 4 | 更大框架的 restricted faithful reduction | 只覆盖 fully censored、no-restore committed subclass，不是任意 Agent policy 的 separation |
| Theorem 5–6 | belief-state 部分识别与阈值决策的有限类推论 | 区间跨零时 defer/probe 的 minimax 决策；不能替代一般 Bayes control |
| Theorem 7–8 | 二点 Gaussian/Bernoulli probe 子类的诊断 | 固定阈值检测与特定 regret 分解，不是全 sequential policy 的复杂度定理 |
| Theorem 9–10 | score/certificate 可测性成立时的充分性 corollary | honest interval authorization 在 contract 下 decision-consistent |
| Theorem 11–13 | 推论 A.1/D.2 的安全 archived-committed 可计算子类 | 在显式 sub-Gaussian、$q,\rho,\sigma$ contract 下给出安全上界和 transcript-KL 下界 |

真正应放在主稿理论开头的是定义 1–6以及定理 A、B、D；定理 C 和推论 C.1 提供 Agent-specific impossibility/regret 强化。Theorem 11–13 保留在后续方法/附录中，说明 SQCAD 如何实现一个可审计的安全 sequential subclass。

## 9. 需要补做的可证伪验证

`src/sqcad/lifecycle_belief_theory.py` 与 `tests/test_lifecycle_belief_theory.py` 已提供有限模型的 theorem-regression diagnostics，核对定理 A 的三项恒等式、$\operatorname{VoR}^{\mathrm{cont}}/\operatorname{VoR}^{\mathrm{info}}$ 分账、动态 quotient lumpability、admissible-value-separated signed-kernel 相反动作构造、零宽度 tie fiber、定理 C/C.1 的同 score regret、定理 D(a) 的 Blackwell 单调性、定理 D(b) 的 transcript-KL regret floor 及其反演预算、推论 D.3 的 priced frontier，以及推论 D.2 的 probe 阈值。它们是 proof witness 和改稿回归检查，不替代本文件的数学证明。

1. **Transition/observation audit。** 在 LifecycleBench 的 forced-keep/forced-archive 配对 rollout 中估计候选暴露、scope/version、provenance 和 restore 成功率，直接检验 $\mathsf K_K\ne\mathsf K_A$，而不是只比较最终任务分数。
2. **Score-fiber test。** 对同一 score 区间内的 belief/state 做配对干预，估计 $\Delta_t$；若 action regret 在 fiber 内显著异质，则为定理 B/C 提供反例证据。
3. **Recoverability/KL-budget test。** 固定 immediate utility 和 workspace budget，逐步改变 probe/restore 通道，分别估计 $\operatorname{VoR}^{\mathrm{cont}}$ 与 $\operatorname{VoR}^{\mathrm{info}}$；同时对每类动作估计两个 matched lifecycle worlds 的 conditional transcript KL，验证 archived/defer 分支是否确实零信息以及 probe/exposure 是否重新打开区分通道。报告 crowding cost，避免把信息价值误报为 keep 的总优势。
4. **Certificate contract audit。** 独立 held-out mechanism family 检验错误授权率、残差 tail、漂移和跨 epoch 稳定性；不能用 toy Gaussian 结果替代真实 LLM certificate coverage。

## 10. 不能过度声称的部分

- 这不是声称“Bayesian formulation 自动解决 lifecycle governance”；先验敏感性、least-favorable prior 和 misspecification 仍需单独分析。
- 这不是声称任意 POMDP 都有新的 Bellman 定理；创新来自持久动作改变未来 candidate/evidence/recovery kernel 的组合结构。
- 这不是声称 `evidence availability` 是唯一额外状态；任何能恢复同等 action-value information 的状态表示都可满足定理 B 的可测性条件。
- 这不是把现有 LLM certificate 当作已证明的 sub-Gaussian 观测；Theorem 11–13 仍是显式 contract 下的 corollary。

## 11. 主稿重构建议

主线应从“不断增加限制条件以修复 Theorem 5”改为：

$$
\text{Agent lifecycle process}
\rightarrow
\text{belief-state value}
\rightarrow
\text{score sufficiency iff measurability}
\rightarrow
\text{censoring counterexample}
\rightarrow
\text{recoverability value}
\rightarrow
\text{architecture-agnostic trichotomy}
\rightarrow
T_{\mathrm{LC}}^*\text{ and }\varepsilon_{\mathrm{LC}}
\rightarrow
\text{SQCAD certificate corollaries}.
$$

这样的结构可以直接 challenge 现有工作：它们若只使用 association/query-local score，必须额外证明定理 B 所要求的 transport/measurability 条件；若 persistent action 改变未来 observation kernel，则定理 C 给出结构性不足性；若提供 restore/probe 通道，则定理 D 说明其价值应进入 lifecycle objective，而不是作为工程补丁。

### 投稿版编号迁移

为避免现有 13 个定理继续挤占主叙事，投稿版建议重新编号，而不是在旧 Theorem 13 后追加：

1. **Main Theorem 1：Lifecycle Bellman Decomposition。** 主文给三项恒等式、canonical Agent filtration 和 A.1；完整 tower-property/convexity proof 放附录。
2. **Main Theorem 2：Score Sufficiency iff Measurability。** 主文给充要条件、B.2 的充分路线和 C 的同-score 反例；旧 Theorem 1–2 作为两个 verified constructions。
3. **Main Theorem 3：Recoverability Monotonicity and Information-Budget Necessity。** 主文给 Blackwell 非负/严格正条件、一般 transcript-KL regret 下界以及 D.1/D.2；旧 Theorem 5–6 作为 interval/minimax corollary。
4. **Main Theorem 4：Architecture-agnostic Lifecycle Trichotomy。** 主文给三分、midpoint cost witness、task drift 推论与 $T_{\mathrm{LC}}^*$；完整 measure/quotient proof 放附录。
5. 旧 Theorem 3–4 移附录，标题明确 `restricted committed subclass`；旧 Theorem 7–10 作为 diagnostic/authorization lemmas；旧 Theorem 11–13 作为 `safe Gaussian/sub-Gaussian certificate subclass`。

主文理论篇幅应围绕三条基础定理和一个总括定理控制在约 2 页；不能同时保留当前 §3.1–§3.8 的全部构造细节。反例数值、固定样本推导、bridge contract 和完整证明统一放附录，主文只保留每条定理的假设、结论、Agent-specific novelty 和一个可视化 witness。

### ICLR 555 理论门槛审计

| 门槛 | 当前状态 | 达到 solid-5 仍缺的证据 |
|---|---|---|
| Correctness | G1--G4 与 C/C.1 已有显式证明；32 项有限 witness 覆盖 Bellman、fiber、Blackwell、KL-budget、三分和 midpoint regret | 外部理论审读；确认 stopping-time transcript KL、standard-Borel quotient、utility normalization、minimality 和 filtration contract 无遗漏 |
| Novelty | Agent kernel 的 access/information 联合缺口与架构无关 lifecycle estimand 已明确，且不冒充 Bellman/Blackwell/measure separation 原创 | 系统文献核查：现有 Agent memory 工作是否已有等价 lifecycle transcript trichotomy 或 sufficient statistic |
| Agent specificity | persistence、candidate regeneration、workspace competition、recoverability 已进入状态和 kernel | 在真实执行 trace 中证明这些 kernel 确实因 keep/archive 改变，而非仅 toy construction |
| Claim–evidence alignment | 19/20/31/38/42/43/44/45 已同步 G4；Theorem 1–13 已有嵌入表，证书结论继续保持 contract-conditional | 最终 LaTeX、图和实验表仍需逐项对照；不得把 toy/controlled witness 外推为真实三分定位 |
| Falsifiability | 已定义 transition audit、score-fiber test、recoverability test | 在 held-out mechanism families 上执行并报告负结果也成立的预注册检验 |

因此，当前数学底稿已经形成可 challenge 的条件化一般理论，内部证明工作已基本收尾，但尚不能诚实宣称 ICLR 三项评分稳定达到 5：剩余数学置信来自独立 proof audit；research-gap 的非空性和意义则来自真实 Agent 干预中对三分分支、自然 utility separation 与 $\varepsilon_{\mathrm{LC}}$ 的估计，而不是继续追加 certificate lemma。
