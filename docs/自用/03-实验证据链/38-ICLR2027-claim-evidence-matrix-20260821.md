# ICLR 2027 Claim--Evidence Matrix（2026-08-22 general-theory migration）

> **Second theory audit (2026-08-22).** The general continuation quantity is now named `VoR^cont = gamma(C^K-C^A)` and is explicitly sign-indefinite when candidate/state or workspace kernels differ. The Blackwell result signs only `VoR^info = gamma(I^K-I^A)` under the common-state contract. A dynamic score-quotient proposition has been added as an Agent-specific horizon-wide sufficient route; its converse is stated only for universal action-value factorization over bounded terminal utilities and action-separating reward perturbations.

> **Architecture-agnostic closure (2026-08-22).** G4 now exhausts future-null, lifecycle-complete, and future-lossy intervention-defined memory channels. Its positive-regret conclusion is conditional on a score-visible immediate contrast, $0<\gamma\le1$, a regular quotient, and a uniformly bounded separating utility class. It proves cost-uniform failure through a midpoint shift; fixed-cost failure still requires unshifted opposite signs. The resulting estimand is $T_{\rm LC}^*$ or an approximation with small $\varepsilon_{\rm LC}$.

> 用途：把论文声称、代码实现、实验工件和允许的措辞绑定在一起。`proved` 只表示在明确限定的数学类上有证明；`measured` 表示在预注册合同和声明样本上直接测量；`proxy` 表示论文机制替代或层级替代；`smoke` 只证明路径可运行；`missing` 表示不能写成结果。任何主表数字必须能回到本表的 `[实验]` 工件和字段。

## 1. 理论主张

> **2026-08-22 theory migration:** 主文理论改为 G1--G3 三条基础定理加 G4 架构无关总括定理。旧 Theorem 1--13 不再作为并列主贡献，而是作为 construction、restricted proposition、interval corollary 或 certificate subclass。此前 constant-regret restore matching claim 继续撤回；所有旧 one-sided restore 数字只作诊断。

### 1.1 三条基础定理与一个总括定理

