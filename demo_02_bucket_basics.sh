#!/bin/bash
set -euo pipefail
#
# Demo 1: Bucket Basics — Create, Upload, Browse, Download
#
# Talking points:
#   - S3-like UX: create, cp, sync, rm — familiar to any infra team
#   - No Git overhead: mutable, non-versioned, overwrite-in-place
#   - Works from CLI, Python, or the Hub web UI
#

BUCKET="xet-team/nvidia-demo-basics"

echo "============================================"
echo " Demo 1: Storage Bucket Basics"
echo "============================================"
echo ""

# --- Create ---
echo ">>> Creating bucket: $BUCKET"
hf buckets create "$BUCKET" --private 2>/dev/null || echo "    (bucket already exists)"
echo ""

# --- Upload a single file ---
echo ">>> Uploading a single config file"
echo '{"model": "cosmos-v2", "epochs": 100, "batch_size": 256}' > /tmp/demo-config.json
hf buckets cp /tmp/demo-config.json "hf://buckets/$BUCKET/config.json"
echo ""

# --- Upload a directory of "episode" files ---
echo ">>> Generating sample episode data (5 episodes, ~10 MB each)"
mkdir -p /tmp/demo-episodes
for i in $(seq 1 5); do
    dd if=/dev/urandom of="/tmp/demo-episodes/episode_$(printf '%04d' $i).bin" bs=1M count=10 2>/dev/null
    echo "    Generated episode_$(printf '%04d' $i).bin (10 MB)"
done
echo ""

echo ">>> Syncing episodes directory to bucket"
time hf buckets sync /tmp/demo-episodes "hf://buckets/$BUCKET/episodes/"
echo ""

# --- Browse ---
echo ">>> Listing bucket contents"
hf buckets list "$BUCKET" -h -R
echo ""

# --- Download ---
echo ">>> Downloading config back"
hf buckets cp "hf://buckets/$BUCKET/config.json" /tmp/demo-config-downloaded.json
cat /tmp/demo-config-downloaded.json
echo ""

echo ">>> Bucket is live at: https://huggingface.co/buckets/$BUCKET"
echo ""
echo "Done! This bucket works like S3 — no Git, no versions, just fast mutable storage."
