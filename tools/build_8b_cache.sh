#!/bin/bash
# Cloud-side: place ModelScope-downloaded Qwen3-Embedding-8B files into the
# HF cache layout (blobs/<sha256> + snapshots/<commit> symlinks + refs/main)
# so precompute_dense_qwen.py loads the model offline (HF_HUB_OFFLINE=1).
set -e
SRC=/root/autodl-tmp/qwen8b_dl
DST=/root/.cache/huggingface/hub/models--Qwen--Qwen3-Embedding-8B
COMMIT=1d8ad4ca9b3dd8059ad90a75d4983776a23d44af
mkdir -p "$DST/blobs" "$DST/snapshots/$COMMIT" "$DST/refs"
# NOTE: refs/main must NOT end in a newline -- scan_cache_dir matches the
# ref hash against snapshots/<commit> directory names exactly; `echo` broke
# 8B offline resolution (CorruptedCacheException, repo silently skipped).
printf '%s' "$COMMIT" > "$DST/refs/main"
cd "$SRC"
for f in model-00001-of-00004.safetensors \
         model-00002-of-00004.safetensors \
         model-00003-of-00004.safetensors \
         model-00004-of-00004.safetensors \
         model.safetensors.index.json \
         config.json tokenizer.json tokenizer_config.json vocab.json \
         merges.txt generation_config.json modules.json; do
  h=$(sha256sum "$f" | awk '{print $1}')
  mv "$f" "$DST/blobs/$h"
  ln -sf "../../blobs/$h" "$DST/snapshots/$COMMIT/$f"
  echo "$f -> ${h:0:12}"
done
echo BUILT
ls -la "$DST/snapshots/$COMMIT/"
