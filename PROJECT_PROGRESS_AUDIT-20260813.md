# SQCAD 项目进度审计（2026-08-13）

> 本审计回答三个问题：(1) 从哪些文献读出 research gap 假设，并转化为了哪些研究理念、工作与痛点；(2) gap 是如何被设计成可证伪命题并以实验证明立住的，为什么现有工作无法覆盖、基线工作是什么；(3) 定理形式化、证明、框架反推、条件充分性/必要性与框架成本收益分别由哪些实验支撑。
>
> 与 `docs/研究逻辑与理论证明/00-ResearchGap到充分性与必要性的完整实验逻辑线-20260813.md` 的关系：`00` 是**论证逻辑线**（每个主张的证据链），本审计是**进度台账**（完成度、阻塞、下一步）。理论推进路线见 `docs/研究逻辑与理论证明/13-形式化为真正理论空白的必要性证明方向-20260813.md`（P0–P4）。

---

## 一、问题 1：文献 → research gap 假设 → 研究理念、工作与痛点

### 1.1 文献分三层

| 层 | 文献 | 读出什么 |
|---|---|---|
| Agent Memory 治理直接工作 | Memory Worth、CMI、Oblivion、FadeMem、DeMem、SimpleMem、SAGE、MemAudit、GateMem、GovMem、ActMem、Trivium（11 篇已完成全文级核对，`实验证据链/10`） | 已有方法用时间衰减、频率、语义相关性、结果反馈、query-local 干预、写时显著性、决策压缩、事后归因管理记忆——但**各自的估计目标都不自动等于持久访问动作的生命周期价值** |
| 公开基准与外部轨迹 | LongMemEval（ICLR 2025）、LoCoMo（ACL 2024）、GoodAI-LTM、MemoryAgentBench | 评测侧重检索正确性与事实问答；缺少"记忆治理动作 → 未来策略价值"的因果评测协议 |
| 因果理论锚点 | Robins 1986（g-formula）、Jiang & Li 2016 / Kallus & Uehara（DR/OPE）、Hudgens & Halloran 2008（干扰）、Manski（部分识别）、Pearl & Bareinboim 2014（transportability）、Thomas & Brunskill 2016（safe policy improvement） | 通用估计机器齐备——**机器不是空白，treatment construction（把记忆管理变成可检验的因果问题）才是** |

### 1.2 从文献到 gap 假设（两步，严格区分假设与证明）

1. **文献驱动的假设**（`08-Gap1覆盖审计`）：现有常用代理（关联共现、query-local 效应、source 平均）可能不足以支撑持久访问生命周期决策——仅凭"已读工作未覆盖"不能推出"无法覆盖"，所以只是假设；
2. **升级为可证伪命题**（`11-形式化定理陈述与证明`）：固定 treatment（持久访问动作）、estimand（lifecycle value \(V_s^\pi(a)\)）、观测合同（候选/暴露/位置/预算/采纳/结局/版本/作用域）、失败判据（两个观测等价世界给出相反最优动作）→ Theorem 1/2 + Corollary 1。

### 1.3 转化为的研究理念与痛点

| 痛点（文献中观察到的） | 转化出的研究理念 | 落点 |
|---|---|---|
| 历史成功共现被策略生成暴露混杂（Memory Worth 自己报告的 hitchhiker 共检索不可区分） | 关联信号只提案、不授权 | Evidence 层与 Qualification 层分离 |
| CMI 类 query-local 效应精确正确仍可能做错生命周期决策（future candidate / budget / interference 未进入 estimand） | 持久访问动作是 treatment，局部效应只是后果链的一段 | Theorem 2 + Access 层 treatment 语义 |
| 写时治理（GovMem/SAGE）不覆盖访问时授权；衰减治理（Oblivion/FadeMem）无识别资格检验 | "写时资格 ≠ 访问时授权"，衰减触发证据需要资格 | Qualification 门输出 {point, bound, unresolved, mismatch} |
| 压缩治理（DeMem）的决策对象是下游答案质量而非持久动作价值；审计（MemAudit）是事后归因而非前瞻授权 | 决策中心视图 + 可撤回授权 | 成本合同 V 与资格→动作接口 |
| 最接近先验 Trivium 的 treatment 是预设 SCM 的 confounder 探针、无策略反馈候选流建模 | 探针是手段之一；识别意识是必经原则 | Theorem 4 + 识别路线分类学（`12` 文档） |

