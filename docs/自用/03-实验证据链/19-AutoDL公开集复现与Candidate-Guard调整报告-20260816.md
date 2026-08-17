# AutoDL 公开集复现与 Candidate-Guard 调整报告（2026-08-16）

## 1. 执行与存储审计

- AutoDL 登录端口：`54834`。
- 所有代码副本、数据、环境、模型缓存、结果和日志均放在：
  `/root/autodl-tmp/SQCAD/database`。
- `/root/autodl-tmp` 为独立 50 GB XFS 数据盘；本轮运行前约占用 0.5 GB。
- GPU：NVIDIA GeForce RTX 4080 SUPER，32 GB。
- Python：3.10.8；独立环境：`envs/sqcad-py310`。
- LongMemEval-S 与 LoCoMo 上传后 SHA-256 与本机源文件一致。

## 2. 基线与统一合同

在同一 chronological stream、同一 workspace budget（12）、同一 extractive reader、同一 evaluator 和同一成本记录下运行：

- R1：BM25、keep-all；
- 原始 SQCAD；
- `sqcad_candidate_guard_1/2/4`；
- `sqcad_no_probe`、`sqcad_no_restore` 对照。

LongMemEval-S 使用时间掩码，LoCoMo 使用冻结官方 QA 顺序。策略决策不读取 gold answer、needed ids 或 evidence ids。

## 3. Bad case 归因

第一轮结果显示，原 SQCAD 的主要失败不是“持久治理后无法排序”，而是支持证据没有进入当前可暴露池。例如：

| 问题 | 原 SQCAD | BM25 | 归因 |
|---|---|---|---|
| John 为慈善工作与何组织合作？ | 返回 hard work 的无关句 | 返回 local organization | 支持 turn 未进入 SQCAD 工作区 |
| Jolene 喜欢什么瑜伽姿势？ | 返回无关对话句 | 返回 savasana | 已有候选中的错误 turn 竞争，缺少证据覆盖保底 |
| Evan 新饮食限制什么？ | 只返回泛化 diet 句 | 返回 two ginger snaps a day | 细粒度支持证据被持久预算淘汰 |

因此调整点放在“证据提议/候选覆盖”，不放宽 qualification，也不把 QA 相似度直接当成持久治理授权。

## 4. 调整方案

新增 `sqcad_candidate_guard_1/2/4`：在每个 QA 时点，从全量可见消息中提出至多 1、2 或 4 个 BM25 候选，候选只进入当前一次性暴露池；候选不会直接写入 `storage_ids`。持久写入仍必须经过原有 qualification/restore 路径。

这保持了理论最小条件：

1. 关联信号只能 propose，不能 authorize；
2. 识别集合跨动作边界时仍然 unresolved/defer；
3. probe 是有成本的有限信息获取，不是 keep-all；
4. 只有通过既有资格和 restore 规则的对象才可改变持久访问状态。

## 5. AutoDL 全量结果

### 5.1 LongMemEval-S

| 方法 | Hit | Recall | Exposure tokens | Storage tokens | 平均 probes |
|---|---:|---:|---:|---:|---:|
| BM25 | 0.967 | 0.323 | 1,973.0 | 74,092.1 | 0.0 |
| SQCAD | 0.785 | 0.118 | 2,711.2 | 1,617.0 | 1.0 |
| Guard-1 | 0.915 | 0.153 | 2,701.0 | 1,616.0 | 2.0 |
| Guard-2 | 0.929 | 0.179 | 2,683.5 | 1,616.0 | 3.0 |
| Guard-4 | 0.950 | 0.224 | 2,632.1 | 1,615.0 | 5.0 |

### 5.2 LoCoMo 官方 scorer

1986 个 QA，冻结 `task_eval/evaluation.py`：

| 方法 | 官方 token-F1 | Evidence recall |
|---|---:|---:|
| BM25 | 0.0454 | 0.5296 |
| 原 SQCAD | 0.0344 | 0.1928 |
| Guard-1 | 0.0455 | 0.3249 |
| Guard-2 | 0.0465 | 0.3835 |
| Guard-4 | 0.0475 | 0.4480 |

原始 `sqcad_no_probe` 和 `sqcad_no_restore` 的官方 F1 分别约为 0.0161 和 0.0163，说明恢复/探测通道不是装饰性模块。

## 6. 最终选择

推荐主框架采用 **Guard-1**：它是 candidate coverage 机制的最小成本版本，在 LoCoMo 官方 F1（0.0455）达到并略超过 BM25（0.0454），同时比 Guard-2/4 少付出 probe 成本。Guard-2/4 作为成本—效果扩展和敏感性分析保留。

这不是 SOTA 声称，也不是因果发现已在公开集被证明；公开集证据只支持：在固定 reader 与预算下，受限的候选证据保底能修复原 SQCAD 的主要 coverage bad case，同时不破坏“资格授权”理论边界。

## 7. 复核文件

- 主结果：`results/public_candidate_guard_budget_scan.json`。
- 官方 LoCoMo：`results/locomo_official_candidate_guard_budget_scan.json`。
- QA 逐题预测：`results/locomo_qa_candidate_guard_budget_scan/`。
- 修改源文件：`src/sqcad/public_unified_contract.py`。
- 新增结构测试：`tests/test_public_unified_contract.py`。
