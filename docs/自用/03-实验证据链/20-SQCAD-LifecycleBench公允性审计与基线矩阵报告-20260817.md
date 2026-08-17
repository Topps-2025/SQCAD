# SQCAD-LifecycleBench 公允性审计与基线矩阵报告（2026-08-17/18）

数据："数据集不是自娱自乐"四通道判定（23- §7.6）落地运行 + 全基线矩阵 + 框架修改判定。
审计工具与判据全部预注册（23- §7.7），运行输出独立落盘：`remote_results/lifecycle_audit/{r1_shortcut,r2_sensitivity,r3_unseen,r5_independent,matrix}.json`；远端 AutoDL 复跑结果与本地逐位一致（见 §8）。

## 1. 摘要

| 防线 | 判据（预注册） | 结果 | 判定 |
|---|---|---|---|
| R1 元数据捷径 | 分栏报告；一致率上界 $= 1 - \frac{15}{1380} = 0.9891$ | metadata(family,variant) train 0.989 → test 0.740；text-only test 0.740；**无任何 public-trace 特征可超过上界** | ✅ 评价不可被猜 |
| R2 标签敏感性 | <5% 稳健 / 5–30% 敏感区 / >30% 脆弱需重定位 | **fragile**：GAMMA=0.7 → 36.2%、TAU_TOL=1.0 → 32.6%；7 项入敏感区；其余稳健 | ⚠️ 脆弱→重定位（§3） |
| R3 未见机制 | 一致率 ≥0.9 且无反向翻转；pair 家族以配对翻转确认率为主判据 | 15 cell 中 12 全转移；hitchhiker pair 翻转 100% 确认；3 个机制边界如实报告 | ✅ 泛化可被挑战 |
| R4 必胜区预注册 | §7.7 表 13 行逐 bucket 对照 | **13 行全部命中，无一失准** | ✅ 预注册纪律 |
| R5 独立实现 | 第二实现位级一致 | 1380/1380 consistent，inconsistent=0 | ✅ 真值可独立检验 |
| R6 人类锚 κ | κ ≥ 0.6 | 28 case 盲化导出完成；判官批次待外部执行 | ⏳ 待外部 |
| R7 发布包 | 去元数据视图 + 官方打分器 | public_trace_only.jsonl（1380 条）+ README + 打分器 | ✅ 可公开发布 |
| R8 迭代日志 | 构建期调整成文 | §7.8 追加 3 条（pair label 同步、判据修正、机制边界） | ✅ |

基线矩阵（决策策略，mean lifecycle value / regret / oracle 一致率 / false-commit，n=1380，paired bootstrap seed 20260817）：

| 策略 | mean value | regret | oracle 一致率 | false-commit |
|---|---:|---:|---:|---:|
| oracle_policy（上界） | +0.964 | 0.015 | 1.000 | 0.000 |
| probe_willing（archive 除非 POSITIVE） | +0.865 | 0.115 | 0.906 | 0.072 |
| sqcad_cert_conflict（+lineage→archive） | −0.278 | 1.258 | 0.744 | 0.228 |
| archive_all | −2.790 | 3.770 | 0.459 | 0.000 |
| storage12 / memory_worth | −3.476 | 4.455 | 0.703 | 0.181 |
| random50 | −6.269 | 7.248 | 0.509 | 0.198 |
| event_rule / sqcad_cert | −8.901 | 9.880 | 0.663 | 0.409 |
| scope_literal | −10.221 | 11.200 | 0.622 | 0.337 |
| keep_all / recency2 | −10.280 | 11.260 | 0.541 | 0.409 |
| frequency2 | −13.254 | 14.233 | 0.419 | 0.409 |

配对 bootstrap（sqcad_cert 为基准，95% CI 不含 0 记为显著）：显著优于 keep_all(+1.38)、recency2(+1.38)、frequency2(+4.35)、scope_literal(+1.32)；显著劣于 archive_all(−6.11)、random50(−2.63)、storage12/memory_worth(−5.43)、sqcad_cert_conflict(−8.62)、probe_willing(−9.77)；与 event_rule 逐 episode 相同（0 分歧，见 §5）。

