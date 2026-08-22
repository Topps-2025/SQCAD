# Appendix: Proofs for Agent Lifecycle Belief Control

## A.1 Scope and standing assumptions

This appendix isolates the mathematical claims from the empirical contracts. Let the latent-world space $\Theta$, observable physical-state spaces $\mathcal S_t$, observation spaces $\mathcal O_t$, and belief-state spaces $X_t$ be standard Borel. The horizon $H$ and action set $\mathcal A$ are finite, rewards are bounded and measurable, $\gamma\in(0,1]$, and every regular conditional distribution used below exists. The post-observation state is $x_t=(b_t,s_t)$, where $b_t=P(\theta\in\cdot\mid\mathcal F_t)$.

The Agent execution order is fixed as

$$
\mathcal F_t
\subset
\mathcal F_t\vee\sigma(A_t,S_{t+1})
\subset
\mathcal F_{t+1}
=\mathcal F_t\vee\sigma(A_t,S_{t+1},O_{t+1}).
\tag{A.1}
$$

For action $a$, the environment kernel factorizes according to this order:

$$
\mathsf K_a(ds',do\mid s,\theta)
=P_a^S(ds'\mid s,\theta)P_a^O(do\mid s',s,\theta).
\tag{A.2}
$$

The next state $s'$ contains persistent authorization, candidate regeneration, workspace occupancy, scope/version, provenance, and recoverability. The observation $o$ contains only evidence revealed after that state transition. This split is representation-dependent, but its sum is not; all value claims below use the fixed operational filtration (A.1).

For $x=(b,s)$, define

$$
Q_t(x,a)=\ell_t(x,a)+\gamma C_t^a(x),
\qquad
C_t^a(x)=\mathbb E\!\left[V_{t+1}(b^{a,S',O},S')\mid x,a\right],
\tag{A.3}
$$

and

$$
A_t^a(x)=\mathbb E\!\left[V_{t+1}(b^{a,S'},S')\mid x,a\right],
\qquad
I_t^a(x)=C_t^a(x)-A_t^a(x).
\tag{A.4}
$$

Write $K$ and $A$ for persistent keep and archive, and let

$$
\Delta_t(x)=Q_t(x,K)-Q_t(x,A).
\tag{A.5}
$$

No proof in this appendix assumes that a deployed LLM Agent satisfies (A.2), conditional Blackwell dominance, zero-KL archive branches, or a score-fiber crossing. Those are falsifiable model-membership conditions.

## A.2 Auxiliary lemmas

### Lemma A.1 (Posterior martingale under conditional garbling)

Fix a next state $s'$. Let $Z$ be a fine observation and let $O$ be generated from $Z$ through a kernel independent of $\theta$. If $b_Z=P(\theta\in\cdot\mid s',Z)$ and $b_O=P(\theta\in\cdot\mid s',O)$, then, as random probability measures,

$$
b_O=\mathbb E\!\left[b_Z\mid s',O\right].
\tag{A.6}
$$

**Proof.** For every bounded measurable $f:\Theta\to\mathbb R$,

$$
\int f\,db_O
=\mathbb E\!\left[f(\theta)\mid s',O\right]
=\mathbb E\!\left[\mathbb E\!\left[f(\theta)\mid s',Z\right]\mid s',O\right]
=\int f\,d\mathbb E\!\left[b_Z\mid s',O\right].
$$

The first and third equalities are definitions of the regular conditional beliefs, and the middle equality is the tower property using the Markov chain $\theta\to Z\to O$ conditional on $s'$. A countable determining class on the standard-Borel space identifies the two random probability measures. $\square$

### Lemma A.2 (Strict Jensen criterion for finite policy trees)

Let $V(b)=\max_{j\in J}\{\langle b,r_j\rangle+c_j\}$ for a finite set $J$, and let $B$ be a random belief. Then

$$
\mathbb E\!\left[V(B)\right]=V(\mathbb E B)
$$

if and only if there exists $j^*\in J$ that is optimal at $B$ almost surely. Hence Jensen is strict whenever no single continuation policy tree is optimal almost surely on the conditional posterior support.

**Proof.** Choose $j^*$ optimal at $\mathbb E B$. Affinity gives

$$
V(\mathbb E B)=\mathbb E[\langle B,r_{j^*}\rangle+c_{j^*}]
\le\mathbb E\!\left[V(B)\right].
$$

Equality holds exactly when the nonnegative random variable $V(B)-(\langle B,r_{j^*}\rangle+c_{j^*})$ vanishes almost surely. The converse is immediate. $\square$

### Lemma A.3 (Weighted two-world testing bound)

Let $P,Q$ be probability laws, $E$ a measurable event, and $d_+,d_->0$. Then

$$
\max\{d_+P(E),d_-Q(E^c)\}
\ge
\frac{d_+d_-}{2(d_++d_-)}e^{-\operatorname{KL}(P\Vert Q)}.
\tag{A.7}
$$

**Proof.** Bretagnolle--Huber gives $P(E)+Q(E^c)\ge c$, where $c=\tfrac12e^{-\operatorname{KL}(P\Vert Q)}$. For nonnegative $p,q$ with $p+q\ge c$, the smallest possible $\max\{d_+p,d_-q\}$ is attained when $d_+p=d_-q$ and $p+q=c$. Its value is $cd_+d_-/(d_++d_-)$. $\square$

### Lemma A.4 (Adaptive stopped-transcript KL ledger)

Let two Agent worlds have the same initial history. Before a stopping time $\tau\le H$, a shared policy kernel selects action $A_u$ from history $H_u$, and world $w\in\{+,-\}$ returns an observed increment $W_{u+1}$ from $\mathsf K_{A_u,w}(\cdot\mid H_u)$. Randomized stop/continue decisions and the terminal authorization $D$ also use shared policy kernels. Define

$$
Y_\tau=(A_0,W_1,\ldots,A_{\tau-1},W_\tau,\tau),
\qquad T_\tau=(Y_\tau,D),
\tag{A.8}
$$

and pad all post-stopping slots with a world-independent absorbing symbol. If $P_+^\pi\ll P_-^\pi$, then

$$
\operatorname{KL}(P_+^\pi(T_\tau)\Vert P_-^\pi(T_\tau))
=\mathbb E_+^\pi\sum_{u<\tau}
\operatorname{KL}\!\left(
\mathsf K_{A_u,+}(\cdot\mid H_u)
\Vert
\mathsf K_{A_u,-}(\cdot\mid H_u)
\right).
\tag{A.9}
$$

**Proof.** Apply the relative-entropy chain rule to the padded fixed-horizon law. The initial factor has zero KL. Conditional action-selection, randomized stopping, and terminal-decision factors are identical in the two worlds and therefore contribute zero. Absorbing post-stopping factors also contribute zero. The remaining conditional factors are exactly the pre-stopping environment kernels in (A.9). If absolute continuity fails, the left side is $+\infty$ and finite information lower bounds become vacuous. $\square$

## A.3 Main results

### Theorem A.1 (Lifecycle Bellman decomposition)

For each persistent action $a\in\{K,A\}$,

$$
Q_t(x,a)=\ell_t(x,a)+\gamma A_t^a(x)+\gamma I_t^a(x).
\tag{A.10}
$$

Consequently,

$$
\Delta_t
=\Delta_t^{\rm imm}
+\gamma\Delta_t^{\rm access}
+\gamma\Delta_t^{\rm info}.
\tag{A.11}
$$

**Proof.** Equation (A.4) defines $I_t^a=C_t^a-A_t^a$, hence $C_t^a=A_t^a+I_t^a$. Substitute this identity into (A.3), then subtract the archive equality from the keep equality. Equivalently, (A.4) follows by conditioning first on $S'$ and then on $O$ along (A.1). $\square$

The complete continuation difference

$$
\operatorname{VoR}^{\rm cont}_{t,K:A}
=\gamma(C_t^K-C_t^A)
$$

is not sign-definite when the actions change state/access kernels. Under a common state kernel it equals

$$
\operatorname{VoR}^{\rm info}_{t,K:A}
=\gamma(I_t^K-I_t^A),
$$

the conditional information quantity signed below.

### Theorem A.2 (Score sufficiency iff lifecycle-value measurability)

Let $S_t:X_t\to\mathcal Z$ be measurable between standard-Borel spaces, and assume $\Delta_t$ is measurable.

1. A score-only rule reproduces the keep region $\{\Delta_t\ge0\}$ if and only if that region belongs to $\sigma(S_t)$.
2. Score-only rules reproduce every shifted keep region $\{\Delta_t\ge\lambda\}$, $\lambda\in\mathbb R$, if and only if $\Delta_t=g_t\circ S_t$ for a measurable $g_t$.

**Proof.** The first statement is the definition of measurability with respect to $\sigma(S_t)$. For the fiber formulation, a Borel keep region constant on every score fiber and its complement are saturated. Their score images are disjoint analytic sets; Lusin separation gives a Borel subset of $\mathcal Z$ whose inverse image is the keep region.

For the second statement, factorization immediately supplies every threshold rule. Conversely, threshold sufficiency for rational $q$ makes every upper level set $\{\Delta_t\ge q\}$ belong to $\sigma(S_t)$. Rational upper level sets generate $\mathcal B(\mathbb R)$, so $\Delta_t$ is $\sigma(S_t)$-measurable. The standard-Borel Doob--Dynkin factorization gives $\Delta_t=g_t\circ S_t$. $\square$

If one score fiber contains gaps $d_1>0$ and $-d_2<0$, a score-only rule keeping with probability $p$ has regrets $(1-p)d_1$ and $pd_2$. Therefore

$$
\inf_{p\in[0,1]}\max\{(1-p)d_1,pd_2\}
=\frac{d_1d_2}{d_1+d_2}>0.
\tag{A.12}
$$

For a fiber with finite measurable endpoints $L<0<U$, the same calculation gives $U(-L)/(U-L)\le(U-L)/4$. Non-crossing and zero-width tie fibers have zero regret.

### Proposition A.2.1 (Horizon-wide quotient sufficiency)

For each remaining stage, let $\phi_u:X_u\to Z_u$ be measurable. Suppose rewards factor through $\phi_u$, next-state push-forward kernels depend on $x$ only through $\phi_u(x)$ for every action, and terminal value factors through $\phi_{H+1}$. Then all remaining action values and optimal values factor through the corresponding quotient maps, and a quotient-only Bayes-optimal policy exists.

**Proof.** Backward induction. If $V_{u+1}=\bar V_{u+1}\circ\phi_{u+1}$, reward factorization and push-forward equality give

$$
Q_u(x,a)=\bar\ell_u(\phi_u(x),a)
+\gamma\int\bar V_{u+1}(z')\bar T_u^a(dz'\mid\phi_u(x)).
$$

Thus $Q_u$ factors through $\phi_u$. A maximum over the finite action set preserves factorization. $\square$

For a universal converse, require one-step action-value factorization for every bounded measurable quotient terminal payoff. Unequal push-forward kernels are then separated by a Borel indicator, so push-forward equality is necessary. This converse is universal over payoffs; it does not infer kernel equality from one fixed task.

### Corollary A.2.2 (Value-separating signed kernels)

For same-score states $x_1,x_2$, let

$$
\nu_i=(\phi_{t+1})_\#T_t^K(\cdot\mid x_i)
-(\phi_{t+1})_\#T_t^A(\cdot\mid x_i).
$$

Let $\mathcal V_{t+1}$ be the bounded continuation values realizable by the admissible future reward/control class. If some $v\in\mathcal V_{t+1}$ satisfies $h_i=\int v\,d\nu_i$ and $h_1\ne h_2$, then the common immediate contrast

$$
d=-\frac\gamma2(h_1+h_2)
$$

produces opposite lifecycle contrasts $\gamma(h_1-h_2)/2$ and $-\gamma(h_1-h_2)/2$. If the task class is closed under all bounded measurable quotient terminal payoffs, $\nu_1\ne\nu_2$ alone supplies such a $v$ by Borel separation. Otherwise, kernel inequality alone is insufficient: differences orthogonal to every realizable value are decision-equivalent for that task class. $\square$

### Theorem A.3 (Recoverability value and information-budget necessity)

**Part (a): conditional value.** Suppose keep and archive have the same state kernel for $b$-almost every $\theta$. Conditional on almost every $s'$, suppose the archive observation is a $\theta$-independent garbling of the keep observation. If $V_{t+1}(\cdot,s')$ is convex, then

$$
\operatorname{VoR}^{\rm info}_{t,K:A}\ge0.
\tag{A.13}
$$

The inequality is strict for $\gamma>0$ if strict conditional Jensen holds on a positive-probability set. In a finite POMDP, Lemma A.2 supplies the concrete sufficient condition that no single continuation policy tree is optimal almost surely over that conditional posterior support.

**Proof.** Lemma A.1 gives $b_O^A=\mathbb E[b_Z^K\mid s',O]$. Conditional Jensen yields

$$
V_{t+1}(b_O^A,s')
\le\mathbb E\!\left[V_{t+1}(b_Z^K,s')\mid s',O\right].
$$

Integrate over $O$ and the common next-state marginal. The common state kernel makes the access terms equal, leaving $I_t^K-I_t^A\ge0$. Positive-probability strict Jensen makes the integrated inequality strict. $\square$

**Part (b): adaptive information necessity.** Let a policy stop at $\tau$ and issue $D\in\{K,A\}$. Consider two worlds with common initial history. On all relevant authorization histories, mistaken archive in $M_+$ costs at least $d_+>0$, while mistaken keep in $M_-$ costs at least $d_->0$. Let $P_+^\pi,P_-^\pi$ be the padded augmented-transcript laws from Lemma A.4, and set $B_\pi=\operatorname{KL}(P_+^\pi\Vert P_-^\pi)$. Then

$$
\max\{\mathbb E_+R_\tau,\mathbb E_-R_\tau\}
\ge
\frac{d_+d_-}{2(d_++d_-)}e^{-B_\pi}.
\tag{A.14}
$$

**Proof.** Apply Lemma A.3 to the measurable event $E=\{D=A\}$. The two weighted error probabilities lower-bound the corresponding terminal authorization regrets. Lemma A.4 supplies the adaptive action-level KL ledger. $\square$

If all non-diagnostic archived/defer branches have zero conditional KL, while channel-opening action class $j$ has conditional KL at most $\kappa_j$, then

$$
B_\pi\le\sum_j\kappa_j\mathbb E_+N_j.
\tag{A.15}
$$

This zero-KL statement is an assumption to be audited action by action, not a generic property of archive.

### Corollary A.3.1 (Priced recoverability frontier)

Let $\alpha=d_+d_-/[2(d_++d_-)]$. Suppose one channel-opening action class has KL at most $\kappa>0$ and direct cost at least $c>0$ per action, and all other pre-authorization actions have zero conditional KL. With $N$ the count, $n=\mathbb E_+N$, and $\widetilde R_\tau=R_\tau+C_\tau$ the terminal authorization regret plus diagnostic cost relative to a world-informed immediate authorization,

$$
\max_w\mathbb E_w\widetilde R_\tau
\ge\max\{cn,\alpha e^{-\kappa n}\}
\ge\frac c\kappa W_0\!\left(\frac{\kappa\alpha}{c}\right).
\tag{A.16}
$$

**Proof.** Equation (A.14) and $B_\pi\le\kappa n$ give the second term inside the maximum. Expected diagnostic cost in $M_+$ is at least $cn$, giving the first. The minimum over $n\ge0$ occurs where $cn=\alpha e^{-\kappa n}$. Setting $x=\kappa n$ gives $xe^x=\kappa\alpha/c$, whose nonnegative solution is $W_0(\kappa\alpha/c)$. $\square$

For a target $r<\alpha$, worst-world total authorization loss at most $r$ therefore requires

$$
n\ge\kappa^{-1}\log(\alpha/r),
\qquad
(c/\kappa)\log(\alpha/r)\le r.
\tag{A.17}
$$

This is a no-free-recovery statement for self-censoring Agent authorization. It is not a claim that Lambert-$W$, Bretagnolle--Huber, or adaptive KL decomposition is new.

## A.4 Architecture-agnostic lifecycle trichotomy

The preceding results use a belief-state representation, but their final decision object can be stated without committing to external, retrieval, prompt, cache, or parameterized memory. Let $\mathcal Z$ be a standard-Borel task space and let $\Omega$ be the standard-Borel space of complete future Agent transcripts. A transcript may include future queries, retrieved memories, LLM outputs, tool calls, memory updates, environment states, and task outcomes. For $a\in\{K,A\}$, let

$$
P^a(dy\mid x,z)
=\mathcal L(Y_{t:H}\in dy\mid x,\operatorname{do}(a),z)
\tag{A.18}
$$

be a jointly measurable probability kernel. The intervention is required to be operationally defined and persistent; an immutable parameter with no retain/suppress/update intervention is not a keep/archive action in this theorem. Define the signed future-transcript kernel

$$
\nu_{x,z}:=P^K(\cdot\mid x,z)-P^A(\cdot\mid x,z).
\tag{A.19}
$$

For a bounded measurable task utility $u:\Omega\to\mathbb R$ and $0<\gamma\le1$, let the lifecycle contrast be

$$
\Delta_{z,u}(x)
=d_z(x)+\gamma\int_\Omega u(y)\,\nu_{x,z}(dy),
\tag{A.20}
$$

where $d_z(x)$ is the immediate keep--archive contrast. Let $S:X\to\mathcal S$ be a measurable governance score. To isolate future-memory insufficiency from an ordinary omitted current cost, assume throughout this section that the immediate contrast is score-visible:

$$
d_z(x)=\bar d(S(x),z).
\tag{A.21}
$$

We also use the regular quotient condition that every bounded measurable function constant on the fibers of $S$ admits a measurable factorization through $S$. This holds directly in finite/countable audits and for the regular standard-Borel score quotients used in Theorem A.2.

For each task $z$, let $\mathcal U_z$ be a uniformly bounded class of measurable transcript utilities containing the zero utility. Thus there is a declared $U_{\max}<\infty$ such that $\sup_{z,u\in\mathcal U_z}\lVert u\rVert_\infty\le U_{\max}$. It is *separating for the induced Agent kernels* if, for any relevant signed kernels $\nu\ne\nu'$,

$$
\exists u\in\mathcal U_z:
\int u\,d\nu\ne\int u\,d\nu'.
\tag{A.22}
$$

The unit ball of bounded measurable utilities is a uniformly bounded separating class by Borel indicator separation. A restricted natural-task class need not be separating; this is an explicit boundary rather than an implicit universality claim. The common envelope fixes the utility scale and prevents the approximation supremum in (A.31) from becoming infinite merely by rescaling one utility.

### Theorem A.4 (Architecture-agnostic lifecycle trichotomy)

Exactly one of the following branches holds for the induced future-transcript kernels.

1. **Future-null memory:** $\nu_{x,z}=0$ for every $x,z$. Keep and archive induce the same future transcript law, so $\Delta_{z,u}(x)=d_z(x)$ for every bounded utility.
2. **Non-null but lifecycle-complete score:** some $\nu_{x,z}\ne0$, and for every task $z$ the signed kernel is constant on every score fiber:

   $$
   S(x_1)=S(x_2)
   \Longrightarrow
   \nu_{x_1,z}=\nu_{x_2,z}.
   \tag{A.23}
   $$

   Then, for every $z$ and every bounded measurable $u$, there is a measurable $g_{z,u}$ such that $\Delta_{z,u}=g_{z,u}\circ S$. Thus the score is uniformly sufficient over the declared task-utility class and all scalar cost shifts.
3. **Non-null and future-lossy score:** some future-memory channel is non-null and there exist $x_1,x_2,z$ such that

   $$
   S(x_1)=S(x_2),
   \qquad
   \nu_{x_1,z}\ne\nu_{x_2,z}.
   \tag{A.24}
   $$

   If $\mathcal U_z$ separates these kernels, there is a task utility $u\in\mathcal U_z$ for which the two lifecycle values differ. After the common scalar cost shift

   $$
   \lambda^*
   :=\frac{\Delta_{z,u}(x_1)+\Delta_{z,u}(x_2)}{2},
   \tag{A.25}
   $$

   the shifted contrasts are opposite. Every randomized score-only rule then has two-state worst-case regret at least

   $$
   \boxed{
   \frac{1}{4}
   \left|\Delta_{z,u}(x_1)-\Delta_{z,u}(x_2)\right|
   =
   \frac{\gamma}{4}
   \left|
   \int u\,d(\nu_{x_1,z}-\nu_{x_2,z})
   \right|
   >0
   }.
   \tag{A.26}
   $$

   If the unshifted contrasts already have opposite signs, the same conclusion holds under the original fixed cost contract.

**Proof.** Either all signed kernels vanish, which is branch 1, or at least one is nonzero. Conditional on the latter, either (A.23) holds on every score fiber and task, or its negation supplies (A.24). Hence the branches are exhaustive and mutually exclusive.

In branch 1, (A.20) immediately reduces to $d_z$. In branch 2, (A.23), the regular quotient condition, and (A.21) imply measurable factorizations of both terms in (A.20), hence of $\Delta_{z,u}$. Theorem A.2 then gives uniform cost sufficiency.

In branch 3, separation gives $u$ such that $q_i:=\int u\,d\nu_{x_i,z}$ satisfy $q_1\ne q_2$. Since the immediate contrast is the same on a score fiber by (A.21),

$$
\Delta_{z,u}(x_1)-\Delta_{z,u}(x_2)
=\gamma(q_1-q_2)\ne0.
$$

Subtracting the midpoint $\lambda^*$ produces gaps $g$ and $-g$, where $g=|\Delta_{z,u}(x_1)-\Delta_{z,u}(x_2)|/2$. A score-only rule must use one keep probability at both states. Equation (A.12) with equal positive gap magnitudes gives minimax regret $g/2$, which is (A.26). $\square$

The theorem is architecture-agnostic but not assumption-free. It does not assert that every LLM reads every memory, that every natural task class separates every transcript difference, or that every score is lossy. Instead, it exhausts all non-pathological possibilities: a claimed universal score must either govern a future-null memory channel or preserve the full task-relevant signed future-transcript kernel.

### Corollary A.4.1 (Task drift and point-mass completeness)

Let a future task be drawn from $\mu\in\mathcal P(\mathcal Z)$ and let $z\mapsto u_z\in\mathcal U_z$ be jointly measurable. The mixture lifecycle contrast is

$$
\Delta_{\mu}(x)
=\int_{\mathcal Z}
\left[
d_z(x)+\gamma\int_\Omega u_z(y)\,\nu_{x,z}(dy)
\right]\mu(dz).
\tag{A.27}
$$

If the admissible drift family contains all point masses $\delta_z$, uniform score sufficiency over that family implies pointwise sufficiency for every task $z$. Conversely, a jointly measurable pointwise factorization through $(S,z)$ implies factorization of (A.27) for every mixture $\mu$. Therefore any branch-3 witness at task $z$ is also a valid drift witness under $\mu=\delta_z$. Task drift enlarges the challenge class but is not necessary for failure; a fixed dedicated task can already instantiate branch 3.

**Proof.** Necessity follows by substituting $\mu=\delta_z$ into (A.27). Sufficiency follows by integrating the pointwise score-factorized contrast with respect to $\mu$. $\square$

### Definition A.4.2 (Lifecycle sufficient statistic)

Define task-relative lifecycle equivalence by

$$
\begin{aligned}
x\equiv_{\rm LC}x'
\quad\Longleftrightarrow\quad
&d_z(x)=d_z(x')\\
&\text{and }\int u\,d\nu_{x,z}=\int u\,d\nu_{x',z}
\quad\text{for every }z\text{ and }u\in\mathcal U_z.
\end{aligned}
\tag{A.28}
$$

The equivalence classes define the partition-valued object

$$
T_{\rm LC}^*(x):=[x]_{\equiv_{\rm LC}}
\tag{A.29}
$$

which is the coarsest task-relative lifecycle sufficient information object in partition order: any statistic $T$ that is sufficient for every declared task utility and scalar cost shift must refine this partition,

$$
T(x)=T(x')\Longrightarrow x\equiv_{\rm LC}x'.
\tag{A.30}
$$

Equivalently, the coordinate map

$$
\Phi_{\rm LC}(x)
:=
\left(
(d_z(x))_{z\in\mathcal Z},
\left(\int u\,d\nu_{x,z}\right)_{z\in\mathcal Z,\,u\in\mathcal U_z}
\right)
\tag{A.30a}
$$

has exactly the fibers in (A.28), with the codomain carrying the product sigma-field. Thus (A.29) is always well defined as a measurable information partition, but its quotient need not itself be standard Borel. A standard-Borel representative exists when the equivalence relation is smooth, for example when countable determining task and utility subfamilies generate the same fibers. This regularity is required before treating $T_{\rm LC}^*$ as an implementable controller state. When each $\mathcal U_z$ contains the unit ball of bounded measurable utilities, (A.28) is equivalent to equality of $d_z$ and the complete signed kernels $\nu_{x,z}$ for every task. The operational framework need not estimate an unrestricted probability law when the natural utility class is smaller; it must estimate exactly the quotient of the signed kernel that the declared tasks can value.

**Proof.** Equality in (A.28) makes (A.20) identical for all declared tasks and utilities, so $T_{\rm LC}^*$ is sufficient. Conversely, if a sufficient statistic merges two states violating (A.28), either an immediate contrast or a declared utility separates their action values. A scalar cost shift at their midpoint then contradicts uniform sufficiency. Thus every uniformly sufficient statistic refines the equivalence classes. $\square$

For an approximate statistic $T$, the estimable target is its lifecycle oscillation

$$
\varepsilon_{\rm LC}(T)
:=
\sup_{T(x)=T(x')}
\sup_{z,\,u\in\mathcal U_z}
\left|\Delta_{z,u}(x)-\Delta_{z,u}(x')\right|.
\tag{A.31}
$$

For each observed task and cost contract, Corollary A.2 gives a fiber-wise randomized rule with worst-case action regret at most $\varepsilon_{\rm LC}(T)/4$, provided the corresponding fiber endpoints are finite and measurable. The bound is per observed task and cost contract; one common randomized rule does not simultaneously cover different tasks unless $z$ is an input to the controller. Equation (A.31), rather than current retrieval relevance alone, is the estimand that the subsequent SQCAD framework must approximate and audit. This is an information-loss claim, not a dimensionality claim: whenever a smooth standard-Borel representative exists, it may in principle be injectively encoded by one real-valued score. The empirical challenge is whether an existing score carries that encoding.

## A.5 What is mathematical and what is empirical

| Question | Needed for theorem validity? | Needed for the paper's Agent-specific claim? |
|---|---:|---:|
| Standard-Borel measurability and regular conditional beliefs | yes | no separate experiment |
| Correct weighted Bretagnolle--Huber and stopped-KL derivation | yes | no separate experiment |
| External proof audit of Theorems A.1--A.4 | not a logical assumption, but required for high reviewer confidence | yes for a strict top-score claim |
| Keep/archive changes candidate, workspace, scope, or evidence kernels in the implemented Agent | no for the trichotomy; it decides whether the system is in branch 1 or a non-null branch | yes for a non-vacuous Agent-memory claim |
| A real baseline score collapses states with different realizable lifecycle values | no | yes |
| Archived/defer branches have zero or small conditional KL | no; A.14 holds with measured $B_\pi$ | yes for the censoring-ledger specialization A.15--A.17 |
| Probe/restore has measured cost and KL-bearing observations | no | yes for the priced-frontier interpretation |
| Common-state conditional Blackwell dominance | yes for A.13 only | yes before applying A.13 to real traces |

The proof package can therefore be mathematically correct before real-Agent experiments exist. Theorem A.4 strengthens the scope: every intervention-defined LLM-Agent memory architecture belongs to one of its three branches. Real-Agent experiments no longer establish the general theorem; they locate named systems and natural task classes in the trichotomy and estimate whether practical scores approximate $T_{\rm LC}^*$.

## A.6 Proof-audit checklist

1. Verify that every theorem uses the fixed Agent filtration (A.1); never move workspace/candidate effects into the information term.
2. Preserve the distinction between fixed-task measurability, universal payoff converse, and admissible-value kernel separation.
3. In every Blackwell application, verify the common state kernel or condition on a common state-level posterior before using Jensen.
4. In every transcript lower bound, include actions, stopping, terminal decision, and absorbing padding; add initial-history KL if histories are not identical.
5. Report terminal authorization regret separately from pre-authorization diagnostic cost; use Corollary A.3.1 only when cost is included explicitly.
6. Treat per-action zero-KL and KL-cap statements as empirical contracts. Do not infer them from the labels `archive`, `defer`, `probe`, or `restore`.
7. In Theorem A.4, keep the future-null, lifecycle-complete, and future-lossy branches distinct. A non-null memory channel alone does not imply score failure.
8. Do not replace the separating-utility assumption by a claim that every natural task values every transcript difference. For a restricted task class, use the quotient in (A.28).
9. Normalize the declared utility class with a common envelope and include the zero utility; otherwise $\varepsilon_{\rm LC}$ can diverge by arbitrary utility rescaling and the minimality proof cannot isolate $d_z$.
10. State minimality in partition order. Do not assume the lifecycle quotient is standard Borel without smoothness or a countable determining family, and do not equate scalar-valuedness with information loss.
