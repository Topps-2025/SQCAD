@echo off
REM SQCAD 云端实验自动化脚本
REM 使用 PuTTY 的 plink 工具进行自动化 SSH

echo ========================================
echo SQCAD 云端实验启动脚本
echo ========================================
echo.

REM 设置变量
set CLOUD_HOST=connect.westb.seetacloud.com
set CLOUD_PORT=16420
set CLOUD_USER=root
set CLOUD_PASS=o4F9PfgQzTR8
set LOCAL_SQCAD=C:\Users\Lenovo\Desktop\Paper\SQCAD
set CLOUD_WORK=/root/autodl-tmp/sqcad_workspace/SQCAD

echo 步骤 1: 上传实验脚本到云端...
echo.

REM 使用 pscp (PuTTY SCP) 上传文件
echo 上传 Phase 1 脚本...
echo %CLOUD_PASS%| pscp -P %CLOUD_PORT% -pw %CLOUD_PASS% "%LOCAL_SQCAD%\scripts\cloud_phase1_experiments.sh" %CLOUD_USER%@%CLOUD_HOST%:%CLOUD_WORK%/scripts/

echo 上传 Phase 2 脚本...
echo %CLOUD_PASS%| pscp -P %CLOUD_PORT% -pw %CLOUD_PASS% "%LOCAL_SQCAD%\scripts\cloud_phase2_experiments.sh" %CLOUD_USER%@%CLOUD_HOST%:%CLOUD_WORK%/scripts/

echo.
echo 步骤 2: 连接云端并启动实验...
echo.

REM 创建远程执行命令
(
echo cd %CLOUD_WORK%
echo chmod +x scripts/cloud_phase1_experiments.sh
echo nohup bash scripts/cloud_phase1_experiments.sh ^> logs/phase1_$(date +%%Y%%m%%d_%%H%%M^).log 2^>^&1 ^&
echo echo "Phase 1 实验已启动，日志位置: logs/phase1_*.log"
echo tail -f logs/phase1_*.log
) > %TEMP%\sqcad_remote_commands.txt

echo 使用 SSH 连接并执行...
echo 密码: %CLOUD_PASS%
echo.

REM 使用 plink 执行远程命令
plink -P %CLOUD_PORT% -pw %CLOUD_PASS% %CLOUD_USER%@%CLOUD_HOST% < %TEMP%\sqcad_remote_commands.txt

echo.
echo ========================================
echo 如果 plink 不可用，请手动执行以下步骤：
echo ========================================
echo.
echo 1. 打开 Git Bash 或 PowerShell
echo 2. 执行: ssh -p 16420 root@connect.westb.seetacloud.com
echo 3. 输入密码: o4F9PfgQzTR8
echo 4. 执行以下命令:
echo.
echo    cd /root/autodl-tmp/sqcad_workspace/SQCAD
echo    chmod +x scripts/cloud_phase1_experiments.sh
echo    nohup bash scripts/cloud_phase1_experiments.sh ^> logs/phase1_$(date +%%Y%%m%%d_%%H%%M^).log 2^>^&1 ^&
echo    tail -f logs/phase1_*.log
echo.
echo ========================================

pause
