# SQCAD 项目进度审计（2026-08-13）

> 本审计回答三个问题：(1) 从哪些文献读出 research gap 假设，并转化为了哪些研究理念、工作与痛点；(2) gap 是如何被设计成可证伪命题并以实验证明立住的，为什么现有工作无法覆盖、基线工作是什么；(3) 定理形式化、证明、框架反推、条件充分性/必要性与框架成本收益分别由哪些实验支撑。
>
> 与 `docs/自用/02-历史草稿/研究路线与方案/00-ResearchGap到充分性与必要性的完整实验逻辑线-20260813.md` 的关系：`00` 是**论证逻辑线**（每个主张的证据链），本审计是**进度台账**（完成度、阻塞、下一步）。理论推进路线见 `docs/自用/02-历史草稿/研究路线与方案/13-形式化为真正理论空白的必要性证明方向-20260813.md`（P0–P4）。

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
2. **升级为可证伪命题**（`11-形式化定理陈述与证明`）：固定 treatment（持久访问动作）、estimand（lifecycle value $V_s^\pi(a)$）、观测合同（候选/暴露/位置/预算/采纳/结局/版本/作用域）、失败判据（两个观测等价世界给出相反最优动作）→ Theorem 1/2 + Corollary 1。

### 1.3 转化为的研究理念与痛点

| 痛点（文献中观察到的） | 转化出的研究理念 | 落点 |
|---|---|---|
| 历史成功共现被策略生成暴露混杂（Memory Worth 自己报告的 hitchhiker 共检索不可区分） | 关联信号只提案、不授权 | Evidence 层与 Qualification 层分离 |
| CMI 类 query-local 效应精确正确仍可能做错生命周期决策（future candidate / budget / interference 未进入 estimand） | 持久访问动作是 treatment，局部效应只是后果链的一段 | Theorem 2 + Access 层 treatment 语义 |
| 写时治理（GovMem/SAGE）不覆盖访问时授权；衰减治理（Oblivion/FadeMem）无识别资格检验 | "写时资格 ≠ 访问时授权"，衰减触发证据需要资格 | Qualification 门输出 $\{\text{point},\ \text{bound},\ \text{unresolved},\ \text{mismatch}\}$ |
| 压缩治理（DeMem）的决策对象是下游答案质量而非持久动作价值；审计（MemAudit）是事后归因而非前瞻授权 | 决策中心视图 + 可撤回授权 | 成本合同 $V$ 与资格→动作接口 |
| 最接近先验 Trivium 的 treatment 是预设 SCM 的 confounder 探针、无策略反馈候选流建模 | 探针是手段之一；识别意识是必经原则 | Theorem 4 + 识别路线分类学（`12` 文档） |

---

## 二、问题 2：gap 如何被设计实验证明立住；为什么现有工作无法覆盖；基线是什么

### 2.1 三个构造性反例（`01`/`02` 报告 + `gap_proof_experiments.py`）

