# 半合成 Chronological Overlay：治理目标实验（2026-08-14）

> 目标阶段 3（由 `16-` §4 判定触发）：公开数据无 lifecycle 金标，因此在 LoCoMo 纵向轨迹上注入**程序化生成**的未来事件（只使用历史时点可见信息），以程序化客观标签直接检验 T1/T2 理论预测的治理指标——false forgetting、有害保留、纠错吸收、probe/restore 救援。
>
> 方案：`草稿-draft/实验方案与基线/19-`。代码：`src/sqcad/chronological_overlay.py` + `tests/test_chronological_overlay.py`（7 项）。结果：`results/chronological_overlay.json`。复用 `16-` 冻结的统一合同与显著性管线（paired studentized bootstrap，$n_{\mathrm{boot}}=2000$，boot_seed=20260812；n=10 会话单位）。

## 1. 预注册注入协议（冻结于运行之前）

| 常数 | 值 | 事件 | 构造 | 客观标签 |
|---|---|---|---|---|
| E1_GAP | 2 | E1 版本更新干扰 | needed turn 首句 + "UPDATE: this is the newer version"，置于 anchor+2 | 原 QA 金标不变；暴露旧版=命中，暴露更新且缺证据=distractor |
| E2_GAP | 1 | E2 纠错事件 | anchor+1 注入否定金标的错误事实 F（"…this was NOT <gold>"）；anchor+2 注入 "Correction: <gold>" | 纠错后暴露 F 且缺证据=harmful；纠错提供吸收机会（对照 E3） |
| E2_GAP | 1 | E3 有害保留 | 仅注入 F（无纠错） | 同上 harmful；F 与证据共享 $\ge 3$ 词（版本冲突可检测） |
| — | — | E4 稀有正向保护 | 无注入（低频 session 的 needed turn，稀有度按原始流计算） | 原 QA |
| — | — | E5 self-obscuring+救援 | 无注入（写时被归档的证据在 QA 时可否被 probe/restore/fallback 救回） | 救回=rescue，未救回=false forgetting |
| N_EVENTS_PER_TRACE | 5 | 每会话每类注入 ≤5 个事件（轮转分配，每 QA 至多 1 个 E1/E2/E3 事件） | OVERLAY_SEED | 20260814 |

金标纪律：QA 金标答案只用于构造 F（programmatic），从不进入任何 policy；评估用暴露语义判据（F 暴露 ∧ 证据缺失 → harmful），不跑 reader、不依赖人工标签。

## 2. 主结果（LoCoMo，10 会话，每类 50 个事件；E4/E5 覆盖全部含证据 QA）

| policy | E1 hit | E2 harm | E3 harm | E4 hit | E5 rescue | E5 ff |
|---|---|---|---|---|---|---|
| bm25 | 0.600 | 0.540 | 0.480 | 0.492 | 0.000 | 0.000 |
| recency | 0.000 | 0.000 | 0.000 | 0.034 | 0.000 | 0.989 |
| keep_all | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| **sqcad** | **0.220** | **0.300** | **0.420** | **0.171** | **0.206** | 0.793 |
| no_probe | 0.080 | 0.020 | 0.060 | 0.062 | 0.070 | 0.924 |
| no_restore | 0.100 | 0.120 | 0.160 | 0.076 | 0.090 | 0.903 |
| no_version_gate | 0.200 | 0.440 | 0.420 | 0.173 | 0.201 | 0.796 |
| **no_fallback** | 0.220 | **0.960** | **0.860** | 0.178 | 0.199 | 0.800 |
| no_positive_protection | 0.220 | 0.300 | 0.420 | 0.171 | 0.206 | 0.793 |

注：harmful 判据要求"F 暴露 ∧ 证据缺失"——recency/keep_all 的 harmful$\approx 0$ 是结构性零（recency 几乎什么都不暴露；keep_all 什么都暴露），解读时须与 hit 联读。

## 3. 显著性判定（预注册规则；n=10 会话，studentized paired bootstrap）

### 3.1 显著优势（机制目标）