| ID | 论文主张 | 限定范围 | 证据 | 状态 | 当前允许措辞 | 仍缺什么 |
|---|---|---|---|---|---|---|
| G1 | persistent action value 可按 canonical Agent filtration 分为 immediate、access/state transition 和 conditional information/recoverability 三项 | 有限时域；kernel 可测；Bayes update 良定义；candidate/workspace/scope/recovery 进入 next state，evidence 在其后观察 | `19-Agent-Lifecycle-Belief-Control-一般理论-20260822.md` 定理 A；`42-ICLR2027-General-Theory-Section-Draft-20260822.md` Theorem 1；`lifecycle_belief_theory.py::lifecycle_contrast`；专项测试 | proved accounting identity + finite witness | “一般 Bellman 工具下的 Agent lifecycle accounting contract；三项之和与 filtration 表示无关，access/info 分账依赖固定执行顺序” | 真实 Agent trace 需要 transition/observation audit；不得声称发明 Bellman equation |
| G2 | 固定成本的 score action-sufficiency iff 最优动作集合在 score 上可测；对所有 cost shifts 统一充分 iff 完整 lifecycle contrast 对 score 可测；逐时刻 reward factorization 与 controlled quotient-lumpability 给出 horizon-wide score homomorphism；同 fiber 的 signed keep--archive kernel 差异若被至少一个 admissible continuation value 分离，则可构造相反最优动作 | 标准 Borel belief-state；二元 keep/archive；动态命题要求每个 future stage 的 quotient map；signed-kernel 结论是相对于可实现 continuation-value 类的存在性结论；只有任务类对所有 bounded measurable quotient terminal payoffs 闭合时，kernel 不同本身才充分；近似结果另要求 fiber endpoints 有限且可测 | 定理 B/C、命题 B.2a、推论 B.2b/B.3；英文 Theorem 2/Proposition 2.2/Corollaries 2.1/2.3；`finite_score_quotient_violations`、`value_separating_signed_kernel_contrasts`；32 项 lifecycle 专项测试中的对应回归 | proved + finite audit witnesses | “同 score fiber 符号反转导致严格正 regret；fiber 振幅至多 `epsilon` 时随机 score-only minimax regret 至多 `epsilon/4`；horizon-wide score state 必须对 Agent kernel 构成 control homomorphism” | 必须在真实 baseline score fibers 中估计 contrast 异质性，并审计 quotient push-forward kernels 与可实现 continuation values；四个直观机制条件不是固定任务下分别必要 |
| G3 | (a) 共同 state kernel 下，keep 的 conditional experiment Blackwell 支配 archive 时，recoverability information value 非负，严格 Jensen gap 时严格为正；(b) 对一般 action-dependent Agent kernel，任何序贯授权策略的 worst-world terminal authorization regret 由 padded augmented transcript 的 KL 预算下界；priced frontier 进一步合并 channel-opening action 的 KL cap 与显式成本 | (a) common next-state kernel 或相同 state-level posterior；garbling 与 latent world 无关；continuation value 对 belief 凸；(b) 两个兼容世界具有相反最优授权与正 action gaps，同一 adaptive policy，transcript 包含 actions/stopping/terminal decision，transcript laws 可比较；priced frontier 要求每个 channel-opening action 的 KL 上界和成本下界 | 定理 D、推论 D.3；英文 Theorem 3/Corollary 3.1；投稿级 proof appendix `45-*`；`recoverability_regret_lower_bound` / `required_recoverability_kl` / `priced_recoverability_regret_floor`；binary Blackwell 与 KL-budget 专项测试 | proved conditional monotonicity + general two-world information lower bound + priced cost--error frontier + finite witnesses | “Blackwell/Jensen/Bretagnolle--Huber/Lambert-W 均为标准工具；Agent-specific 增量是 persistent action 决定哪些 transcript 分支提供零 KL、哪些 probe/restore 动作以显式成本重新购买信息；总动作仍加 immediate/access/crowding/cost” | 真实 recoverability intervention、per-action conditional KL/cost audit、共同 state-kernel/strict-gap evidence；不得声称标准信息不等式或 Lambert-W 优化原创 |
| G4 | 任意具有持久 keep/archive 干预语义的 memory channel 恰落入 future-null、non-null lifecycle-complete 或 non-null future-lossy 三分；第三分支若有 admissible utility 分离同 score signed kernels，则存在 task/cost witness 使任意 score-only 随机规则承担严格正 regret；$T_{\rm LC}^*$ 是对声明任务类与所有 scalar cost shifts 的最粗 lifecycle information partition | jointly measurable intervention kernels；$0<\gamma\le1$；即时 contrast 对 score 可见；regular standard-Borel quotient；utility class 包含零函数、统一有界并对相关 kernels 分离；$\varepsilon_{\rm LC}/4$ 是逐任务、逐成本的 fiber-wise 界；实现 standard-Borel controller state 另需 smooth quotient/可数 determining family | 定理 E；英文 Theorem 4；proof appendix Theorem A.4；`finite_lifecycle_trichotomy`、`task_universal_shifted_regret`；32 项 lifecycle 专项测试 | proved conditional exhaustive trichotomy + minimal partition estimand + finite regression | “每个 intervention-defined 架构都属于三分之一；non-null 不自动等于失败；future-lossy 在 separating task/cost challenge 下产生正 regret；后续框架估计 $T_{\rm LC}^*$ 的 regular representation 或控制 $\varepsilon_{\rm LC}$” | 真实系统实验只负责定位分支、验证自然任务分离性并估计 $\varepsilon_{\rm LC}$；不得声称所有 LLM、所有自然任务、固定成本必然失败或标量维数天然不足 |

### 1.2 构造、受限命题与证书子类