| 命题 | 构造 | 关键数字 | 证明的 gap |
|---|---|---|---|
| A（Theorem 1） | 两 SCM 共享随机序列、完美共暴露：全字段 max diff = 0.0（25,000 行联合日志逐位一致），lifecycle 却为 +1650 / −1100 | Memory Worth 在 $M_2$ regret = 1100 | 观测日志在信息论层面无法识别 lifecycle value——换正确的因果估计器也失败 |
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
| Theorem 2 | 局部效应精确相等、lifecycle 相反（局部不充分） | 命题 B：$\Delta_{\mathrm{do}}=2.000$ 相等、−1784/+1776、regret 1784 | ✅ 同上 |
| Corollary 1 | source 不自动 transport | 命题 C | ✅ 同上 |
| Theorem 3 | C1–C8（**可操作、可审计的充分授权条件族**，2026-08-13 更名）下协议/观测双路识别；条件失败输出 $\{\text{point},\ \text{bound},\ \text{unresolved},\ \text{mismatch}\}$ | Stage 1：bias $\approx$ MC 噪声、CI 12/12、自信错误 0、unresolved 恰为 neutral；Stage 2：五种违反全部被门捕获 | ✅ 充分方向已验证（观测路 lifecycle DR 尚为 g-formula 级） |
| Theorem 4 | 未识别类上 committing 规则最坏情况 regret $\ge \vert\tau_1\vert\,\vert\tau_2\vert/(\vert\tau_1\vert+\vert\tau_2\vert)$、错误概率 $\ge 1/2$；突破需拒绝或新证据 | 双世界实例：660 @ p=0.6；错误 ≥ 0.5；门控 0 | ✅ 证明 + 计算验证（两点构造版） |
| Theorem 4(c′)→审计性 | 拒绝触发必须可验证 | 论证成立但 13- 指出需独立形式化（authorization certificate：soundness/verifiability/non-triviality） | ⚠️ 待升级（P0） |
| **T1 self-obscuring lifecycle theorem**（14- §6；严格证明 `15`） | (a) 任意无恢复 committing 策略在错误审查世界 $R_T = \tau\cdot p\cdot(T-n_{\mathrm{early}}) = \Theta(T)$（精确斜率 5.85 = 10×0.6×1950/2000）；(b) $q>0$ 恢复 $\Rightarrow \mathbb{E}[R_T] \le O(1/(q\rho))$，与 $T$ 无关；(c) $p_{\mathrm{arch}}=p$ 时下界消失 | W0–W3 消融（`实验证据链/13`）：W2 精确 5.8500 vs W0 0.0440（去审查即失效）；恢复平台 0.4250；restore sweep 单调（corr 818/142/37） | ✅ 严格证明（引理 1/2 + 定理 1，15-）+ 12-seed 数值 |
| **T2 reduction separation**（14- §7.2；严格证明 `16`） | 任何忠实 feedback-preserving reduction（定义 1：动作集合/即时 reward/观测信息保持 + $\phi$ 世界无关 + 保真）若不加证据可得性状态，则 max regret $\ge \frac{1}{2}\tau p(T-n_{\mathrm{early}}) = \Theta(T)$（定理 2；配对恒等式 $regret_K+regret_A \equiv \tau p(T-n_{\mathrm{early}})$ 对任意策略逐点成立，引理 4） | controls：W0/W1 全部有效（slope $\le$ 0.075），W2 全部精确 5.8500；`实验证据链/14`：配对恒等式 4 策略逐位精确 11700.0、忠实像上 5.8500 精确、禁止 $\phi$ 控制 0.0000、不被审查的 contextual_bandit $\approx$ 0.03 | ✅ **严格证明**（定义 1/2 + 引理 3/4 + 定理 2 + 推论 2/3，`16`）+ 12-seed 数值 |
| Lemma A–D | C2/C3、C6、C7、C8 存在替代/退守路线（N1 不成立） | C6 bias 0.49/0.30 vs se 1.4；C7 bundle 8.97±1.12 vs 8.07；IV −0.003 vs 观测偏倚 +0.835；C8 +21.4 vs 当期 1.07 | ✅ 代码验证（**C1/C4/C5 未逐项处理，不声称全族不必要**） |

### 3.2 框架反推实验（`03`/`04` 报告）

识别条件逐条映射框架组件（`10-识别条件到框架设计`）：Evidence 层（日志完整性 C1/C4/C5、采纳分离、策略状态）← 命题 A 的不可识别来源；Access 层（持久动作语义、预算与共记忆）← 命题 B；Qualification 层（scope/version 门、overlap 检验、随机微干预）← C3/C8/Cor 1。**两阶段实验**验证：Stage 1 协议路线恢复 oracle（bias −0.47、CI 12/12、决策零错误）；Stage 2 逐条件违反全被门捕获为 unresolved/mismatch（C7 下盲门强制决策 regret 41.0、C3 下 83.4——弃权不是免费的，框架承诺的是"绝不做自信错误决策"）。

### 3.3 充分性与必要性的实验分工

- **充分性**（"C1–C8 满足 ⇒ 能识别"）：Theorem 3 + Stage 1 + g-formula/局部 DR 估计有效性实验（`04`：支持覆盖处恢复真值、支持缺失处可预言符号错误、DR 单误设低偏双误设失效、C6 使 DR 失效、界改写错误决策为 unresolved）；
- **必要性**（"可识别 ⇏ 必须满足完整 C1–C8"；"门控是必要的"）：Lemma A–D 替代路线（`necessity_counterexamples.py`）+ Theorem 4 下界；
- **关键边界**（`11` 报告用户修订后口径）：Lemma 只覆盖 C2/C3/C6/C7/C8；C7/C8 是治理粒度/estimand 退守；不能说"C1–C8 每一项都已被证明不必要"。

### 3.4 成本与收益实验（`07`/`08` 报告）