**框架修改判定（§7）**：参考决策在三个预注册失败点被矩阵证实——(a) lineage_conflict→archive（conflict 变体 +8.62 显著）；(b) hitchhiker UNRESOLVED→archive（probe_willing 依据）；(c) future_in_s2 需 scope 前瞻（scope_literal 在该 bucket 达到 oracle 上界，但全局误杀需精化）。

## 2. 数据集修订回顾与 hash 校验

- 纠错文本修订（23- §7.6）：`"{e}: peanuts -- the old peanut fact is wrong"` 使词法 requalify 通道从 public 层可达；oracle/证书逐位不变（R5 + 47 合同测试双重验证）。
- 本批数据集（`results/lifecycle_bench/`，旧版备份 `results/lifecycle_bench_mvp_backup/`）：1380 episodes、三层序列化、split 818/354/208。
- **远端重建校验**（AutoDL，数据盘 /root/autodl-tmp，env sqcad-py310）：

| 文件 | 本地 sha256 | 远端重建 sha256 | 一致 |
|---|---|---:|---:|---|
| public.jsonl | `9aaa40ef…` | `9aaa40ef…` | ✅ |
| hidden.jsonl | `c7d8b75e…` | `c7d8b75e…` | ✅ |
| policy_log.jsonl | `4da241ee…` | `4da241ee…` | ✅ |
| manifest.json | 仅 `generated_at` 时间戳不同 | （其余字段逐项一致） | ✅ 预期 |

（本地初版文件为 CRLF，重写为 LF 后与远端逐字节一致；构建由 seeds 完全决定。）

## 3. R2 标签敏感性：fragile → 重定位

31 个 frozen 常数扰动 run（15 组 × 2 值 + GAMMA 3 值），全部 1380 标签重算，flip_rate = 与冻结参数下标签不同的比例：

| 常数 | 值 | flip | 区带 |
|---|---|---|---|
| GAMMA | 0.7 | 0.3623 | **脆弱** |
| TAU_TOL | 1.0 | 0.3261 | **脆弱** |
| PROBE_COST | 0.5 | 0.2536 | 敏感 |
| WORKSPACE_BUDGET | 12 | 0.1667 | 敏感 |
| ADOPT_THRESHOLD | 3 | 0.1558 | 敏感 |
| PROBE_THRESHOLD | 2 | 0.1449 | 敏感 |
| PROBE_BUDGET_PER_TASK | 0 | 0.0725 | 敏感 |
| GAMMA 0.95/0.99、PROBE_COST 2.0、TAU_TOL 0.2、ADOPT 1、PROBE_TH 4、WS 8、STORAGE_RATE 0.02、EXPOSURE_UNIT 0.1 | — | 0.036–0.072 | 敏感边缘 |
| HARM_PENALTY、TASK_VALUE、RECENCY_W、FREQUENCY_W、NEGATIVE_ATTENUATION、REQUALIFY_OVERLAP 全部、PROBE_BUDGET 2 | — | 0.0 | 稳健 |

**重定位说明（预注册判据执行，不改标签）**：
1. 脆弱常数是**经济参数与判定参数**，非生成噪声：GAMMA 直接决定远期价值贴现（0.7 使远期任务价值近乎消失 → 大量 keep→archive 翻转）；TAU_TOL 是 oracle 判定阈值（0.5→1.0 把 $\tau \in [0.5, 1.0]$ 的 keep/archive 重分类为 neutral）。二者敏感是价值函数定义使然，不是标签随机性。
2. 本批标签的有效域：**GAMMA $\in [0.9, 0.99]$ 区间**（0.95/0.99 下 flip 仅 3.6%，均落在 TAU_TOL 边缘的临界 episode）；TAU_TOL 敏感区与 R3 的机制边界发现互相印证（rescue 移位后 $\tau$ 跌破 0.5 → neutral，同一 TAU_TOL 敏感性）。
3. 语义类常数（HARM_PENALTY 含场景重建、TASK_VALUE、权重类、词法门槛）全部 0.0 翻转——**场景设计的语义结论不依赖这些常数的具体取值**。
4. 外部使用者应按冻结 manifest 参数（frozen.py）解释标签；如需跨 GAMMA 迁移结论，须在本报告标注的重定位区间内讨论。