| ID | 论文主张 | 限定范围 | 证据 | 状态 | 当前允许措辞 | 仍缺什么 |
|---|---|---|---|---|---|---|
| A1 | 观测等价世界可以有相反的 persistent keep/archive 最优动作 | 旧 Theorem 1 的双记忆 SCM、共同暴露、明确 `do` 语义 | `[代码]` `src/sqcad/decision_identification_theory.py`；`[实验]` `results/necessity_counterexamples.json` | proved + measured construction | “G2 的 observational score-fiber witness” | 不得外推为所有日志都不可识别 |
| A2 | query-local exposure effect 不足以决定生命周期动作 | 旧 Theorem 2 的 crowding/bridge 构造 | `[代码]` `src/sqcad/decision_identification_theory.py` | proved + controlled construction | “G2 的 access-kernel witness” | 真实系统中的因果效应仍需独立干预 |
| A3 | 无恢复通道的 committed policy 有线性后悔；单世界 Bernoulli restore 仅作机制诊断 | archived-committed 类；`p_arch=0`；独立 probe/restore 显式模型 | `self_obscuring_ablation.py`；对应结果 | restricted proposition + diagnostic | “无恢复 committed 子类为 `Theta(T)`” | 不得外推任意 Agent policy |
| A4 | 完全删失、无恢复 committed 子类的 faithful-reduction separation | world-independent observation map；无 restore/probe | `reduction_closure.py`；严格结果工件 | restricted proposition | “仅对 censored-committed faithful reduction 子类成立” | 不能外推所有 reduction |
| A5 | interval minimax 与 probe/defer 比较 | 二动作 compatible interval；显式 worst-case criterion | 旧 Theorem 5--6；`decision_identification_theory.py` | G2/Corollary 2.1 specialization | “单 score fiber 的 minimax 投影” | Bayes-optimal probe 仍需完整 Bellman value |
| A6 | fixed-sample probe 门槛与固定门槛恢复成本 | Gaussian two-point / fixed-threshold subclasses | `reduction_closure.py`；专项测试 | restricted propositions | “可计算 certificate subclass” | 不得外推 arbitrary sequential policy |
| A7 | honest interval authorization 控制 confident error | honest coverage；二元动作；估计器另需显式 regularity | 旧 Theorem 9--10；严格结果 | certificate-conditional corollary | “coverage contract 下的 authorization guarantee” | 真实 LLM coverage 和完整 observational DR 未实现 |
| A8 | safe archived-committed 类的恢复总成本 matching order | `Safe(H,delta)`；双侧证书；有限 horizon | safe-recovery 理论、代码和测试 | certificate subclass | “同一安全类内的 total-cost order” | 需要独立机制族 scaling 实验 |
| A9 | anytime/stitched Qualification certificate | conditional sub-Gaussian probes；margin-separated | safe-recovery theory；Qualification path tests | certificate subclass + implementation bridge | “contract 下 wrong authorization $\le\alpha$” | 未验证 raw LLM certificate contract |
| A10 | unresolved margin 的信息下界 | $\tau=\pm\epsilon$ 两点 | margin lower-bound helper/tests | G2 near-boundary specialization | “证据需求按 `epsilon^{-2}` 发散” | 不等于所有任务上 abstention 全局最优 |

## 2. 公开数据和统一合同

| ID | 论文主张 | 数据/样本 | 证据 | 状态 | 当前允许措辞 | 仍缺什么 |
|---|---|---|---|---|---|---|
| P1 | 统一合同可以在同一 chronological stream、reader、budget 和成本下比较 policy | LongMemEval-S、LoCoMo；冻结合同代码 | `src/sqcad/public_unified_contract.py`；`tests/test_unified_baseline_runner.py`；`results/public_unified_contract.json` | measured | “合同层比较已完成” | 不能把合同层 reader 分数当成原论文 QA 分数 |
| P2 | SQCAD 的公开集优势主要是治理/存储 trade-off，不是静态检索排序全面领先 | LME-S 500 / LoCoMo 10；BM25、dense、SQCAD rows | `results/public_unified_contract.json`；`results/public_dense_0.6B.json`；33- 报告 | measured with tier-B | “在当前合同和模型替代层上观察到 trade-off” | 需要具名系统完整 generation 才能挑战端到端方法 |
| P3 | Qwen3-Embedding-0.6B/8B 代表相应检索层替代 | dense cache / CUDA timing | `results/public_dense_0.6B.json`、`public_dense_8B.json`、`contract_wallclock_gpu_20260821.json` | proxy/measured | “tier-B embedding retrieval proxy” | 不得称为 SimpleMem/ActMem 完整复现 |
| P4 | LongMemEval-S QA 端到端可复现 | 官方 QA evaluator | `results/locomo_official_qa_*.json` 仅 LoCoMo；LME 官方 QA 需要外部 API | missing for LME | “LME QA 层未复现；只报告检索/合同层” | API 或等价本地 reader、完整核验 |
| P5 | LoCoMo F1 可以作为公开端到端指标 | 官方 scorer + frozen predictions | `tools/run_locomo_official_scorer_portable.py`；`results/locomo_official_qa_*.json` | measured for available rows | “LoCoMo official token-F1 for rows with valid predictions” | 具名系统完整 QA 预测仍需补齐 |

## 3. 自建机制数据