- **成本合同** $V = \sum\gamma^{t-1}\left[U - \lambda_{\mathrm{tok}}\cdot C_{\mathrm{tok}} - \lambda_{\mathrm{llm}}\cdot C_{\mathrm{llm}} - \lambda_{\mathrm{probe}}\cdot C_{\mathrm{probe}} - \lambda_{\mathrm{lat}}\cdot C_{\mathrm{lat}} - \rho_{\mathrm{harm}}\cdot R_{\mathrm{harm}}\right] - \rho_{\mathrm{ff}}\cdot R_{\mathrm{ff}}$（$\lambda_{\mathrm{llm}}=0$ 如实标注）：SQCAD 默认/风险规避/延迟敏感区间最优（38.48）；对最优非探测基线 break-even $\lambda_{\mathrm{probe}}^*=5.53$（110$\times$ 默认）；探测预算受限（pb=0）领先 CMI +6.6；**保留的负面结果**：强制恢复在含害世界 V 38.62→8.73；**如实边界**：对配探测 CMI 的 V 领先 10-seed CI 下界恰为 0（不可显著区分）；
- **统计门**：采样单元=seed 的 studentized paired bootstrap（heavy-tail 0.9275 vs 正态 0.8745；D0 世界覆盖–n 斜率反转 0.79→0.92–1.00）；主表差值 CI 不跨 0；四件套 SHA-256 冻结（当前聚合哈希随最新内容重生成）。

---

## 四、进度台账

### 4.0 新增的客观性约束

公开数据集阶段的主结果不允许依赖我们手工定义的“应保留/应删除”金标。主结果使用原生答案、支持证据、时间顺序、未来事实更新和统一成本日志自动计算；Gate A 等人工标注只做盲法机制审计与子集分层，不参与测试集调参、不作为总体 SOTA 分数。该约束已写入 `17-SQCAD公开数据集落地与框架实验方案-20260813.md`。

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
| **P0 修正**（C6 隔离、IV lifecycle 化、C7/C8 语义） | ✅ 完成（certificate 形式化仍待） | `实验证据链/12` §1–2 | C6 隔离：协议 1.1914 逐位相同、观测对比按 $(1-2\varepsilon)$ 稀释；lifecycle IV 误差 0.017 vs 偏倚 12.96 |
| **P1 一般决策识别定理**（$R^*(L,U)=U(-L)/(U-L)$；安全提交 $\iff$ 识别集不跨 0） | ✅ 完成 | `12` 定理文档 §3.6、`实验证据链/12` §3 | **Theorem 5 完整证明** + 计算验证（660 复现 @p*=0.6；决策识别非点识别实例 (500,1650) regret 0） |
| **P2 拒绝/探测成本边界** | ✅ 完成（数值级） | `实验证据链/12` §4 | $C_{\mathrm{probe}}<330$ 探测胜 commit、$<170$ 胜 defer；与 Gate 4 $\lambda_{\mathrm{probe}}$ 参数对接仍待 |
| **P3 动态探索必要性**（$\Omega(T)$ 无探索 regret） | ✅ **在显式模型内严格证明**（T1(a)，`15`）+ 数值 | `实验证据链/13` §3/§5、`15` | W0–W3 消融：W2 精确 5.85 = $\tau\cdot p\cdot(T-n_{\mathrm{early}})/T$；无恢复提交规则 5.85 精确（`13` §5）；去审查（W0）后 0.044——现象依赖审查结构；不外推为任意序贯策略 |
| **P4 动态探索上界 + minimax 探测下界** | ⚠️ **旧 matching 已撤回并替换**：T1(b) 仅单世界诊断；P4 定理 3/4 保留 fixed-sample 与有限时域等待下界；有效安全上界/下界为 `17` Theorems 11–13，同一 `Safe(H,delta)` 类并显式 false-restore 成本 | `16` §2、`17`、`safe_recovery_theory.py` | 不能再写 horizon-independent $O(1/(q\rho))$ 或旧推论 4 matching；当前主张是 finite-horizon total-cost order，anytime/stitched 另有 coverage overhead；公式与 toy coverage 已测试 |
| **self-obscuring 结构消融 + self-confirming 全对比（T1/T2 机制证据链，实验 A/B）** | ✅ 完成（严格证明 + 12-seed 数值） | `实验证据链/13`、`15`、`self_obscuring_ablation.py`（15 项新测试） | 主张升级判定（14- §9：验收 1/2 严格满足、3 部分满足）→ 推进 SQCAD 框架设计 |
| **reduction controls（实验 B，14- §7.2）** | ✅ 完成 | `实验证据链/13` §4 | T2 反证的数值侧；W0/W1 有效、W2 精确线性 |
| **T2 严格化 + P4 下界（评审回应批）** | ⚠️ T2 restricted reduction 证明保留；P4 旧 matching 撤回，安全 matching 转至 `17` | `16`、`17`、`reduction_closure.py`、`safe_recovery_theory.py` | T2 仅 fully censored/no-restore committed subclass；P4 仅 fixed-sample/finite-horizon 下界；Theorems 11–13 才是当前同类安全总成本闭环 |
| 外部 rollout（chronological future） | ⏸ 阻塞（模型端点） | `00 实验证据链` 未验证清单 | — |
| 公开数据集客观治理比较 | ⏳ 方案已定、实施未完成 | `17-SQCAD公开数据集落地与框架实验方案-20260813.md` | LongMemEval-S 主集 + LoCoMo 复验；统一合同、同一 reader/evaluator、无手工金标依赖 |
| **公开数据集落地准备批（本批）** | ✅ 完成 | `18-基线开源状态与无GPU复现审计-20260813.md`、`docs/自用/03-实验证据链/15-基线开源状态与无GPU复现审计-20260813.md`、`tools/render_framework_diagram.py` | ①核心源码冻结（255 测试通过 + 四件套清单重生成，聚合 `badbb886…`，code 46/results 25/reports 11）；②框架工程图 13-（Evidence→Qualification→Access→Decision→Lifecycle，含 T1/T2/P4 之后的 censoring-aware 语义与 restore/probe 通道，渲染脚本入仓库）；③GitHub 展示层组建（README 重写、docs_en 更新、CITATION.cff）；④12 个 R3 基线 + 4 个基准数据集逐一网络核查（结论：仅 ActMem 真 GPU 阻塞；其余 API-key 阻塞或纯 CPU；Oblivion 代码公开但 NEC 专有许可；FadeMem/Memory Worth/DeMem/Trivium/GovMem 无官方代码；LoCoMo 官方 F1 无 judge LLM 可纯 CPU 评分） | 按 17 §5 先做 D1/D2 检索协议（可全 CPU）与 LoCoMo 离线 F1；Oblivion/SimpleMem 非 LLM 机器离线验收 |
| 论文写作（Introduction 规范稿等） | ✅ 已有草稿 | `07-Introduction规范稿` | 声称压缩最后做 |

