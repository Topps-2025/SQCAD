#!/bin/bash
# Cloud-side step-4 dense substitute rows for ONE model size (tier B,
# Qwen3-Embedding).  Mirrors cloud_supplement.sh step-4 block, with the
# --data fix (script default data paths are Windows-local) and offline HF
# loading (files pre-placed in the HF cache from ModelScope, non-xet).
# Usage: bash tools/cloud_step4_dense.sh 0.6B|8B
set -u
cd /root/autodl-tmp/sqcad
export PYTHONPATH=/root/autodl-tmp/sqcad/src:/root/autodl-tmp/sqcad
export HF_HUB_OFFLINE=1
PY=/root/miniconda3/bin/python
VER="$1"
MODEL="Qwen/Qwen3-Embedding-${VER}"
case "$VER" in
  0.6B|8B) ;;
  *) echo "usage: $0 0.6B|8B"; exit 1 ;;
esac

echo "--- dense precompute ($VER) longmemeval_s ---"
$PY tools/precompute_dense_qwen.py --dataset longmemeval_s \
    --data datasets/longmemeval_s_cleaned.json \
    --model "$MODEL" --out "results/dense_${VER}_lme.json" || exit 1
echo "--- dense precompute ($VER) locomo ---"
$PY tools/precompute_dense_qwen.py --dataset locomo \
    --data datasets/locomo10.json \
    --model "$MODEL" --out "results/dense_${VER}_locomo.json" || exit 1
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
    --dense-cache "results/dense_cache_${VER}.json" \
    --qa-out-dir "results/locomo_qa_dense_${VER}" \
    --output "results/public_dense_${VER}.json" || exit 1
$PY tools/run_locomo_official_scorer_portable.py \
    --eval-file datasets/locomo_eval/evaluation.py \
    --pred-dir "results/locomo_qa_dense_${VER}" \
    --out "results/locomo_official_qa_dense_${VER}.json" || exit 1
echo "DONE_${VER}"
