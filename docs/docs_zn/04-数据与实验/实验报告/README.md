# 实验报告

> **目录说明（2026-08-12 重组）**：实验报告已按论文证据链重新组织——
>
> - **核心实验报告（外部，逻辑顺序）**：`docs/实验证据链/` —— ① research gap 佐证实验（命题 A/B/C 反例 + 公平性审查）→ ② 形式化定理与陈述（`docs/研究逻辑与理论证明/11-形式化定理陈述与证明.md`）→ ③ 充分识别实验 → ④ 必要性与门控下界 → ⑤ 现实、成本与统计支撑。研究逻辑路线见 `docs/草稿-draft/研究路线与方案/00-ResearchGap到充分性与必要性的完整实验逻辑线-20260813.md`。
> - **非核心与旧版本报告（草稿归档）**：`docs/草稿-draft/实验报告/`（LongMemEval 系列、作用域、解构抽象、最小框架、Gate-A、早期校准与基线报告、Gap v1 旧版等）。

---

## 工程原型说明（保留）

论文架构的最小事务性代码位于仓库 `src/sqcad/`，不实现 LLM 解构器或因果估计器。

`causal_memory_store.py` 使用 SQLite 建立：

- 不可替换的 `evidence` 来源记录；
- 指向来源的 `factor`；
- 具有作用域、稳定性、证据覆盖和多因子支持的 `abstract_rule`；
- 原子化的 decision-level 日志，记录候选集、行为策略动作、真实 propensity、暴露、采用、Agent 行动和结果；
- 可审计的 `governance_transition`；
- 归档、恢复、作用域过滤和完整 provenance 查询。

运行测试：

```powershell
cd "C:\Users\Lenovo\Desktop\Paper\SQCAD"
# 工程原型代码位于 src/sqcad/
python -m unittest -v test_causal_memory_store.py
python -m unittest -v test_unified_agent_memory_runner.py
```

当前事务存储测试覆盖：无来源规则禁止、独立支持门槛、跨主体作用域阻断、规则证据追溯、归档后阻断激活及恢复回滚、downweight/isolate 可逆迁移、decision-level 日志回放和 propensity 合法性校验。该原型只证明工程不变量可以实现，不证明因果规则本身正确。

`unified_agent_memory_runner.py` 进一步在同一候选流、任务序列、工作区预算和 evaluator 下运行 recency、frequency、fade-like、outcome-feedback-like、item-level causal 与 risk-gated decomposition–abstraction 策略，并将 exposure、adoption、action、outcome 和状态迁移写入上述存储。30-seed 工程 smoke 结果见 `docs/草稿-draft/实验报告/统一AgentMemory工作流Runner初步实验报告.md`；它不是公开 benchmark 结果。完整框架与实验合同见 `docs/docs_zn/07-杂项草稿与实验记录/00-最新版框架完整设计与实验方案.md`。
