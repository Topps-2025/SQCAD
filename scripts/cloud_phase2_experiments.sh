#!/bin/bash
# SQCAD Phase 2 实验：闭环验证（端到端 + 问题量化）
# 在云 GPU 上执行

set -e

WORK_DIR="/root/autodl-tmp/sqcad_workspace/SQCAD"
RESULTS_DIR="$WORK_DIR/results"
DATA_DIR="$WORK_DIR/data"

echo "=== SQCAD Phase 2: 闭环验证实验 ==="
echo "开始时间: $(date)"
echo "工作目录: $WORK_DIR"

cd $WORK_DIR

# ============================================
# Task 1: 端到端任务实验（2 周并行）
# ============================================
echo -e "\n### Task 1: 端到端任务成功率实验 ###"

# 检查任务数据
if [ ! -f "$DATA_DIR/end_to_end_tasks.json" ]; then
    echo "错误: 任务数据不存在，请先运行 Phase 1"
    exit 1
fi

# 检查 vLLM 服务
if ! curl -s http://127.0.0.1:8000/v1/models > /dev/null; then
    echo "错误: vLLM 服务未运行"
    exit 1
fi

# 运行 4 个 baseline（并行或串行）
STRATEGIES=("full_store" "sqcad" "recency" "stream")

for STRATEGY in "${STRATEGIES[@]}"; do
    echo "运行 baseline: $STRATEGY"

    python experiments/run_end_to_end.py \
        --tasks $DATA_DIR/end_to_end_tasks.json \
        --strategy $STRATEGY \
        --llm gpt-4 \
        --workspace_budget 12 \
        --output $RESULTS_DIR/end_to_end_${STRATEGY}.json \
        2>&1 | tee $RESULTS_DIR/end_to_end_${STRATEGY}.log

    echo "完成: $STRATEGY"
done

# 自动评估
echo -e "\n评估任务完成率..."
python analysis/evaluate_task_completion.py \
    --results $RESULTS_DIR/end_to_end_*.json \
    --output $RESULTS_DIR/end_to_end_metrics.json

echo "端到端实验完成"

# ============================================
# Task 2: 系统普查（1 周）
# ============================================
echo -e "\n### Task 2: Agent 系统 Memory 管理普查 ###"

# 15 个系统列表
SYSTEMS="autogpt,babyagi,gpt-researcher,langchain-agents,agentgpt,supergpt,metagpt,openagents,hugginggpt,jarvis,voyager,reflexion,memgpt,generative-agents,sqcad"

python scripts/survey_agent_systems.py \
    --systems $SYSTEMS \
    --output $RESULTS_DIR/system_survey.json \
    2>&1 | tee $RESULTS_DIR/system_survey.log

# 生成报告
python analysis/survey_report.py \
    --survey $RESULTS_DIR/system_survey.json \
    --output $RESULTS_DIR/system_memory_tiers.tex

echo "系统普查完成"

# ============================================
# Task 3: 失败归因分析（1 周）
# ============================================
echo -e "\n### Task 3: 任务失败归因分析 ###"

# 抽样 100 失败 episodes
python scripts/sample_failures.py \
    --datasets longmemeval,locomo,agentbench \
    --n_episodes 100 \
    --failure_criteria "hit==0 or f1<0.02 or completion==0" \
    --output $DATA_DIR/failure_sample.json

echo "失败样本已导出到: $DATA_DIR/failure_sample.json"
echo "需要人工标注，请在本地完成标注后回传"

# ============================================
# 汇总结果
# ============================================
echo -e "\n=== Phase 2 实验完成 ==="
echo "结束时间: $(date)"
echo -e "\n生成的文件："
ls -lh $RESULTS_DIR/end_to_end_*.json
ls -lh $RESULTS_DIR/system_survey.json
ls -lh $DATA_DIR/failure_sample.json

# 创建结果摘要
cat > $RESULTS_DIR/phase2_summary.txt <<EOF
SQCAD Phase 2 实验摘要
完成时间: $(date)

1. 端到端任务实验: 完成
   - 4 个 baselines: full_store, sqcad, recency, stream
   - 8 任务 × 15 episodes = 120 episodes
   - 文件: end_to_end_*.json, end_to_end_metrics.json

2. 系统普查: 完成
   - 15 个 Agent 系统
   - 文件: system_survey.json, system_memory_tiers.tex

3. 失败归因: 抽样完成
   - 100 failure episodes
   - 需要人工标注
   - 文件: failure_sample.json

下一步:
- 人工验证端到端结果（20% 抽样）
- 人工标注失败原因（2 人）
- 分析所有结果
- 论文集成 (Phase 3)
EOF

cat $RESULTS_DIR/phase2_summary.txt

# ============================================
# 准备数据回传
# ============================================
echo -e "\n### 准备数据回传 ###"

TRANSFER_DIR="$WORK_DIR/transfer_to_local"
mkdir -p $TRANSFER_DIR

# 打包 Phase 1 + Phase 2 结果
tar -czf $TRANSFER_DIR/sqcad_phase1_phase2_results_$(date +%Y%m%d).tar.gz \
    -C $RESULTS_DIR \
    l3_robust_*.json \
    simplemem_lme_s_n100.json \
    end_to_end_*.json \
    system_survey.json \
    phase1_summary.txt \
    phase2_summary.txt

# 打包数据
tar -czf $TRANSFER_DIR/sqcad_phase2_data_$(date +%Y%m%d).tar.gz \
    -C $DATA_DIR \
    end_to_end_tasks.json \
    failure_sample.json

echo "数据已打包到: $TRANSFER_DIR"
ls -lh $TRANSFER_DIR/*.tar.gz

echo -e "\n回传命令（在本地执行）："
echo "scp -P 16420 root@connect.westb.seetacloud.com:$TRANSFER_DIR/*.tar.gz D:/SQCAD-database/"
