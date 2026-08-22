#!/bin/bash
# 本地执行脚本：上传文件到云端并启动实验
# 在 Git Bash 中运行

set -e

CLOUD_HOST="connect.westb.seetacloud.com"
CLOUD_PORT="16420"
CLOUD_USER="root"
CLOUD_WORK="/root/autodl-tmp/sqcad_workspace/SQCAD"
LOCAL_SQCAD="C:/Users/Lenovo/Desktop/Paper/SQCAD"

echo "========================================="
echo "SQCAD 云端实验部署脚本"
echo "========================================="
echo ""

# 步骤 1: 上传实验脚本
echo "步骤 1: 上传实验脚本到云端..."
echo ""

echo "上传 Phase 1 脚本..."
scp -P $CLOUD_PORT "$LOCAL_SQCAD/scripts/cloud_phase1_experiments.sh" $CLOUD_USER@$CLOUD_HOST:$CLOUD_WORK/scripts/ || {
    echo "错误: Phase 1 脚本上传失败"
    echo "请手动执行: scp -P 16420 C:/Users/Lenovo/Desktop/Paper/SQCAD/scripts/cloud_phase1_experiments.sh root@connect.westb.seetacloud.com:/root/autodl-tmp/sqcad_workspace/SQCAD/scripts/"
    exit 1
}

echo "上传 Phase 2 脚本..."
scp -P $CLOUD_PORT "$LOCAL_SQCAD/scripts/cloud_phase2_experiments.sh" $CLOUD_USER@$CLOUD_HOST:$CLOUD_WORK/scripts/ || {
    echo "警告: Phase 2 脚本上传失败，继续..."
}

echo ""
echo "上传完成！"
echo ""

# 步骤 2: 连接云端并启动实验
echo "步骤 2: 连接云端..."
echo "SSH 命令: ssh -p $CLOUD_PORT $CLOUD_USER@$CLOUD_HOST"
echo "密码: o4F9PfgQzTR8"
echo ""

echo "========================================="
echo "在云端执行以下命令启动 Phase 1："
echo "========================================="
echo ""
echo "cd $CLOUD_WORK"
echo "chmod +x scripts/cloud_phase1_experiments.sh"
echo "mkdir -p logs"
echo "nohup bash scripts/cloud_phase1_experiments.sh > logs/phase1_\$(date +%Y%m%d_%H%M).log 2>&1 &"
echo "echo \"实验已启动，进程 ID: \$!\""
echo "tail -f logs/phase1_*.log"
echo ""
echo "========================================="

# 提供手动连接选项
echo ""
read -p "是否立即连接到云端？(y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "连接中..."
    ssh -p $CLOUD_PORT $CLOUD_USER@$CLOUD_HOST
else
    echo ""
    echo "稍后手动连接: ssh -p $CLOUD_PORT $CLOUD_USER@$CLOUD_HOST"
    echo "密码: o4F9PfgQzTR8"
fi
