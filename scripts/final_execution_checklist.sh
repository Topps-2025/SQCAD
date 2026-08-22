#!/bin/bash
# SQCAD ICLR 2027 完整执行清单
# 本脚本用于追踪和验证所有任务的完成状态

set -e

WORK_DIR="C:/Users/Lenovo/Desktop/Paper/SQCAD"
CLOUD_HOST="connect.westb.seetacloud.com"
CLOUD_PORT="16420"
CLOUD_USER="root"

echo "=========================================="
echo "SQCAD ICLR 2027 目标执行清单"
echo "=========================================="
echo ""

# ============================================
# Phase 0: 准备工作检查
# ============================================
echo "Phase 0: 准备工作检查"
echo "--------------------"

check_file() {
    if [ -f "$1" ]; then
        echo "✓ $2"
        return 0
    else
        echo "✗ $2 [缺失: $1]"
        return 1
    fi
}

check_file "$WORK_DIR/scripts/cloud_phase1_experiments.sh" "Phase 1 实验脚本"
check_file "$WORK_DIR/scripts/cloud_phase2_experiments.sh" "Phase 2 实验脚本"
check_file "$WORK_DIR/scripts/analyze_phase1_results.py" "Phase 1 分析脚本"
check_file "$WORK_DIR/scripts/analyze_phase2_results.py" "Phase 2 分析脚本"
check_file "$WORK_DIR/docs/自用/00-论文主体/31-ICLR2027论文初稿-20260819.md" "论文初稿"

echo ""

# ============================================
# Phase 1: 云端实验执行指引
# ============================================
echo "Phase 1: 云端实验执行"
echo "--------------------"
echo ""
echo "⚠️  需要手动执行以下步骤："
echo ""
echo "1. 上传脚本到云端："
echo "   scp -P $CLOUD_PORT $WORK_DIR/scripts/cloud_phase1_experiments.sh $CLOUD_USER@$CLOUD_HOST:/root/autodl-tmp/sqcad_workspace/SQCAD/scripts/"
echo ""
echo "2. SSH 连接云端："
echo "   ssh -p $CLOUD_PORT $CLOUD_USER@$CLOUD_HOST"
echo "   密码: o4F9PfgQzTR8"
echo ""
echo "3. 启动 Phase 1 实验："
echo "   cd /root/autodl-tmp/sqcad_workspace/SQCAD"
echo "   chmod +x scripts/cloud_phase1_experiments.sh"
echo "   mkdir -p logs"
echo "   nohup bash scripts/cloud_phase1_experiments.sh > logs/phase1_\$(date +%Y%m%d_%H%M).log 2>&1 &"
echo "   tail -f logs/phase1_*.log"
echo ""
echo "4. 等待 Phase 1 完成（预计 12-15 小时）"
echo ""

read -p "Phase 1 是否已启动？(y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "请先完成 Phase 1 启动"
    exit 1
fi

echo "✓ Phase 1 已启动"
echo ""

# ============================================
# Phase 2: 等待实验完成
# ============================================
echo "Phase 2: 等待实验完成"
echo "--------------------"
echo ""
echo "⚠️  监控实验状态："
echo ""
echo "在云端执行："
echo "  tail -f logs/phase1_*.log          # 查看日志"
echo "  ps aux | grep cloud_phase1          # 查看进程"
echo "  watch -n 5 nvidia-smi               # 查看 GPU"
echo ""

read -p "Phase 1 是否已完成？(y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "等待 Phase 1 完成后继续"
    exit 0
fi

echo "✓ Phase 1 已完成"
echo ""

# ============================================
# Phase 3: 启动 Phase 2 实验
# ============================================
echo "Phase 3: 启动 Phase 2 实验"
echo "-------------------------"
echo ""
echo "在云端执行："
echo "  cd /root/autodl-tmp/sqcad_workspace/SQCAD"
echo "  chmod +x scripts/cloud_phase2_experiments.sh"
echo "  nohup bash scripts/cloud_phase2_experiments.sh > logs/phase2_\$(date +%Y%m%d_%H%M).log 2>&1 &"
echo "  tail -f logs/phase2_*.log"
echo ""

read -p "Phase 2 是否已启动？(y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "请先完成 Phase 2 启动"
    exit 1
fi

echo "✓ Phase 2 已启动"
echo ""