**测试与工程状态**：全套 **255 项测试通过**（239 + 16 新）；`results/`（gitignored）与 D 盘外部数据库同步（34 个 JSON）；冻结清单 `freeze_manifest.json` **已重新生成**（聚合 SHA-256 `badbb886d0e878126cd6aa8582fe7d43f0f307dce67c1a4f4e1ce758a94f9b61`；code 46 / config registry + 两冻结数据集字节哈希 / results 25 / reports 11）；公开数据集主表尚未冻结，不能把当前受控 runner 结果写成外部 SOTA。

---

## 五、阻塞清单

1. **R3 基线复现**：无 NVIDIA GPU、无 OpenAI/Anthropic/Azure/HF API key（环境事实，非省略）。`18-` 审计细化：**GPU 不是主要墙、API key 才是**——12 个系统中仅 ActMem（Qwen3-Embedding-8B）被 GPU 卡死；SimpleMem/Oblivion/CMI 的非 LLM 机器（单测、数据 reader、检索组件）现在即可离线验收，缩小日后只剩端点的缺口；
2. **外部 QA 层端到端**：GPT-4o-mini 端点（`06` 如实标注）；
3. **trace-grounded 主表**：`06` §7.1 下一步（无模型端点也可做，是最近的现实接地增量）；
4. **GoodAI-LTM / MemoryAgentBench 数据**：R2 阻塞。

## 六、下一步（按 `14-` §9 验收与 §10 执行顺序；T1/T2 机制证据链 + 评审回应批已落地）

1. **主张升级判定已更新**：T1(a) 与 T2 restricted separation 可保留；旧 T1(b)/P4 matching 已撤回。当前安全恢复闭环是 `17` Theorems 11–13，仍需独立数学复核和 held-out mechanism-family 实验后才能升级为投稿主结果；
2. **P4 当前状态**：定理 3 固定样本检测、定理 4 有限时域等待下界保留；同类 total-cost matching 仅引用 `17`，不能再引用 `16` 的旧推论 4；
3. P0 遗留：authorization certificate 形式化（soundness/verifiability/non-triviality）与 Theorem 4(c′) 收紧；该遗留不阻塞公开数据集客观治理比较，但限制“完整授权理论”的表述。
4. P2 对接成本合同：$C_{\mathrm{probe}} \leftarrow$ Gate 4 的 $\lambda_{\mathrm{probe}}\cdot\mathbb{E}[\text{probes}]$ 估计，重算边界表；
5. 长线下游（最近的现实接地增量）：**trace-grounded chronological 实验**（验收 6/7：时间先后 + 因果优先于观察依赖，无模型端点可做）、外部 rollout、声称压缩（最后做）；
6. 公开数据集落地时先完成客观性 gate：冻结 candidate stream、future split、reader/evaluator、成本合同和基线版本；人工标注仅作盲法机制审计，不能替代客观主表；
7. 每批补充后：全量测试 → 重新生成四件套冻结清单 → 同步 D 盘 → 提交推送。