| ID | 论文主张 | 数据/样本 | 证据 | 状态 | 当前允许措辞 | 仍缺什么 |
|---|---|---|---|---|---|---|
| S1 | 反事实 keep/archive 生命周期合同能检验错误遗忘和恢复 | LifecycleBench，paired same-source episodes | `src/sqcad/lifecycle_bench/`；`results/lifecycle_bench/manifest.json`；`results/lifecycle_restore_strict_20260821.json` | measured internally | “受控机制基准支持内部效度” | 真实纵向干预和外部效度 |
| S2 | recovery 在 recurring regime shift 降低 false forgetting | 固定场景 + 随机世界种子；预注册成本 | `results/lifecycle_restore_strict_20260821.json`；37- §4 | measured internally | “在该构造上观察到恢复收益” | 不得写成公开数据泛化结论 |
| S3 | sentinel/预算/谱系机制有可触发差异，且 badcase 可驱动成本门控修改 | 独立半合成触发世界；64 个独立 seeds；同一 candidate stream 配对 | `src/sqcad/minimal_framework_challenge_benchmark.py`；`results/minimal_framework_challenge_triggered_guarded_v2_20260821.json`；实验报告 39- | measured internal paired ablation | “recoverability/adaptive-budget 在该构造上收益显著；无条件 sentinel 产生负效用 badcase，full-cost sentinel gate 恢复该损失并减少探测成本” | 仅内部机制世界；不外推公开数据或真实用户流量；需跨机制族的独立触发集 |
| S4 | SQCAD 修改在多个机制家族上稳定优于基线 | 机制家族和 episode-level rows | `results/public_v2_rule.json`、`results/locomo_qa_v2/`、33- §3 | partial / unit sensitivity | “只对通过预注册统计单元的方向作结论” | bucket-level power、独立随机化和完整 paired replay |

## 4. 具名基线和闭源机制替代

| ID | 基线 | 实现/指标 | 状态 | 论文允许写法 | 进入主表门槛 |
|---|---|---|---|---|---|
| B1 | SimpleMem | 官方快照 + Qwen3-8B generation + Qwen3-Embedding-0.6B；合同 LME-S `n=1`：hit 1.0、recall 0.6667、storage 22,767、66 LLM calls | smoke only | “open-weight mechanism path smoke” | 至少预注册 LME-S/LoCoMo 子集，完整 QA、失败窗口、SHA 和成本字段 |
| B2 | ActMem | 无官方代码；`tools/repro_named_actmem.py` 按论文 §3.1–3.4 机制实现；云端单 trace 完成 550/550 事实提取请求后卡在 embedding/PMI 后处理，未写出质量 JSON（`results/cloud_actmem_20260821/actmem_resource_limit_20260821.json`） | partial resource-limited path; no quality result | “paper-mechanism proxy path reached generation but remains partial” | 需要一条完整可审计 trace；应降低候选对复杂度或改用更大显存后重新预注册，且完成 QA/CI/成本字段 |
| B3 | Oblivion | 官方代码/规则审计 | verified rule-level | “official rule/path verification” | 与统一合同输入输出逐字段核对 |
| B4 | Memory Worth / CMI / DeMem / Trivium / GovMem | Memory Worth/DeMem/Trivium/GovMem 无官方可执行仓库；CMI 官方仓库存在但当前未运行；GovMem 不可迁移到 access-time contract | proxy, control, or not transportable | “signal-substituted proxy / estimand control / not transportable” | 不得把简化控制数字写成五个论文系统结果 |
| B5 | FadeMem | 视频域方法 | not transportable | 只放 related work/limitations | 不能转成 Agent Memory 数字 |

## 5. ICLR 5/5/5 gates

| Gate | 5/5 需要什么 | 当前判定 |
|---|---|---|
| Correctness | 三条基础定理、G4 总括定理与附录子类限定清楚；主表只用直接测量；序贯/代理/单条冒烟不越权 | **内部条件化理论主线通过、外部置信未满**：G1--G4 证明与有限 witness 闭合；仍需独立数学复核，真实 Agent kernel 证据决定非空性与适用意义而非逻辑有效性 |
| Empirics | 强基线完整或明确不可迁移；公开集和自建集合同分层；badcase 驱动 paired ablation | **部分通过**：paired badcase replay 已有 64 个机制世界和 CI；SimpleMem/ActMem 完整质量行仍缺失 |
| Clarity | abstract、contribution、results、limitations 与本表逐条一致 | **理论文本通过、全稿仍需版面审计**：31/42/45 已同步 Theorem 4、$T_{\rm LC}^*$ 与边界；需在最终 LaTeX 中压缩符号并核对图表 |
| Overall | 可被独立研究者按 manifest 重跑并得到同一结论 | **未通过** |

## 6. 进入论文主表前的硬门槛

1. `n=1`、smoke、partial、proxy、not transportable 行不得进入 SOTA 主表。
2. 每个主表数字必须同时有：数据 hash、代码 commit/路径、配置、硬件、随机种子、输出 SHA 和评测脚本版本。
3. 任何“优于基线”的句子必须给出统计单元、CI、是否显著和成本口径；episode 重复不能替代机制实例独立性。
4. 任何理论结果必须标明是 G1--G3 foundational theorem、G4 architecture-agnostic synthesis，还是 fixed-sample、fixed-threshold、certificate/reduction subclass；后者不得重新包装为并列主定理。
5. 云端结果先回传本地并完成字段/SHA/语义检查；全部工件核对完毕前不关机。
