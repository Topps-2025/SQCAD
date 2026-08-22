#!/bin/bash
# Cloud GPU Setup and Experiment Runner
# 在云端执行的初始化脚本

set -e

echo "=== Cloud GPU Environment Setup ==="
date

# 1. 检查环境
echo "1. Checking environment..."
pwd
df -h
nvidia-smi

# 2. 检查数据盘挂载
echo -e "\n2. Checking data disk..."
if [ -d "/root/autodl-tmp" ]; then
    echo "Data disk mounted at /root/autodl-tmp"
    DATA_DIR="/root/autodl-tmp"
elif [ -d "/mnt/data" ]; then
    echo "Data disk mounted at /mnt/data"
    DATA_DIR="/mnt/data"
else
    echo "No data disk found, using /root"
    DATA_DIR="/root"
fi

# 3. 创建工作目录
echo -e "\n3. Setting up work directory..."
WORK_DIR="$DATA_DIR/sqcad_workspace"
mkdir -p $WORK_DIR
cd $WORK_DIR
echo "Work directory: $WORK_DIR"

# 4. 检查 SQCAD 代码
echo -e "\n4. Checking SQCAD code..."
if [ -d "$WORK_DIR/SQCAD" ]; then
    echo "SQCAD directory exists"
    cd $WORK_DIR/SQCAD
    git status || echo "Not a git repo or git not available"
else
    echo "SQCAD directory not found"
    echo "Please upload SQCAD code to $WORK_DIR/"
fi

# 5. 检查 Python 环境
echo -e "\n5. Checking Python environment..."
python --version
pip list | grep -E "torch|transformers|vllm" || echo "Key packages not found"

# 6. 检查 vLLM 服务
echo -e "\n6. Checking vLLM service..."
if curl -s http://127.0.0.1:8000/v1/models > /dev/null; then
    echo "vLLM service is running"
    curl -s http://127.0.0.1:8000/v1/models | head -20
else
    echo "vLLM service not running"
fi

echo -e "\n=== Setup Complete ==="
echo "Data directory: $DATA_DIR"
echo "Work directory: $WORK_DIR"
echo "Ready for experiments"