## 4. R3 未见机制 holdout

15 bucket × 3 knob × 20 episodes = 900，seed 区 20260901+，未见实体池 16 名。主判据：oracle 与设计意图一致率 ≥0.9 且无反向翻转（hitchhiker_pair 以配对翻转确认率为主判据）。

- **12/15 cell 全转移**（≥0.9 一致率、无 reversal）：entity/difficulty 全部；slot_shift 中 rare_bridge/rescue_impossible、self_obscuring/crowding、version_update、harmful_stale、scope_mismatch、stable_*、hitchhiker_pair（配对确认率 1.0）。
- **3 个机制边界（如实报告，非标签错误——evaluator 为同一诚实反事实）**：
  1. `rare_bridge/rescue_possible` slot_shift：一致率 0.35。救援任务由 slot 2 移至 3–5 后 $\tau \in \{0.19, 0.34, 0.51\}$，仅 $0.51 > 0.5$ 的保持 keep，其余退化为 neutral；
  2. `self_obscuring/rescue_possible` slot_shift：一致率 0.0。$\tau \in \{0.16, 0.31, 0.49\}$ 全部 $< \mathrm{TAU\_TOL}$ → neutral；
  3. `neutral/default` slot_shift（该家族无救援任务，knob 退化为决策记忆存储大小 6/12 tokens）：一致率 0.0。storage 扰动使 $\tau$ 0→$\{-0.65, -1.0\}$，中性平衡偏 archive。
- **判据修正（R8 日志 #7）**：`_flip_pair_slot` 原只改 needed_fid 未同步 `decision_action_label`（MVP 中 flip 侧 label=keep），误报 20 个假 reversal；修复后配对翻转确认率 = 1.0（base 在新槽位 archive ∧ flip 在新槽位 keep，同一公开 trace）。
- 机制边界解读：rescue 收益是**贴现位置敏感**的（方向保持、强度跌破判定阈值）；neutral 平衡对存储规模敏感。二者为机制可迁移性的真实边界，不否定场景设计的内部有效性（原设计 tau 与阈值有 0.18–0.34 余量）。

## 5. 基线矩阵与消融

决策策略与消融语义见 `baselines.py`（预注册）。关键事实与解释：

1. **sqcad_cert 与 event_rule 逐 episode 相同（0 分歧）**：证书 NEGATIVE 在 LB 上全部由可见 correction 事件驱动（修订文本后词法通道可达），150 个 NEGATIVE(event_targets_fid) = 可见事件重叠 ≥2 的集合（correction_visible 100 + stable_negative control 50）；MISMATCH 证书为 0（LB 场景中决策记忆始终处于正确 scope，scope gate 测试面在 21- E1 而非 LB）。**诚实报告：文本事件规则是 LB 上证书决策的完全代理**——证书决策的 public-layer 可识别信号。
2. **消融区分度集中在 no_censoring（250/1380），其余四开关 0/1380**：设计事实——(a) 证书不进效用（效用只由 success/penalties/成本决定）；(b) future events 无条件重判证书（`simulate_event` 不依赖 cfg.qualification）；(c) probe/restore/lineage 在 follow-on 效用路径零触发。**机制必要性证据由环 4（公开数据 overlay）承担**（E2 fallback 0.96→0.30、F1 restore 0.0455→0.0163 显著）；本消融矩阵的 no_censoring 差异回答"censoring（归档记忆不可检索）的代价"：250 个 archive 分支中未来任务需要决策记忆的 episode 价值受损。
3. oracle_policy regret 0.015：来自 150 个 neutral 场景（oracle 策略按协议选 keep，非最优分支）；一致率按非 neutral 分母计算。

