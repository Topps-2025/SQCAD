#!/bin/bash
# SQCAD Phase 1 实验：基础补强
# 在云 GPU 上执行

set -e

WORK_DIR="/root/autodl-tmp/sqcad_workspace/SQCAD"
RESULTS_DIR="$WORK_DIR/results"
DATA_DIR="$WORK_DIR/data"

echo "=== SQCAD Phase 1: 基础补强实验 ==="
echo "开始时间: $(date)"
echo "工作目录: $WORK_DIR"

cd $WORK_DIR

# ============================================
# Task 1: L3 多参数鲁棒性（3 天）
# ============================================
echo -e "\n### Task 1: L3 多参数鲁棒性扫描 ###"

# 9 组参数配置
GAMMA_VALUES=(0.90 0.95 0.99)
HARM_VALUES=(15 20 25)
PROBE_COST=1.0
TASK_VALUE=10

for GAMMA in "${GAMMA_VALUES[@]}"; do
    for HARM in "${HARM_VALUES[@]}"; do
        echo "Running: GAMMA=$GAMMA, HARM_PENALTY=$HARM"

        OUTPUT_FILE="$RESULTS_DIR/l3_robust_gamma${GAMMA}_harm${HARM}.json"

        python src/sqcad/lifecycle_bench.py \
            --gamma $GAMMA \
            --task_value $TASK_VALUE \
            --harm_penalty $HARM \
            --probe_cost $PROBE_COST \
            --n_episodes 1380 \
            --output $OUTPUT_FILE \
            2>&1 | tee "$RESULTS_DIR/l3_robust_gamma${GAMMA}_harm${HARM}.log"

        echo "Completed: $OUTPUT_FILE"
    done
done

echo "L3 鲁棒性扫描完成"

# ============================================
# Task 2: SimpleMem n=100 运行（4-6 小时）
# ============================================
echo -e "\n### Task 2: SimpleMem n=100 完整运行 ###"

# 检查 vLLM 服务
if ! curl -s http://127.0.0.1:8000/v1/models > /dev/null; then
    echo "警告: vLLM 服务未运行，尝试启动..."
    # 这里需要根据实际情况调整 vLLM 启动命令
    nohup python -m vllm.entrypoints.openai.api_server \
        --model /root/autodl-tmp/hf_cache/hub/models--Qwen--Qwen3-8B \
        --port 8000 \
        --tensor-parallel-size 1 \
        --gpu-memory-utilization 0.9 \
        > $RESULTS_DIR/vllm.log 2>&1 &
    sleep 30
fi

# 运行 SimpleMem
python tools/run_simplemem.py \
    --dataset longmemeval_s \
    --n_samples 100 \
    --llm_base_url http://127.0.0.1:8000/v1 \
    --llm_model qwen3-8b \
    --embedding_model /root/autodl-tmp/hf_cache/hub/models--Qwen--Qwen3-Embedding-0.6B \
    --workspace_budget 12 \
    --seeds 20260812,20260817 \
    --output $RESULTS_DIR/simplemem_lme_s_n100.json \
    2>&1 | tee $RESULTS_DIR/simplemem_n100.log

echo "SimpleMem n=100 完成"

# ============================================
# Task 3: 端到端任务实验准备
# ============================================
echo -e "\n### Task 3: 端到端任务数据准备 ###"

# 选取 8 个任务
python scripts/select_end_to_end_tasks.py \
    --sources agentbench,gaia \
    --n_tasks 8 \
    --episodes_per_task 15 \
    --criteria multi_turn,long_memory,clear_goal \
    --output $DATA_DIR/end_to_end_tasks.json

echo "端到端任务数据准备完成"

# ============================================
# 汇总结果
# ============================================
echo -e "\n=== Phase 1 实验完成 ==="
echo "结束时间: $(date)"
echo -e "\n生成的文件："
ls -lh $RESULTS_DIR/l3_robust_*.json
ls -lh $RESULTS_DIR/simplemem_lme_s_n100.json
ls -lh $DATA_DIR/end_to_end_tasks.json

# 创建结果摘要
cat > $RESULTS_DIR/phase1_summary.txt <<EOF
SQCAD Phase 1 实验摘要
完成时间: $(date)

1. L3 鲁棒性扫描: 9 组参数完成
   - GAMMA: 0.90, 0.95, 0.99
   - HARM_PENALTY: 15, 20, 25
   - 文件: l3_robust_*.json

2. SimpleMem n=100: 完成
   - 文件: simplemem_lme_s_n100.json

3. 端到端任务准备: 完成
   - 8 任务 × 15 episodes
   - 文件: end_to_end_tasks.json

下一步:
- 分析 L3 鲁棒性结果
- 分析 SimpleMem 结果
- 运行端到端实验 (Phase 2)
EOF

cat $RESULTS_DIR/phase1_summary.txt