---

## 二、问题 2：gap 如何被设计实验证明立住；为什么现有工作无法覆盖；基线是什么

### 2.1 三个构造性反例（`01`/`02` 报告 + `gap_proof_experiments.py`）

| 命题 | 构造 | 关键数字 | 证明的 gap |
|---|---|---|---|
| A（Theorem 1） | 两 SCM 共享随机序列、完美共暴露：全字段 max diff = 0.0（25,000 行联合日志逐位一致），lifecycle 却为 +1650 / −1100 | Memory Worth 在 M₂ regret = 1100 | 观测日志在信息论层面无法识别 lifecycle value——换正确的因果估计器也失败 |
| B（Theorem 2） | 两条记忆 query-local 真 do-effect 精确相等（2.000），lifecycle 却为 −1784 / +1776 | CMI observational regret = 1784 | 局部效应**精确已知**也不足以做生命周期决策 |
| C（Corollary 1） | source 数据完全相同的两世界，target 机制不同 | target world 1 错误决策 regret ≈ 2.0 | source 平均不自动 transport |

**设计原理**：每个反例都让基线**拿到正确的因果答案**（公平性审查 S1 信息/S2 构造/S3 非稻草人/S4 正面无特权已验证）——失败发生在 **estimand 层**而非估计误差层，从而排除"基线实现得不好"的解释。Theorem 1/2 因此**不依赖基线 R3 复现状态**（机制级数学命题）。

### 2.2 为什么现有工作无法覆盖（三层）

1. **Estimand 层**：关联/局部/source-平均即使精确估计自己的目标，也不识别 lifecycle value 或其最优动作（Theorem 1/2/C）；
2. **Authorization 层**：现有方法输出排序、分数或直接动作，没有"识别资格 → 持久动作"的授权接口（点识别 / 不跨零界 / 未识别 / mismatch 四态区分）；
3. **系统比较层**：官方完整基线 R3 未完成（无 GPU、无 API key），故不声称"SQCAD 已超过所有现有系统"——只能声称校准版 A（机制级）/ B（结构级）/ C（审计级）（`实验证据链/09` 声称纪律）。

11 篇全文核对（`实验证据链/10`）确认：**没有任何一篇同时把持久访问动作定义为 treatment、把 lifecycle value 定义为 estimand、并显式处理策略生成的候选–暴露反馈，再以识别资格授权治理动作**（覆盖审计，不是数学证明）。

### 2.3 基线工作清单（复现门 R0–R3/M1，`05`/`03` 审计）

- **内部对照**（统一合同 18 行）：no_memory/keep_all/fifo/lru/recency/fixed_decay/frequency_decay/dense/rrf/bm25 + 治理传输（memory_worth/oblivion/fademem/simplemem/demem proxy 结构）+ trivium 探测层 + causal_item（CMI proxy）+ 框架行 risk_gated_decomp_abstract；
- **not_transportable 无数字**：SAGE、MemAudit、GateMem（公平迁移协议未定义，比较继续禁止）；
- **R3 阻塞**：Oblivion/SimpleMem 等官方完整复现（GPU/API key），解锁协议见 `09` §6。

---

## 三、问题 3：定理形式化、框架反推、充分/必要性、成本收益的实验设计

### 3.1 定理与验证总表