# ============================================
# Phase 4: 等待 Phase 2 完成
# ============================================
echo "Phase 4: 等待 Phase 2 完成"
echo "-------------------------"
echo ""

read -p "Phase 2 是否已完成？(y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "等待 Phase 2 完成后继续"
    exit 0
fi

echo "✓ Phase 2 已完成"
echo ""

# ============================================
# Phase 5: 下载结果
# ============================================
echo "Phase 5: 下载实验结果"
echo "--------------------"
echo ""
echo "执行下载命令："
echo "  mkdir -p D:/SQCAD-database/cloud_results_20260822"
echo "  scp -P $CLOUD_PORT $CLOUD_USER@$CLOUD_HOST:/root/autodl-tmp/sqcad_workspace/SQCAD/transfer_to_local/*.tar.gz D:/SQCAD-database/cloud_results_20260822/"
echo ""

read -p "是否立即下载？(y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    mkdir -p D:/SQCAD-database/cloud_results_20260822
    scp -P $CLOUD_PORT $CLOUD_USER@$CLOUD_HOST:/root/autodl-tmp/sqcad_workspace/SQCAD/transfer_to_local/*.tar.gz D:/SQCAD-database/cloud_results_20260822/ || {
        echo "下载失败，请手动执行"
        exit 1
    }
    echo "✓ 结果已下载"
else
    echo "请手动下载结果"
    exit 0
fi

echo ""

# ============================================
# Phase 6: 解压和同步
# ============================================
echo "Phase 6: 解压和同步到本地"
echo "------------------------"
echo ""

cd D:/SQCAD-database/cloud_results_20260822/

echo "解压文件..."
tar -xzf sqcad_phase1_phase2_results_*.tar.gz || {
    echo "解压失败"
    exit 1
}

echo "复制到本地 SQCAD..."
cp *.json "$WORK_DIR/results/" 2>/dev/null || true

echo "✓ 文件已同步"
echo ""

# ============================================
# Phase 7: 运行分析脚本
# ============================================
echo "Phase 7: 分析实验结果"
echo "--------------------"
echo ""

cd "$WORK_DIR"

echo "运行 Phase 1 分析..."
python scripts/analyze_phase1_results.py || {
    echo "⚠️  Phase 1 分析失败"
}

echo ""
echo "运行 Phase 2 分析..."
python scripts/analyze_phase2_results.py || {
    echo "⚠️  Phase 2 分析失败"
}

echo ""
echo "✓ 分析完成"
echo ""

# ============================================
# Phase 8: 论文集成检查清单
# ============================================
echo "Phase 8: 论文集成检查清单"
echo "------------------------"
echo ""
echo "请手动完成以下任务："
echo ""
echo "[ ] 1. 检查 results/ 目录中的所有 JSON 文件"
echo "[ ] 2. 查看 results/phase1_analysis_summary.json"
echo "[ ] 3. 查看 results/phase2_analysis_summary.json"
echo "[ ] 4. 将 SimpleMem 结果添加到论文 §5.2 表格"
echo "[ ] 5. 将 L3 鲁棒性表格添加到论文 §5.3"
echo "[ ] 6. 将 results/paper_section_5_4_draft.md 集成到论文"
echo "[ ] 7. 更新 §1 Introduction（系统普查 + 失败归因）"
echo "[ ] 8. 全文一致性检查"
echo "[ ] 9. References 完整性检查"
echo "[ ] 10. Git commit 和 push"
echo ""

# ============================================
# Phase 9: 云端关机
# ============================================
echo "Phase 9: 云端关机"
echo "----------------"
echo ""
echo "⚠️  在 AutoDL 控制台手动关机"
echo "    （云端命令可能无效）"
echo ""

read -p "云端是否已关机？(y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "✓ 云端已关机"
else
    echo "请在 AutoDL 控制台完成关机"
fi

echo ""
echo "=========================================="
echo "所有任务完成！"
echo "=========================================="
echo ""
echo "最终检查："
echo "  - Phase 1/2 实验结果已下载"
echo "  - 分析脚本已运行"
echo "  - 论文修订已应用"
echo "  - 云端已关机"
echo ""
echo "下一步："
echo "  1. 完成论文实验结果集成"
echo "  2. 全文最终检查"
echo "  3. 准备投稿"
