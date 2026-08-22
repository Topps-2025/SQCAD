# Lifecycle Value, Score Sufficiency, and Recoverability in Persistent-Memory Agents

> **Draft status.** Synchronized theory spine for ICLR 2027 Sections 2--3. The main manuscript now uses Theorems 1--3 and demotes the former Theorem 1--13 chain to Appendix A constructions, restricted propositions, and certificate subclasses. Citation metadata has passed offline parsing only and still requires the complete online gate.

## One-sentence argument

In persistent-memory agents, we show that memory authorization must be evaluated through a lifecycle action-value contrast because current keep/archive decisions alter future access states and evidence experiments; this yields an exact sufficiency criterion for score-only governance, a score-fiber regret bound, and a recoverability theorem that combines conditional Blackwell value with a transcript-KL necessity bound for arbitrary adaptive authorization policies.

## Terminology ledger

| Canonical term | Definition at first use | Avoided variants |
|---|---|---|
| persistent-memory agent | an agent whose memory action changes a state consumed by later kernels and cannot be reversed immediately at zero cost | long-memory agent, permanent-memory agent |
| lifecycle action-value contrast | $\Delta_t=Q_t(K)-Q_t(A)$ | lifecycle score, memory worth |
| access value | continuation value due to candidate, workspace, scope/version, and recoverability-state transitions | retrieval value, state information value |
| conditional information value | value of evidence observed after conditioning on the next physical state | access value, total VoR |
| action-dependent censoring | a persistent action changes which future candidate or evidence events can occur | ordinary missingness |
| score fiber | the set of belief-states sharing one score value | score bucket, equivalence class |
| recoverability | a future evidence experiment made available by retain/restore/probe state | reversibility, accessibility |

## 2. Related work and theoretical boundary

Decision-centric memory has recently moved beyond relevance-only retrieval. DeMem formulates budgeted Agent memory as a rate--distortion problem and derives an exact forgetting boundary based on downstream decision conflict rather than descriptive similarity (Zou et al., 2026, PDF pp. 1--5). Its analytical model is a memory-constrained contextual decision problem, instantiated as a contextual bandit in which contexts are sampled independently from a fixed distribution. Memory Worth estimates the conditional success probability of episodes in which a memory is retrieved and explicitly treats this quantity as associational rather than causal (Simsek, 2026, PDF pp. 2--5). OBLIVION treats forgetting as control over decaying accessibility, with uncertainty-gated reads and reactivation (Rana et al., 2026, PDF pp. 1--4), while FadeMem uses relevance, frequency, and recency to control adaptive decay (Wei et al., 2026, PDF pp. 1--4). These works establish that memory should be governed and that deletion need not be binary. They do not, in the versions examined here, characterize when a current governance score is sufficient for a persistent action whose downstream state and evidence kernels differ.

The mathematical ingredients for such a characterization are classical. Controlled-sensing and active-perception POMDPs allow actions to influence dynamics and observations, optimize over beliefs, and use convexity or information ordering to compare experiments (Satsangi et al., 2018; Krishnamurthy, 2017; Shi et al., 2025). Bretagnolle--Huber and the adaptive KL chain rule are likewise standard lower-bound tools. We therefore do not claim a new Bellman equation, Doob--Dynkin lemma, Blackwell theorem, or sequential-testing inequality. Our contribution is their Agent-memory specialization: persistent authorization determines which candidate, workspace, and evidence transitions occur, which archived periods carry zero distinguishing KL, and which priced exposure/probe/restore actions reopen the information channel. This specialization produces an operationally falsifiable condition for score-only governance and a quantitative regret consequence when recoverable information is limited.

## 3. Persistent-memory lifecycle control

### 3.1 Process and persistence contract

Consider a finite horizon $t=1,\ldots,H$ and a latent environment $\theta\in\Theta$. The observable Agent state is

$$
s_t=(m_t,w_t,\mathcal C_t,e_t,z_t),
$$

where $m_t$ records memory authorization and scope/version, $w_t$ is the available workspace and storage budget, $\mathcal C_t$ is the candidate pool, $e_t$ is the provenance/evidence state, and $z_t$ records restore and probe availability. Given history $h_t$, the Agent holds the posterior $b_t(\theta)=P(\theta\mid h_t)$. Its lifecycle actions are $\mathcal A=\{K,A,P,D\}$ for keep, archive, probe, and defer.

An action produces the next physical state and then the evidence visible in that state:

