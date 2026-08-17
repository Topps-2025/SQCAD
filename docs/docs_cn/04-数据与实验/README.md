# 04 数据与实验

本文给出数据集与关键数值；完整实验流程、审计与可复现证据在内部 `docs/自用/03-实验证据链/`（00–21 编号报告），实验方案总入口为 `docs/自用/00-论文主体/23-SQCAD完整实验方案-理论公开自建消融-20260817.md`。

## 1. 公开数据：外部效度（L2）

**合同**：相同 chronological stream、workspace budget、reader、evaluator 与成本记录；AutoDL RTX 4080 SUPER 复核与本地一致（云端已关机）。

| 方法 | LongMemEval-S Hit | LongMemEval-S Recall | LoCoMo 官方 token-F1 | 解释 |
|---|---:|---:|---:|---|
| BM25 | 0.967 | 0.323 | 0.0454 | 静态检索覆盖上界/成本对照，不是持久治理方法 |
| 原 SQCAD | 0.785 | 0.118 | 0.0344 | 持久存储低，候选覆盖不足 |
| Guard-1 | 0.915 | 0.153 | 0.0455 | 推荐的最小 coverage 修复：至多一个 BM25 候选入当前读取池 |
| Guard-2 | 0.929 | 0.179 | 0.0465 | 更高覆盖，更多 probe |
| Guard-4 | 0.950 | 0.224 | 0.0475 | 覆盖更高，成本也更高 |

结论边界：受限、一次性的 candidate guard 能修复证据覆盖 bad case 并保持资格授权边界；**不能**单独证明 keep/archive 的长期因果价值。dense/RRF 因官方权重不可得未复现（来源：`自用/03-实验证据链/19-`）。

## 2. 自建数据：内部效度（L3）

**SQCAD-LifecycleBench**：1,380 个 keep/archive 同源反事实 episode（6 机制家族 × 200 + 3 对照家族 × 50 + 15 观测等价对）。每个 episode 有同一未来流下 keep/archive 两支 rollout，真实长期 outcome 只在隐藏层，public trace 不含 oracle 标签。split 818/354/208；远端 AutoDL 重建 hash 与本地一致。构建方案见 `自用/00-论文主体/22-`。

| 策略 | 平均 lifecycle value | regret | oracle 一致率 | false-commit |
|---|---:|---:|---:|---:|
| oracle_policy（上界） | +0.964 | 0.015 | 1.000 | 0.000 |
| probe_willing（archive 除非 POSITIVE） | +0.865 | 0.115 | 0.906 | 0.072 |
| SQCAD + lineage conflict→archive | −0.278 | 1.258 | 0.744 | 0.228 |
| archive_all | −2.790 | 3.770 | 0.459 | 0.000 |
| storage12 / Memory-Worth proxy | −3.476 | 4.455 | 0.703 | 0.181 |
| 原 SQCAD certificate / event rule | −8.901 | 9.880 | 0.663 | 0.409 |
| keep-all / recency2 | −10.280 | 11.260 | 0.541 | 0.409 |

配对 bootstrap（seed 20260817）显示：conflict 变体较原证书显著 +8.62；probe_willing 显著 +9.77；reference certificate 与可见事件规则逐 episode 相同（0 分歧，如实报告）。

## 3. 公允性审计（四通道）

| 通道 | 判据 | 结果 |
|---|---|---|
| 真值可独立检验 | R5 第二实现位级一致 + 远端重建 hash | 1380/1380 一致 ✅ |
| 失败可以发生 | 基线矩阵 12 个非平凡策略分离 | 11 个显著分离 ✅ |
| 泛化可被挑战 | R3 未见机制 holdout | 12/15 全转移 + 3 个机制边界如实报告 ✅ |
| 评价不可被猜 | R1 元数据捷径上界 + R4 预注册 13 行 + R7 发布包 | 全命中 ✅ |

R2 标签敏感性：GAMMA=0.7（36.2% 翻转）与 TAU_TOL=1.0（32.6%）脆弱——经济/判定参数敏感，已按预注册重定位到 $\mathrm{GAMMA}\in[0.9,0.99]$ 有效域；语义类常数 0 翻转。R6 人类锚定（28 case 盲化导出）待外部判官。

## 4. 框架修改判定

1. **lineage conflict → archive**（原保守 keep）：conflict 变体全局显著 +8.62，version_update/update_before 上 −119.53 → −0.54（=oracle 上界）——确认修改；
2. **hitchhiker association-only → archive**：无独立信号（仅关联暴露）不应 keep；机制化路径留 Phase B 精化——确认方向；
3. **future_in_s2 需 scope 前瞻**：比"存在跨 scope 任务"更精细的信号需要（未来任务是否**需要**决策记忆）——确认问题、暂缓修改，列为 Phase B 端到端第一验证点。

## 5. 复现

- 测试：47 项合同测试 + 23 项公允性测试全绿；R5 1380/1380 位级一致。
- 资产：`src/sqcad/lifecycle_bench/`、`tests/test_lifecycle_bench_contract.py`、`tools/lifecycle_fairness.py`、`remote_results/lifecycle_audit/`。
- 遗留：R6 判官批次、Phase B 端到端（修改 #3 第一验证点）、核心具名基线扩展（FadeMem/Oblivion/Memory Worth/DeMem/SimpleMem 按统一合同分栏）。