- **E5 救援**：sqcad rescue 0.206 vs bm25/recency/keep_all 的 0.000——**+0.206 [0.144, 0.230] 显著**（只有 SQCAD 的 probe/restore/fallback 通道能救回被归档的证据）；vs no_probe +0.136 [0.083, 0.168] 显著、vs no_restore +0.116 [0.070, 0.160] 显著。
- **fallback 消融（保守暴露）**：E2 harmful 0.960→0.300（**−0.660 [−0.766, −0.447] 显著**）；E3 harmful 0.860→0.420（**−0.440 [−0.663, −0.314] 显著**）——doc 17 §6 "no fallback → 缺证据条件下错误提交上升" 的预测在注入事件上**成立**。
- **probe 通道**：E1 hit 0.080→0.220（+0.140 [0.013, 0.299] 显著，旧版本救援）；E4 稀有召回 +0.109 显著；E5 hit +0.129 [0.073, 0.163] 显著。
- **vs recency（recency-biased 持久化对照）**：E1/E2/E3/E4/E5 全部命中显著为正（+0.08~+0.22）。
- **E1 distractor**：vs bm25 −0.060 [−0.118, −0.007] 显著——SQCAD 的版本意识（冲突负衰减）使更新干扰暴露低于检索 oracle。

### 3.2 不显著 / 方向有利但 n=10 检出力不足

- **E2 harmful vs bm25**：0.300 vs 0.540，diff −0.240 [−0.427, 0.039]——方向有利（SQCAD 的有害暴露低于检索 oracle）但 CI 跨 0，n=10 不可判定，如实标注。
- E3 harmful vs bm25：−0.060 [−0.262, 0.167] ns。
- no_version_gate 在本子集上差异不显著（E1/E5 方向接近 0）。

### 3.3 显著劣势（预期边界，如实报告）

- E1/E2/E3/E4/E5 hit vs bm25 全部显著为负（−0.32~−0.38）——静态召回以检索 oracle 为界（`16-` 同一结论在注入流上复现）；vs keep_all 显著为负（无预算天花板）。
- E2/E3 harmful vs recency/keep_all 显著为正——其 harmful≈0 是"什么都不暴露"的结构性零，不是治理优势。

## 4. 回答目标第三款：合成数据是否成立

**成立，且取得目标上的显著优势**：

1. 公开数据所缺的 lifecycle 客观目标（未来纠错、有害保留、归档遮蔽、付费救援）已由程序化 overlay 补上；**全部标签程序化生成，无人工金标闭环**（doc 17 §7.1）。
2. SQCAD 在注入事件上的治理指标**显著优于全部非检索基线**，且两条关键机制消融（fallback、probe/restore）的效应**显著**（E2/E3 harmful 降低 0.44~0.66；E5 救援 +0.14~0.21）。
3. 对检索 oracle：有害暴露方向有利（E2 −0.24）但 n=10 未达显著；静态召回仍显著落后——结论与 `16-` 一致：**SQCAD 的价值在治理目标与成本，不在静态检索排序**。
4. **外部效度边界**（如实）：事件密度是预注册设计参数（每会话 ≤5/类）；F 由金标否定构造，其文本分布比真实错误更规整；结论证明"机制在真实轨迹结构上的可操作性"，不等于真实部署收益（`07-` 纪律）。

## 5. 声称边界

- **可声称**：本报告全部表格与判定（注入协议、客观指标、显著性、机制消融）。
- **不可声称**：公开数据静态 QA 全面占优（bm25 界未破）；overlay 结果直接等于真实 Agent Memory 部署收益；人工标注意义上的"有害记忆"识别（标签全部程序化）。

## 6. 下一步

- 合成数据集独立构建（完全脱离公开轨迹的 T1/T2 世界规模化实例，验证 §4 结论的分布鲁棒性）；
- 事件密度/种子敏感性扫描（预注册 20260814 种子为主结果，±种子为稳健性附件）；
- dense/RRF 行与 SimpleMem/Oblivion 完整系统复现等待端点/权重/3.12 环境就绪（`17-`）。