$$
\mathsf K_a(ds',do\mid s,\theta)
=P_a^S(ds'\mid s,\theta)P_a^O(do\mid s',s,\theta).
\tag{1}
$$

This order fixes the canonical execution filtration

$$
\mathcal F_t
\subset \mathcal F_t\vee\sigma(a_t,s_{t+1})
\subset \mathcal F_t\vee\sigma(a_t,s_{t+1},o_{t+1})=\mathcal F_{t+1}.
\tag{2}
$$

The state transition contains candidate regeneration, workspace competition, authorization duration, scope/version compatibility, and restore cost. The observation kernel contains evidence that can actually be generated after that transition. This convention is substantive: moving a variable between $s'$ and $o$ changes the names of the access and information terms below, although their sum remains invariant.

The process is *persistent* only if $m_{t+1}$ records an authorization commitment that later kernels consume, including its duration and reversal or restore cost. If an action can be changed at the next step without cost or trace, the process reduces to one-step retrieval control and is outside our target class.

We say that the process exhibits *action-dependent censoring* if, for some state, latent world, and future candidate or evidence event $E$,

$$
P_\theta(E\mid s,K)\neq P_\theta(E\mid s,A),
\tag{3}
$$

and this difference is induced by the persistent action through $\mathcal C_{t+1:H}$, $e_{t+1:H}$, or $z_{t+1:H}$. Archive may therefore prevent evidence from being generated, or make it observable only through a priced probe. This differs from query-local missingness because the governance action changes the future data-generating process.

### 3.2 Theorem 1: lifecycle Bellman decomposition

Let the immediate expected net utility be

$$
\ell_t(b,s,a)=\mathbb E_{\theta\sim b}[r_\theta(s,a)-\kappa(s,a)],
$$

and define $V_{H+1}=0$ and

$$
Q_t((b,s),a)=\ell_t(b,s,a)+\gamma C_t^a(b,s),
\qquad
V_t(b,s)=\max_{a\in\mathcal A}Q_t((b,s),a),
\tag{4}
$$

where

$$
C_t^a(b,s)=
\mathbb E\left[V_{t+1}(b^{a,s',o},s')\mid b,s,a\right].
\tag{5}
$$

Let $b^{a,s'}$ denote the posterior after observing the next physical state but before observing $o$. Define

$$
A_t^a(b,s)=
\mathbb E\left[V_{t+1}(b^{a,s'},s')\mid b,s,a\right],
\qquad
I_t^a(b,s)=C_t^a(b,s)-A_t^a(b,s).
\tag{6}
$$

Here $A_t^a$ is the continuation value induced by physical access-state transitions, while $I_t^a$ is the conditional value of the subsequent evidence experiment.

**Theorem 1 (Lifecycle Bellman decomposition).** Assume that $0\le\gamma\le1$, the kernels and rewards are measurable, Bayes updates are well defined, and the finite-horizon values are integrable. For every belief-state $(b,s)$ and action $a$,

$$
Q_t((b,s),a)=\ell_t(b,s,a)+\gamma A_t^a(b,s)+\gamma I_t^a(b,s).
\tag{7}
$$

Consequently, the keep--archive lifecycle contrast satisfies

$$
\boxed{
\Delta_t
=\Delta_t^{\rm imm}
+\gamma\Delta_t^{\rm access}
+\gamma\Delta_t^{\rm info}
},
\tag{8}
$$

where $\Delta_t=Q_t(K)-Q_t(A)$ and each superscript denotes the corresponding keep--archive difference.

**Proof.** From (6), $C_t^a=A_t^a+I_t^a$ by definition. Substituting this identity into (4) proves (7). Subtracting the archive identity from the keep identity yields (8). Equivalently, (6) follows by applying the tower property along filtration (2): first condition on the next physical state, then integrate the evidence posterior. $\square$

The algebra is deliberately simple. The content is the accounting contract: future candidate exposure and workspace crowding belong to $\Delta^{\rm access}$; only evidence refinement conditional on the same next state belongs to $\Delta^{\rm info}$. Calling their sum ``information value'' would make a Blackwell comparison invalid whenever keep and archive induce different state kernels.

### 3.3 Theorem 2: score sufficiency and unavoidable fiber regret

Let $X_t$ and the score codomain $\mathcal Z$ be standard Borel spaces, let $S_t:X_t\to\mathcal Z$ be measurable, and assume that $\Delta_t:X_t\to\mathbb R$ is measurable. A score is *zero-action-sufficient* if an $S_t$-measurable rule reproduces the keep region $\{x:\Delta_t(x)\ge0\}$ under the current cost contract. It is *uniformly cost-sufficient* if this property holds after every scalar cost shift $\lambda\in\mathbb R$, with keep region $\{x:\Delta_t(x)\ge\lambda\}$. The second requirement is stronger: it tests whether the score preserves the action-value magnitude needed when storage, latency, or risk prices change.

**Theorem 2 (Score sufficiency iff lifecycle-value measurability).** The score $S_t$ is zero-action-sufficient if and only if $\{x:\Delta_t(x)\ge0\}\in\sigma(S_t)$, equivalently if the optimal zero-threshold action is constant on every score fiber. It is uniformly cost-sufficient if and only if there exists a measurable function $g_t$ such that

$$
\Delta_t(x)=g_t(S_t(x))
\quad\text{for all }x\in X_t.
\tag{9}
$$

If two states $x_1,x_2$ lie in the same score fiber but have different lifecycle contrasts, $S_t$ is not uniformly cost-sufficient, although it may still select the current action when their signs agree. If their contrasts have opposite signs,

$$
d_1:=\Delta_t(x_1)>0>\Delta_t(x_2)=:-d_2,
\tag{10}
$$

then no score-only rule is optimal in both states. Among randomized score-only rules, the minimax action regret on this fiber is

$$
\inf_{p\in[0,1]}
\max\{(1-p)d_1,pd_2\}
=\frac{d_1d_2}{d_1+d_2}>0.
\tag{11}
$$

The same value is the Bayes regret under the least-favorable two-point prior

$$
\pi^*(x_1)=\frac{d_2}{d_1+d_2},
\qquad
\pi^*(x_2)=\frac{d_1}{d_1+d_2}.
\tag{12}
$$

**Proof.** Zero-action sufficiency is equivalent to the keep region being an inverse image under $S_t$, which is exactly $\{\Delta_t\ge0\}\in\sigma(S_t)$. This implies constancy on every score fiber. Conversely, if the Borel keep region is fiber-constant, it and its complement are saturated; their images under $S_t$ are disjoint analytic subsets of $\mathcal Z$. Lusin separation supplies a Borel set separating those images, whose inverse image is exactly the keep region. For uniform sufficiency, if (9) holds, the rule keeps exactly when $g_t(S_t(x))\ge\lambda$. Conversely, uniform cost sufficiency implies that $\{x:\Delta_t(x)\ge q\}\in\sigma(S_t)$ for every rational $q$. Rational upper level sets generate the Borel sigma-algebra on $\mathbb R$, so $\Delta_t$ is $\sigma(S_t)$-measurable. The Doob--Dynkin factorization on standard Borel spaces gives (9).

For (11), a rule must use the same keep probability $p$ at $x_1$ and $x_2$. Its regrets are $(1-p)d_1$ and $pd_2$. Equalizing them gives $p=d_1/(d_1+d_2)$ and the stated minimax value. Under (12), its Bayes regret is

$$
\frac{d_2}{d_1+d_2}(1-p)d_1
+\frac{d_1}{d_1+d_2}pd_2
=\frac{d_1d_2}{d_1+d_2}
$$

for every $p$, proving least favorability. $\square$

**Corollary 2.1 (Approximate sufficiency on score fibers).** Define the closed compatible contrast interval on score fiber $z$ by

$$
L_t(z)=\inf_{x:S_t(x)=z}\Delta_t(x),
\qquad
U_t(z)=\sup_{x:S_t(x)=z}\Delta_t(x),
\tag{13}
$$

and assume that its endpoints are finite and measurable. A non-crossing fiber admits a zero-regret deterministic action; if $L_t(z)=U_t(z)=0$, every mixture has zero regret. On a genuinely crossing fiber $L_t(z)<0<U_t(z)$, the score-only rule that keeps with probability

$$
p_t^*(z)=\frac{U_t(z)}{U_t(z)-L_t(z)}
$$

has minimax action regret

$$
R_t^*(z)=
\frac{U_t(z)(-L_t(z))}{U_t(z)-L_t(z)}
\le\frac{U_t(z)-L_t(z)}{4}.
\tag{14}
$$

Hence score-fiber oscillation at most $\varepsilon$ implies a globally $\varepsilon/4$-minimax randomized score-only rule. Exact measurability is the zero-oscillation case, and the earlier interval minimax rule is the single-fiber specialization.

**Proof.** On a genuinely crossing fiber, a keep probability $p$ incurs endpoint regrets $(1-p)U$ and $p(-L)$. Equalizing them yields the displayed $p_t^*$ and $R_t^*$. With $a=U>0$ and $b=-L>0$, $ab/(a+b)\le(a+b)/4$. Non-crossing and zero-width tie fibers have zero regret directly. $\square$

**Agent-kernel consequence.** Equation (8) turns Theorem 2 into a falsifiable Agent-memory statement. Suppose $S_t(x_1)=S_t(x_2)$ and the immediate contrast is the same, but the unencoded future-kernel gaps

$$
J_t(x_i)=\Delta_t^{\rm access}(x_i)+\Delta_t^{\rm info}(x_i)
\tag{15}
$$

differ. Then $\Delta_t(x_1)-\Delta_t(x_2)=\gamma[J_t(x_1)-J_t(x_2)]$, so the score fails (9). If the two totals cross zero, the positive regret bound (11) follows. Thus an accurately estimated association, relevance, or one-step retrieval score is still insufficient whenever persistent authorization changes unencoded candidate, crowding, evidence, or recovery kernels within one score fiber.

**Proposition 2.2 (Dynamic score quotient / Agent control homomorphism).** Let $X_u$ be the complete post-observation belief-state space, let the action set be finite, and let $T_u^a(dx'\mid x)$ be the next-belief-state kernel after both the physical transition and evidence update. For every $u=t,\ldots,H+1$, let $\phi_u:X_u\to Z_u$ be a standard-Borel quotient map. If there exist measurable quotient rewards and kernels such that

$$
\ell_u(x,a)=\bar\ell_u(\phi_u(x),a),
\qquad
(\phi_{u+1})_\#T_u^a(\cdot\mid x)
=\bar T_u^a(\cdot\mid\phi_u(x)),
$$

and $V_{H+1}=\bar V_{H+1}\circ\phi_{H+1}$, then backward induction gives

$$
Q_u(x,a)=\bar Q_u(\phi_u(x),a),
\qquad
V_u(x)=\bar V_u(\phi_u(x))
$$

for every remaining stage. Hence a quotient-only Bayes-optimal policy exists and every keep--archive contrast factors through $\phi_u$. Conversely, for $\gamma>0$, if one-step action-value factorization is required for every bounded measurable quotient terminal payoff, equality of the push-forward kernels is necessary: otherwise a Borel set separating the two probability measures supplies an indicator payoff with different action values.

This is the horizon-wide Agent-specific condition. Candidate/state transitions, workspace competition, evidence/recovery channels, and continuation belief effects need not be action-independent, but their action dependence must be retained by the quotient. Theorem 2 remains the exact fixed-task iff; Proposition 2.2 prevents a fixed-task cancellation from being misreported as a sufficient Agent state representation.

**Corollary 2.3 (Value-separating signed kernels).** For two states $x_1,x_2$ on one current score fiber, define signed quotient kernels $\nu_i=(\phi_{t+1})_\#T_t^K(\cdot\mid x_i)-(\phi_{t+1})_\#T_t^A(\cdot\mid x_i)$. Let $\mathcal V_{t+1}$ be the bounded measurable continuation values realizable by the admissible future reward/control class. If $\gamma>0$ and some $v\in\mathcal V_{t+1}$ gives $h_i=\int v\,d\nu_i$ with $h_1\ne h_2$, choose the same immediate contrast $d=-\gamma(h_1+h_2)/2$ in both states. Then

$$
\Delta_t(x_1)=\frac{\gamma}{2}(h_1-h_2)
=-\Delta_t(x_2)\ne0.
$$

Thus any unencoded signed keep--archive candidate, workspace, scope/version, or recovery difference that is separated by an admissible continuation value yields a same-score opposite-action construction. If the task class is closed under all bounded measurable quotient terminal payoffs, $\nu_1\ne\nu_2$ alone suffices because Borel indicators separate signed measures. Kernel differences orthogonal to every realizable value are decision-equivalent for that task class. Whether a fixed real task already crosses zero remains empirical.

**Future-kernel-rich classes.** Assume $\gamma>0$, fix an immediate contrast $d$ and $\eta>0$. Call a model class $(S_t,d,\eta)$-future-kernel-rich if it contains two compatible states $x_+,x_-$ on one score fiber with the same immediate contrast $d$, while the omitted future-kernel functionals in (15) satisfy

$$
J_t(x_+)\ge\frac{-d+\eta}{\gamma},
\qquad
J_t(x_-)\le\frac{-d-\eta}{\gamma}.
$$

Equation (8) then gives $\Delta_t(x_+)\ge\eta$ and $\Delta_t(x_-)\le-\eta$, so (11) lower-bounds every score-only randomized rule's worst-case regret by $\eta/2$. This is a reusable model-class condition on persistent access/evidence/recovery kernels omitted by the score; whether a real Agent class satisfies it is an empirical question, not a theorem consequence.

**Explicit witness.** Let $\gamma>0$, let $\theta\in\{-1,+1\}$ have prior $1/2$, and let the next decision earn $R$ when it identifies $\theta$. In $x_1$, keep exposes a perfectly identifying future signal whereas archive yields a constant signal, giving $J_t(x_1)=R/2$. In $x_2$, a scope mismatch or workspace constraint makes both actions yield constant signals, giving $J_t(x_2)=0$. Give both states the same current score and immediate contrast $-\gamma R/4$. Then

$$
\Delta_t(x_1)=\gamma R/4>0,
\qquad
\Delta_t(x_2)=-\gamma R/4<0.
\tag{16}
$$

This witness disappears when the action-dependent future kernel is removed. Its source is therefore the Agent lifecycle mechanism, rather than Bayesian uncertainty alone.

### 3.4 Theorem 3: conditional value of recoverability

The access and information terms can be compared separately only under an explicit kernel contract. Fix $(b,s)$ and suppose keep and archive induce the same next-state kernel for $b$-almost every $\theta$. They then induce the same next-state marginal and the same state-level posterior $b^{s'}$. For almost every $s'$, let $Z$ be the keep observation and $O$ the archive observation. Keep *conditionally Blackwell-dominates* archive if there is a $\theta$-independent garbling kernel $G_{s'}$ such that

$$
P_A^O(do\mid s',s,\theta)
=\int G_{s'}(do\mid z,s)P_K^O(dz\mid s',s,\theta).
\tag{17}
$$

If archive is followed by a paid probe, its result is included in $O$; evidence available without that probe remains in $Z$. Every probe or restore price is recorded in the Bellman reward/cost ledger when incurred and is never absorbed into the experiment ordering. Differences in candidate regeneration or workspace occupancy are excluded from (17) and remain in $\Delta^{\rm access}$.

For general action-dependent state kernels, define the continuation value difference

$$
\operatorname{VoR}^{\rm cont}_{t,K:A}
:=\gamma\left(C_t^K(b,s)-C_t^A(b,s)\right)
=\gamma\,\mathbb E_{\theta\sim b,(s',o)\sim\mathsf K_K(\cdot\mid s,\theta)}[V_{t+1}(b^{K,s',o},s')]
-\gamma\,\mathbb E_{\theta\sim b,(s',o)\sim\mathsf K_A(\cdot\mid s,\theta)}[V_{t+1}(b^{A,s',o},s')].
$$

This quantity is not sign-definite because it includes access-state and crowding effects. Under the common-state contract above, it equals the conditional information value $\operatorname{VoR}^{\rm info}_{t,K:A}:=\gamma(I_t^K-I_t^A)$, which is the quantity signed by Theorem 3(a).

**Theorem 3 (Recoverability: monotonicity and information-budget necessity).**

**(a) Conditional value.** Assume the common state-kernel condition above, conditional Blackwell dominance (17), and convexity of $V_{t+1}(\cdot,s')$ in the belief. Then

$$
\Delta_t^{\rm info}=I_t^K-I_t^A\ge0,
\qquad
\operatorname{VoR}^{\rm info}_{t,K:A}
=\gamma\Delta_t^{\rm info}\ge0.
\tag{18}
$$

The inequality, and hence $\operatorname{VoR}^{\rm info}_{t,K:A}$ for $\gamma>0$, is strict if a set of next states and archive observations of positive probability has a strict conditional Jensen gap,

$$
\operatorname{E}\left[V_{t+1}(b_Z^K,s')\mid O=o\right]
>
V_{t+1}\left(\operatorname{E}[b_Z^K\mid O=o],s'\right).
\tag{19}
$$

For a finite-horizon finite POMDP, convexity follows from the policy-tree representation: each fixed continuation policy has value affine in the belief, and the optimal value is their pointwise maximum. In that setting, a transparent sufficient condition for (19) is that the keep posterior support crosses continuation-policy regions, so no single continuation policy is optimal almost surely over that conditional support.

**Proof.** Couple the observations so that $O$ is generated by garbling $Z$. Bayesian posteriors satisfy

$$
b_O^A=\operatorname{E}\left[b_Z^K\mid O\right].
\tag{20}
$$

Conditional Jensen and convexity give

$$
V_{t+1}(b_O^A,s')
\le
\operatorname{E}\left[V_{t+1}(b_Z^K,s')\mid O\right].
\tag{21}
$$

Integrating over $O$ and the common next-state marginal yields $C_t^K\ge C_t^A$. The common state kernel also gives $A_t^K=A_t^A$, hence $I_t^K-I_t^A=C_t^K-C_t^A\ge0$. A positive-probability strict gap in (19) makes the integrated inequality strict. $\square$

**(b) Information-budget necessity.** Consider any adaptive lifecycle policy $\pi$ that, at a stopping time $\tau\le H$ of the canonical filtration, issues a persistent authorization $D\in\{K,A\}$. Let $R_\tau(\pi)$ denote the terminal action regret of that authorization: the remaining-lifecycle value gap between the better persistent action and $D$. Let $M_+$ and $M_-$ be two Agent worlds with the same pre-decision history, and hence zero initial-history KL and the same current score. On every authorization history of positive probability, suppose a mistaken archive in $M_+$ has action regret at least $d_+>0$, while a mistaken keep in $M_-$ has action regret at least $d_->0$.

For $u<\tau$, let $A_u$ be the diagnostic action and let $W_{u+1}$ be the complete observed increment after that action, including candidate, state-transition, probe, and restore observations. Define

$$
Y_\tau=(A_0,W_1,\ldots,A_{\tau-1},W_\tau,\tau),
$$

and let $T_\tau=(Y_\tau,D)$. Action selection, randomized stopping, and terminal authorization are generated by policy kernels shared across the two worlds; only the action-dependent environment law of $W_{u+1}$ differs. Pad the action/observation slots after $\tau$ with a world-independent absorbing symbol to obtain a fixed-$H$ measurable object. The common terminal decision kernel $\pi(D\mid Y_\tau)$ has zero conditional KL, so the KL of $T_\tau$ equals the KL of $Y_\tau$. Let $\mathbb P_+^\pi$ and $\mathbb P_-^\pi$ be the laws of this padded augmented transcript and define

$$
B_\pi=\operatorname{KL}(\mathbb P_+^\pi\Vert\mathbb P_-^\pi).
\tag{22a}
$$

Then every such policy satisfies

$$
\max\{\mathbb E_+R_\tau(\pi),\mathbb E_-R_\tau(\pi)\}
\ge
\frac{d_+d_-}{2(d_++d_-)}e^{-B_\pi}.
\tag{22b}
$$

If $\mathbb P_+^\pi\ll\mathbb P_-^\pi$ and the adaptive action kernel of the policy is the same in both worlds, the KL chain rule gives

$$
B_\pi
=\mathbb E_+^\pi\!\left[
\sum_{u<\tau}
\operatorname{KL}\!\left(
\mathsf K_{A_u,+}(\cdot\mid H_u)
\Vert
\mathsf K_{A_u,-}(\cdot\mid H_u)
\right)
\right].
\tag{22c}
$$

Thus an archived state that censors the distinguishing event contributes zero KL until a probe, restore, or another observation-generating action reopens the channel. More generally, if each temporary keep/exposure contributes at most $\kappa_K$ KL, each probe contributes at most $\kappa_P$, and every other pre-authorization action contributes zero conditional KL, then

$$
B_\pi\le \kappa_K\mathbb E_+N_K+\kappa_P\mathbb E_+N_P.
\tag{22d}
$$

In the symmetric case $d_+=d_-=d$, (22b) is $d e^{-B_\pi}/4$. If a wrong authorization persists for $L$ future tasks with per-task gap at least $\nu$, then $d\ge\nu L$: bounded recoverable information implies an $\Omega(L)$ lifecycle-regret lower bound. Conversely, for $0<r<d_+d_-/[2(d_++d_-)]$, driving this lower bound below $r$ requires

$$
B_\pi\ge \log\frac{d_+d_-}{2r(d_++d_-)}.
\tag{22e}
$$

**Proof of (b).** Because $D$ is included in the augmented transcript, $E=\{D=A\}$ is measurable. Bretagnolle--Huber applied to the two transcript laws gives

$$
\mathbb P_+^\pi(E)+\mathbb P_-^\pi(E^c)
\ge \tfrac12 e^{-B_\pi}.
$$

The two terms are the authorization-error probabilities in $M_+$ and $M_-$. Their regret contributions are at least $d_+\mathbb P_+^\pi(E)$ and $d_-\mathbb P_-^\pi(E^c)$ by the uniform branchwise gap assumption. Minimizing the larger weighted term subject to the displayed sum gives (22b). Applied to the padded fixed-horizon transcript, the relative-entropy chain rule yields (22c). The common initial history, diagnostic action-selection kernels, randomized stop/continue kernels, and terminal decision kernel contribute zero KL, as do the post-stopping absorbing factors. Only the action-dependent environment kernels before $\tau$ remain. The per-action bound (22d) follows by summing their conditional KL caps. If initial histories have different laws, their KL must be added to (22c). If absolute continuity fails, $B_\pi=+\infty$ and (22b) remains valid but vacuous. $\square$

**Corollary 3.1 (Priced recoverability frontier).** Let $\alpha=d_+d_-/[2(d_++d_-)]$. Suppose every pre-authorization action that reopens the distinguishing channel contributes at most $\kappa>0$ conditional KL and costs at least $c>0$, while all other actions contribute zero conditional KL. Let $N$ count these channel-opening actions, let $n=\mathbb E_+N$, and define total authorization loss relative to a world-informed immediate authorization by $\widetilde R_\tau=R_\tau+C_\tau$, where $C_\tau$ is cumulative diagnostic cost. Then

$$
\max_{w\in\{+,-\}}\mathbb E_w\widetilde R_\tau(\pi)
\ge
\max\{cn,\alpha e^{-\kappa n}\}
\ge
\frac{c}{\kappa}W_0\!\left(\frac{\kappa\alpha}{c}\right),
$$

where $W_0$ is the principal Lambert-$W$ branch. Indeed, (22b)--(22d) give the terminal-loss term and the expected diagnostic cost in $M_+$ is at least $cn$. Minimizing their maximum over $n\ge0$ equalizes them; $cn=\alpha e^{-\kappa n}$ is equivalent to $(\kappa n)e^{\kappa n}=\kappa\alpha/c$. Consequently, any target $r<\alpha$ for worst-world total authorization loss must satisfy

$$
n\ge\kappa^{-1}\log(\alpha/r),
\qquad
(c/\kappa)\log(\alpha/r)\le r.
$$

This is the Agent-specific no-free-recovery consequence: when persistent archive endogenously censors all non-diagnostic branches, reducing authorization error requires a priced action that reopens a KL-bearing channel. The Lambert-$W$ algebra is standard; the contribution is the lifecycle transcript contract that identifies which Agent actions carry information and what they cost.

Part (a) signs only the recoverability-information term; it does not imply that keep is globally optimal. Part (b) does not require a common state kernel and instead prices the entire action-dependent Agent transcript. It shows why a prior alone cannot repair self-censoring: without KL-bearing observations, the posterior odds cannot separate the two lifecycle worlds. By (8), a more informative keep action can still lose because of immediate storage/exposure cost or negative access value from workspace crowding. Conversely, recoverability overturns an immediate archive advantage exactly when

$$
\gamma(\Delta_t^{\rm access}+\Delta_t^{\rm info})
>-\Delta_t^{\rm imm}.
\tag{22}
$$

### 3.5 Theorem 4: architecture-agnostic lifecycle trichotomy

The belief-state results admit an implementation-independent capstone. Let $z\in\mathcal Z$ index a future task and let $\Omega$ be the standard-Borel space of complete future Agent transcripts, including queries, retrieved memories, LLM outputs, tool calls, state updates, and outcomes. For any operationally defined persistent memory intervention $a\in\{K,A\}$, let

$$
P^a(dy\mid x,z)
=\mathcal L(Y_{t:H}\in dy\mid x,\operatorname{do}(a),z),
\qquad
\nu_{x,z}=P^K(\cdot\mid x,z)-P^A(\cdot\mid x,z).
\tag{23}
$$

This definition covers external, retrieval, prompt, cache, adapter, or parameterized memory whenever retain/suppress/update is a well-defined intervention. Immutable base parameters without such an intervention are outside the keep/archive comparison. For bounded task utility $u$ and $0<\gamma\le1$, define

$$
\Delta_{z,u}(x)
=d_z(x)+\gamma\int_\Omega u(y)\,\nu_{x,z}(dy).
\tag{24}
$$

Assume the current contrast is score-visible, $d_z(x)=\bar d(S(x),z)$, and use a regular standard-Borel score quotient. Let $\mathcal U_z$ be a declared, uniformly bounded utility class containing the zero utility and separating the induced signed kernels: unequal relevant kernels are assigned unequal integrals by at least one $u\in\mathcal U_z$. The unit ball of bounded Borel utilities is separating, whereas a restricted natural-task class need not be. Uniform boundedness fixes the utility scale and makes the approximation target below finite whenever the immediate contrasts are also uniformly bounded.

**Theorem 4 (Architecture-agnostic lifecycle trichotomy).** Exactly one branch holds:

1. **Future-null:** $\nu_{x,z}=0$ for all $x,z$, so memory governance reduces to the immediate contrast.
2. **Non-null and lifecycle-complete:** some $\nu_{x,z}\ne0$, but $\nu_{x,z}$ is constant on every score fiber for every task. Then every $\Delta_{z,u}$ factors measurably through $S$, and the score is uniformly sufficient over the declared task class and all scalar cost shifts.
3. **Non-null and future-lossy:** there exist $x_1,x_2,z$ with $S(x_1)=S(x_2)$ but $\nu_{x_1,z}\ne\nu_{x_2,z}$. If $\mathcal U_z$ separates these kernels, some $u\in\mathcal U_z$ gives different lifecycle values. After the common midpoint cost shift

   $$
   \lambda^*
   =\frac{\Delta_{z,u}(x_1)+\Delta_{z,u}(x_2)}{2},
   \tag{25}
   $$

   every randomized score-only rule has two-state worst-case regret at least

   $$
   \boxed{
   \frac14|\Delta_{z,u}(x_1)-\Delta_{z,u}(x_2)|
   =\frac\gamma4
   \left|\int u\,d(\nu_{x_1,z}-\nu_{x_2,z})\right|
   >0}.
   \tag{26}
   $$

   If the original contrasts already have opposite signs, no cost shift is needed.

**Proof.** Either every signed kernel vanishes or some is nonzero. In the latter case, the kernels are either constant on every score fiber and task or an explicit same-score violation exists; hence the branches are exhaustive and mutually exclusive. Branch 1 follows from (24). In branch 2, fiber constancy, regular quotient factorization, and score-visible immediate cost make every contrast score-measurable, so Theorem 2 applies. In branch 3, separation supplies $u$ with $q_i=\int u\,d\nu_{x_i,z}$ and $q_1\ne q_2$. The immediate terms agree on the score fiber, so the lifecycle-value difference is $\gamma(q_1-q_2)$. Subtracting (25) creates symmetric gaps. Equation (11) then gives one half of the gap magnitude, which is (26). $\square$

This theorem does not assert that every LLM reads every memory or that every natural task values every transcript difference. It gives the stronger defensible universal statement: any task-universal score for a non-null intervention-defined memory channel must preserve the complete task-relevant signed future-transcript kernel.

**Corollary 4.1 (Task drift).** For $z\sim\mu$ with a jointly measurable utility selector $z\mapsto u_z$,

$$
\Delta_\mu(x)
=\int_{\mathcal Z}
\left[d_z(x)+\gamma\int_\Omega u_z(y)\,\nu_{x,z}(dy)\right]\mu(dz).
\tag{27}
$$

If the admissible drift family contains all point masses, uniform sufficiency over all $\mu$ implies pointwise sufficiency for every $z$; a jointly measurable pointwise factorization through $(S,z)$ conversely implies mixture factorization. Task drift enlarges the challenge class but is unnecessary for branch-3 failure.

**Lifecycle sufficient statistic.** Define

$$
x\equiv_{\rm LC}x'
\Longleftrightarrow
d_z(x)=d_z(x')
\ \text{and}\ 
\int u\,d\nu_{x,z}=\int u\,d\nu_{x',z}
\quad\forall z,\ u\in\mathcal U_z.
\tag{28}
$$

Then

$$
T_{\rm LC}^*(x):=[x]_{\equiv_{\rm LC}}
\tag{29}
$$

is the coarsest task-relative lifecycle sufficient information object in partition order. Any statistic sufficient for every declared task utility and scalar cost shift must refine this partition. A standard-Borel controller-state representative additionally requires a smooth equivalence relation, for example a countable determining family. If the utility class contains the unit ball of bounded Borel functions, the partition preserves exactly the immediate contrast and complete signed future-transcript kernel for every task. For an approximation $T$, define

$$
\varepsilon_{\rm LC}(T)
=\sup_{T(x)=T(x')}
\sup_{z,u\in\mathcal U_z}
|\Delta_{z,u}(x)-\Delta_{z,u}(x')|.
\tag{30}
$$

Corollary 2.1 gives per-task fiber-wise minimax action regret at most $\varepsilon_{\rm LC}(T)/4$ under finite measurable endpoints. Estimating a regular representation of $T_{\rm LC}^*$, or an auditable approximation with small $\varepsilon_{\rm LC}$, is therefore the target of the subsequent SQCAD framework. This is an information-loss claim, not a claim that a scalar representation is intrinsically insufficient.

### 3.6 Probe and defer as Bellman actions

Let a probe cost $c_P>0$, leave the current physical state unchanged, and produce an observation $Z$ before the next decision. Define

$$
\operatorname{EVI}_t(P)
=\mathbb E_Z[V_{t+1}(b^Z,s)]-V_{t+1}(b,s).
$$

Comparing its Bellman value with reversible defer gives

$$
Q_t^P>Q_t^D
\quad\Longleftrightarrow\quad
\gamma\operatorname{EVI}_t(P)>c_P.
\tag{31}
$$

This is the general decision rule. SQCAD's interval and sub-Gaussian certificates should be presented as computable sufficient conditions for (31), not as additional main theorems. Probe is globally optimal only after its value also exceeds keep and archive.

## 4. What the theory jointly establishes

Theorem 1 identifies the lifecycle terms that a memory-governance rule must price. Theorem 2 states exactly when a current score preserves that value and quantifies the unavoidable regret when an Agent-specific future kernel varies inside a score fiber. Theorem 3 signs the recoverability component under a valid conditional experiment comparison and lower-bounds authorization regret by the KL information that the Agent's action-dependent transcript preserves. Theorem 4 lifts these objects above any particular memory implementation, exhausts the future-null, lifecycle-complete, and future-lossy cases, and identifies the minimal statistic the framework must estimate. Together they support the following bounded claim:

> Persistent Agent-memory governance is not identified by current retrieval utility alone unless that score preserves the task-relevant signed future-transcript effect of authorization. Across intervention-defined LLM-Agent memory architectures, a score either governs a future-null channel, is lifecycle-complete, or admits a separating task/cost witness with strictly positive score-only regret. Recoverability has nonnegative conditional information value under Blackwell dominance; when persistent actions censor the distinguishing transcript, any policy must purchase enough KL-bearing exposure, probe, or restore evidence or incur a quantitative lifecycle-regret floor.

The framework does not claim that all scalar scores fail, that keep is generally preferable, or that real LLM traces satisfy the assumed kernels. Those are empirical questions.

## 5. Falsifiable empirical contracts

1. **Transition/observation audit.** Forced keep/archive paired rollouts must estimate changes in candidate exposure, workspace occupancy, scope/version compatibility, provenance, and restore success. This tests whether the system is genuinely inside the persistent lifecycle class.
2. **Score-fiber audit.** Within narrow bins of each baseline score, paired interventions must estimate $\Delta_t$. Heterogeneous signs instantiate Theorem 2's regret condition; homogeneous fibers are evidence in favor of score sufficiency.
3. **Recoverability intervention.** Holding immediate utility and workspace budget fixed, vary the restore/probe experiment and separately estimate $\operatorname{VoR}^{\rm info}$ and $\operatorname{VoR}^{\rm cont}$. Candidate and crowding effects must be reported separately.
4. **Certificate calibration.** The Gaussian or sub-Gaussian authorization subclass must be tested on held-out mechanism families for coverage, drift, and false authorization. Toy witnesses validate algebra, not real-Agent assumptions.

## Section outline

- Related work distinguishes decision-centric compression and heuristic memory control from sequential endogenous lifecycle kernels.
- The process definition fixes persistence, state variables, and the Agent execution filtration.
- Theorem 1 decomposes lifecycle value into immediate, access, and conditional information terms.
- Theorem 2 gives fixed-task score sufficiency iff measurability; Proposition 2.2 gives the horizon-wide quotient condition; Corollary 2.3 and the fiber result give opposite-action and minimax/Bayes regret consequences.
- Theorem 3 gives the conditional value of recoverability under a common-state Blackwell comparison and a general augmented-transcript KL necessity bound.
- Theorem 4 gives the architecture-agnostic trichotomy and defines the lifecycle sufficient statistic estimated by the framework.
- Probe/defer certificates are retained as computable corollaries, followed by empirical contracts.

## Assumptions or missing inputs

- A complete online citation check is pending because `CONTACT_EMAIL` is not configured. Offline output: `VERDICT-LINE: PASS: 0/7 verified, 0 errors, 0 warnings (0 checks skipped)`.
- The finite-POMDP policy-tree convexity statement is a sufficient route; any continuous-state version must retain convexity as an explicit assumption or provide a separate proof.
- The theory does not establish that the deployed Agent has action-dependent kernels. That requires the paired lifecycle audits listed above.
- Main-manuscript theorem numbers, abstract claims, appendix labels, and the claim--evidence matrix have been migrated; future edits must preserve their synchronized scope.

## Claim--evidence map

| Claim | Evidence | Status |
|---|---|---|
| Lifecycle value has three terms | Bellman definition plus tower-property accounting, Theorem 1 | proved under stated process contract |
| A score is uniformly cost-sufficient iff it preserves $\Delta_t$ | upper-level-set measurability plus Doob--Dynkin, Theorem 2 | proved on standard Borel spaces |
| A quotient score is sufficient across a finite horizon | reward factorization plus controlled belief-kernel push-forward equality, Proposition 2.2 | proved; real Agent quotient audit missing |
| A signed keep--archive kernel difference separated by an admissible continuation value admits opposite actions within one score fiber | Realizable separating value plus midpoint immediate contrast, Corollary 2.3; raw kernel inequality suffices only for a task class closed under all bounded terminal payoffs | proved relative to the admissible continuation-value class |
| Same-score opposite actions force positive regret | explicit two-state minimax and least-favorable Bayes calculation | proved for fixed-task crossing fibers |
| Recoverability information value is nonnegative | common-state conditional Blackwell coupling plus Jensen, Theorem 3 | $\operatorname{VoR}^{\rm info}$ proved nonnegative; $\operatorname{VoR}^{\rm cont}$ is not sign-definite |
| Adaptive authorization requires distinguishing information | augmented stopping transcript, weighted Bretagnolle--Huber, and adaptive KL chain rule | proved for terminal authorization regret under uniform branchwise gaps |
| Priced recovery has a nonzero cost--error frontier | per-action KL cap and direct diagnostic cost combined with Theorem 3(b), Corollary 3.1 | proved for the stated channel-opening action class; real per-action KL/cost audit missing |
| Every intervention-defined memory architecture falls into a future-null, lifecycle-complete, or future-lossy branch | exhaustive kernel trichotomy, separating task utilities, and two-state minimax, Theorem 4 | proved under regular quotient and score-visible immediate-cost conditions |
| The framework has a minimal target estimand | task-relative equivalence quotient $T_{\rm LC}^*$ and oscillation $\varepsilon_{\rm LC}$ | proved; practical estimator and real-task calibration remain open |
| SQCAD differs empirically from contextual memory compression | paired Agent transition/observation audit | needs evidence |
| Certificate subclass transports to real LLM traces | held-out coverage and drift tests | needs evidence |