| 定理 | 内容 | 验证方式与关键数字 | 状态 |
|---|---|---|---|
| Theorem 1 | 观测等价、lifecycle 符号翻转（观测不可识别） | 命题 A：max diff 0.0、+1650/−1100、regret 1100 | ✅ 构造证明 + 代码验证 |
| Theorem 2 | 局部效应精确相等、lifecycle 相反（局部不充分） | 命题 B：Δ_do=2.000 相等、−1784/+1776、regret 1784 | ✅ 同上 |
| Corollary 1 | source 不自动 transport | 命题 C | ✅ 同上 |
| Theorem 3 | C1–C8（**可操作、可审计的充分授权条件族**，2026-08-13 更名）下协议/观测双路识别；条件失败输出 {point, bound, unresolved, mismatch} | Stage 1：bias≈MC 噪声、CI 12/12、自信错误 0、unresolved 恰为 neutral；Stage 2：五种违反全部被门捕获 | ✅ 充分方向已验证（观测路 lifecycle DR 尚为 g-formula 级） |
| Theorem 4 | 未识别类上 committing 规则最坏情况 regret ≥ \|τ₁\|\|τ₂\|/(\|τ₁\|+\|τ₂\|)、错误概率 ≥ 1/2；突破需拒绝或新证据 | 双世界实例：660 @ p=0.6；错误 ≥ 0.5；门控 0 | ✅ 证明 + 计算验证（两点构造版） |
| Theorem 4(c′)→审计性 | 拒绝触发必须可验证 | 论证成立但 13- 指出需独立形式化（authorization certificate：soundness/verifiability/non-triviality） | ⚠️ 待升级（P0） |
| Lemma A–D | C2/C3、C6、C7、C8 存在替代/退守路线（N1 不成立） | C6 bias 0.49/0.30 vs se 1.4；C7 bundle 8.97±1.12 vs 8.07；IV −0.003 vs 观测偏倚 +0.835；C8 +21.4 vs 当期 1.07 | ✅ 代码验证（**C1/C4/C5 未逐项处理，不声称全族不必要**） |

### 3.2 框架反推实验（`03`/`04` 报告）

识别条件逐条映射框架组件（`10-识别条件到框架设计`）：Evidence 层（日志完整性 C1/C4/C5、采纳分离、策略状态）← 命题 A 的不可识别来源；Access 层（持久动作语义、预算与共记忆）← 命题 B；Qualification 层（scope/version 门、overlap 检验、随机微干预）← C3/C8/Cor 1。**两阶段实验**验证：Stage 1 协议路线恢复 oracle（bias −0.47、CI 12/12、决策零错误）；Stage 2 逐条件违反全被门捕获为 unresolved/mismatch（C7 下盲门强制决策 regret 41.0、C3 下 83.4——弃权不是免费的，框架承诺的是"绝不做自信错误决策"）。

### 3.3 充分性与必要性的实验分工

- **充分性**（"C1–C8 满足 ⇒ 能识别"）：Theorem 3 + Stage 1 + g-formula/局部 DR 估计有效性实验（`04`：支持覆盖处恢复真值、支持缺失处可预言符号错误、DR 单误设低偏双误设失效、C6 使 DR 失效、界改写错误决策为 unresolved）；
- **必要性**（"可识别 ⇏ 必须满足完整 C1–C8"；"门控是必要的"）：Lemma A–D 替代路线（`necessity_counterexamples.py`）+ Theorem 4 下界；
- **关键边界**（`11` 报告用户修订后口径）：Lemma 只覆盖 C2/C3/C6/C7/C8；C7/C8 是治理粒度/estimand 退守；不能说"C1–C8 每一项都已被证明不必要"。

### 3.4 成本与收益实验（`07`/`08` 报告）

- **成本合同** V = Σγ^{t-1}[U − λ_tok·C_tok − λ_llm·C_llm − λ_probe·C_probe − λ_lat·C_lat − ρ_harm·R_harm] − ρ_ff·R_ff（λ_llm=0 如实标注）：SQCAD 默认/风险规避/延迟敏感区间最优（38.48）；对最优非探测基线 break-even λ_probe*=5.53（110× 默认）；探测预算受限（pb=0）领先 CMI +6.6；**保留的负面结果**：强制恢复在含害世界 V 38.62→8.73；**如实边界**：对配探测 CMI 的 V 领先 10-seed CI 下界恰为 0（不可显著区分）；
- **统计门**：采样单元=seed 的 studentized paired bootstrap（heavy-tail 0.9275 vs 正态 0.8745；D0 世界覆盖–n 斜率反转 0.79→0.92–1.00）；主表差值 CI 不跨 0；四件套 SHA-256 冻结（当前聚合哈希随最新内容重生成）。

---

## 四、进度台账

