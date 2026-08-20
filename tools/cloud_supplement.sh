#!/bin/bash
# Cloud supplement batch (33- report): L3 theory-aligned + L2 strict-online.
# Run on the AutoDL box from /root/autodl-tmp/sqcad:
#   bash tools/cloud_supplement.sh [step]
# Optional step arg: 1 | 2 | 3 | 4 -- run only that block.
set -eo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=/root/autodl-tmp/sqcad/src:/root/autodl-tmp/sqcad
PY=/root/miniconda3/bin/python
mkdir -p logs remote_results/lifecycle_audit
ONLY="${1:-}"

if [ -z "$ONLY" ] || [ "$ONLY" = "1" ]; then
echo "=== [1/4] L3 theory-aligned family (sqcad_v2 / sqcad_v2_probe) ==="
$PY tools/l3_sqcad_v2.py 2>&1 | tee logs/l3_sqcad_v2.log
fi

if [ -z "$ONLY" ] || [ "$ONLY" = "2" ]; then
echo "=== [2/4] L2 strict-online baselines (memory_worth_online / causal_item_online) ==="
$PY -m sqcad.public_online_baselines \
    --longmemeval datasets/longmemeval_s_cleaned.json \
    --locomo datasets/locomo10.json \
    --qa-out-dir results/locomo_qa_online \
    --output results/public_online_baselines.json 2>&1 | tee logs/online_baselines.log
fi

if [ -z "$ONLY" ] || [ "$ONLY" = "3" ]; then
echo "=== [3/4] LoCoMo official scorer (frozen upstream evaluation.py) ==="
$PY tools/run_locomo_official_scorer_portable.py \
    --eval-file datasets/locomo_eval/evaluation.py \
    --pred-dir results/locomo_qa_online \
    --out results/locomo_official_qa_online.json 2>&1 | tee logs/locomo_official_online.log
fi

if [ -z "$ONLY" ] || [ "$ONLY" = "4" ]; then
echo "=== [4/4] Qwen3-Embedding substitute rows (tier B) ==="
if [ -z "$HF_ENDPOINT" ]; then export HF_ENDPOINT=https://hf-mirror.com; fi
# Mirror xet redirects to us.aws.cdn.hf.co which is unreachable from CN boxes
# (peer closes at the same byte on every resume). Disable xet so the mirror
# serves model.safetensors over plain LFS HTTP.
export HF_HUB_DISABLE_XET=1
export HF_HUB_ENABLE_HF_TRANSFER=0

for VER in 0.6B 8B; do
  case $VER in
    0.6B) MODEL=Qwen/Qwen3-Embedding-0.6B ;;
    8B)   MODEL=Qwen/Qwen3-Embedding-8B ;;
  esac
  echo "--- dense precompute ($VER) longmemeval_s ---"
  $PY tools/precompute_dense_qwen.py --dataset longmemeval_s \
      --model $MODEL --out results/dense_${VER}_lme.json
  echo "--- dense precompute ($VER) locomo ---"
  $PY tools/precompute_dense_qwen.py --dataset locomo \
      --model $MODEL --out results/dense_${VER}_locomo.json
  echo "--- merge caches + contract dense run ($VER) ---"
  $PY - <<EOF
import json
a = json.load(open("results/dense_${VER}_lme.json"))
b = json.load(open("results/dense_${VER}_locomo.json"))
cache = {**a["cache"], **b["cache"]}
json.dump({"model": a["model"], "budget": a["budget"],
           "cache": cache}, open("results/dense_cache_${VER}.json", "w"))
print(f"merged {len(cache)} samples")
EOF
  $PY -m sqcad.public_unified_contract \
      --longmemeval datasets/longmemeval_s_cleaned.json \
      --locomo datasets/locomo10.json \
      --datasets longmemeval_s,locomo \
      --policies dense \
      --dense-cache results/dense_cache_${VER}.json \
      --qa-out-dir results/locomo_qa_dense_${VER} \
      --output results/public_dense_${VER}.json 2>&1 | tee logs/dense_${VER}.log
  $PY tools/run_locomo_official_scorer_portable.py \
      --eval-file datasets/locomo_eval/evaluation.py \
      --pred-dir results/locomo_qa_dense_${VER} \
      --out results/locomo_official_qa_dense_${VER}.json \
      | tee logs/locomo_official_dense_${VER}.log
done
fi

echo "=== DONE ==="