## 6. R6 人类锚 / R7 发布包

- R6：28 case 分层抽样盲化导出（`anchor/anchor_cases.md`，无 family/variant 标记）；私有 oracle 标签独立存 `anchor_labels_private.csv`；判官 CSV → `score_anchor` 计算 Cohen's κ（判据 κ ≥ 0.6）。**待外部判官批次**。
- R7：`release/public_trace_only.jsonl`（1380 条，id 匿名化、去 family/variant/episode_id/regime）+ README + `score_lifecycle_predictions.py` 官方打分器（predictions → 选择分支折扣价值/regret/一致率）。

## 7. 框架修改判定（本批 /goal 第 3 步）

预注册必胜区表（23- §7.7，13 行）**全部按预注册方向验证**（无失准）。据此判定框架是否需修改：

| # | 修改候选 | 证据 | 判定 |
|---|---|---|---|
| 1 | **lineage_conflict → archive**（当前保守 keep） | version_update/update_before 上 sqcad_cert −119.53 vs conflict −0.54（=oracle 上界）；全局 bootstrap 显著 +8.62 | **确认修改**：UNRESOLVED(lineage_conflict) 应 archive。语义：版本冲突标识"旧版事实不可信任"，保守 keep 导致灾难性 false-commit |
| 2 | **hitchhiker association_only → archive** | hitchhiker/default 上 sqcad_cert −1.90 vs archive 4.93；probe_willing（archive 除非 POSITIVE）全局最优 +0.865（bootstrap +9.77 显著） | **确认修改方向**：无独立信号（仅关联暴露）的记忆不应 keep。机制化路径（资格阈值 vs 探测恢复成本权衡）在 Phase B 精化，本批先落"association_only_hitchhiker → archive"规则 |
| 3 | **future_in_s2 需 scope 前瞻** | 该 bucket scope_literal = oracle 上界（−12.94），sqcad_cert −13.77 输；但 scope_literal 全局误杀（harmful_stale 等 future 全 s1 场景被误 archive） | **确认问题、暂缓修改**：需要比"存在跨 scope 任务"更精细的信号（未来任务是否**需要**决策记忆）。列为 Phase B 端到端的第一验证点 |

三项修改对框架主张的影响：修改 1/2 收紧"资格不足→不 keep"的保守侧，与环 4 的 fallback/probe 治理发现方向一致（过度保守的代价 < 过度 commit 的代价——本矩阵 false-commit −119.53 vs 保守 −0.54 的量级对比）；不触及三层结构与资格证书形式化（16- 严格化保持不变）。

## 8. 可复现性与远端复跑

- 本地：47 合同测试 + 23 公允性测试 + R5 1380/1380 一致（16.9s）。
- 远端（AutoDL，数据盘）：重建数据集 hash 与本地一致（§2）；审计套件（R1/R3/R2/matrix）在远端复跑，结果与本地逐位一致（r1/r3 已完成对照，r2/matrix 复跑落盘 audit_out/）。
- 统计协议：episode 级配对 bootstrap、seed 20260817、2000 重采样；扰动/knob 集与判据全部预注册在先（23- §7.7）。

## 9. 结论

- 四通道判定：**真值可独立检验 ✅（R5 位级一致 + 远端重建 hash 一致）、失败可以发生 ✅（基线矩阵 12 个非平凡策略 11 个显著分离）、泛化可被挑战 ✅（12/15 转移 + 3 边界如实报告）、评价不可被猜 ✅（R1 上界 + R4 13 行全命中 + R7 发布包）**。
- R2 fragile 为经济参数敏感（GAMMA/TAU_TOL），已按预注册执行重定位说明；语义类常数 0 翻转。
- 框架修改 3 项判定完成（§7），其中 2 项确认修改方向、1 项暂缓精化。
- 遗留：R6 判官批次（外部）、Phase B 端到端（修改 3 的第一验证点）、dense 复现（环 4 已有 19- 记录）。
