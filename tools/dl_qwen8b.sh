#!/bin/bash
# Cloud-side: download Qwen3-Embedding-8B files from ModelScope (CN CDN,
# non-xet) into /root/autodl-tmp/qwen8b_dl/.  Files are later placed into
# the HF cache layout (blobs/<sha256> + snapshots symlinks) so
# precompute_dense_qwen.py loads them offline (HF_HUB_OFFLINE=1).
set -u
cd /root/autodl-tmp/qwen8b_dl || exit 1
for f in model-00001-of-00004.safetensors \
         model-00002-of-00004.safetensors \
         model-00003-of-00004.safetensors \
         model-00004-of-00004.safetensors \
         model.safetensors.index.json \
         config.json tokenizer.json tokenizer_config.json vocab.json \
         merges.txt generation_config.json modules.json \
         config_sentence_transformers.json 1_Pooling/config.json; do
  curl -sL --retry 5 --retry-delay 3 -C - -o "$f" \
    "https://modelscope.cn/models/Qwen/Qwen3-Embedding-8B/resolve/master/$f" \
    || echo "FAIL $f"
done
echo ALL_DONE
ls -la