| 模块 | 状态 | 证据/代码 | 下一步 |
|---|---|---|---|
| Gap 反例（命题 A/B/C + 公平性审查） | ✅ 完成 | `01`/`02`、`gap_proof_experiments.py` | — |
| Theorem 3 充分性（两阶段 + 估计有效性） | ✅ 完成（含边界） | `03`/`04`、`identification_recovery_experiment.py`、`estimation_validity_experiment.py` | lifecycle 级完整 DR（长线） |
| 统一合同主表 + 基线审计 | ✅ 完成（R3 阻塞如实标注） | `05`（归档于草稿）、`03` 审计、`09` | R3 解锁升级协议 |
| 真实轨迹接地 + 半合成 | ✅ 完成（QA 层未复现） | `06`（归档）、`trace_grounded_runner.py`、`trace_semisynthetic_benchmark.py` | trace-grounded 主表（Gate 2.2） |
| 成本合同 + 负面结果 | ✅ 完成 | `07`（归档）、`cost_contract_experiment.py` | P2：把 commit/defer/probe 成本并入决策定理 |
| 统计与工程门 | ✅ 完成 | `08`（归档）、`bootstrap_ci.py`、`freeze_four_piece.py` | 内容更新后重新生成冻结清单 |
| 必要性（Lemma A–D + Theorem 4） | ✅ 完成（两点构造版） | `11`、`12`、`necessity_counterexamples.py` | P0 修正 + P1 一般化 |
| 文献全文级核对 | ✅ 完成 | `10`、D 盘 audit 全文资产 | 审稿点名文献时按同法补核 |
| **P0 修正**（C6 隔离、IV lifecycle 化、C7/C8 语义） | ✅ 完成（certificate 形式化仍待） | `实验证据链/12` §1–2 | C6 隔离：协议 1.1914 逐位相同、观测对比按 (1−2ε) 稀释；lifecycle IV 误差 0.017 vs 偏倚 12.96 |
| **P1 一般决策识别定理**（R*(L,U)=U(−L)/(U−L)；安全提交 ⟺ 识别集不跨 0） | ✅ 完成 | `12` 定理文档 §3.6、`实验证据链/12` §3 | **Theorem 5 完整证明** + 计算验证（660 复现 @p*=0.6；决策识别非点识别实例 (500,1650) regret 0） |
| **P2 拒绝/探测成本边界** | ✅ 完成（数值级） | `实验证据链/12` §4 | C_probe<330 探测胜 commit、<170 胜 defer；与 Gate 4 λ_probe 参数对接仍待 |
| **P3 动态探索必要性**（Ω(T) 无探索 regret） | ⚠️ 数值落地、严格证明待做 | `实验证据链/12` §5 | self-confirming：无探测斜率 6.000=τ·p 精确线性；q=0.05 regret 12000→128 平台 |
| **P4 SQCAD 上界匹配** | ⚠️ 数值落地、minimax 严格证明待做 | `实验证据链/12` §6 | KL 下界 9.36 vs SQCAD 式停止规则 34.6（3.7× 同阶） |
| 外部 rollout（chronological future） | ⏸ 阻塞（模型端点） | `00 实验证据链` 未验证清单 | — |
| 论文写作（Introduction 规范稿等） | ✅ 已有草稿 | `07-Introduction规范稿` | 声称压缩最后做 |

**测试与工程状态**：全套 224 项测试通过；`results/`（gitignored）与 D 盘外部数据库同步；冻结清单 `freeze_manifest.json`（代码 40 + 配置 + 结果 21 + 报告 12）；GitHub 已推送（commit 7d964c8 起）。

---

## 五、阻塞清单

1. **R3 基线复现**：无 NVIDIA GPU、无 OpenAI/Anthropic/Azure/HF API key（环境事实，非省略）；
2. **外部 QA 层端到端**：GPT-4o-mini 端点（`06` 如实标注）；
3. **trace-grounded 主表**：`06` §7.1 下一步（无模型端点也可做，是最近的现实接地增量）；
4. **GoodAI-LTM / MemoryAgentBench 数据**：R2 阻塞。

## 六、下一步（按 `13-` 优先级，P0–P4 第一轮已落地）

1. P0 遗留：authorization certificate 形式化（soundness/verifiability/non-triviality）与 Theorem 4(c′) 收紧；
2. P3/P4 严格化：self-confirming 环境的 Ω(T) 形式证明；探测复杂度 minimax 下界与匹配上界；
3. P2 对接成本合同：C_probe ← Gate 4 的 λ_probe·E[probes] 估计，重算边界表；
4. 每批补充后：全量测试 → 重新生成四件套冻结清单 → 同步 D 盘 → 提交推送；
5. 长线下游：trace-grounded 主表、外部 rollout、声称压缩（最后做）。
