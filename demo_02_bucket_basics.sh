#!/bin/bash
set -euo pipefail
#
# Demo 2: Bucket Basics — Create, Upload, Browse, Download
#
# Talking points:
#   - S3-like UX: create, cp, sync, rm — familiar to any infra team
#   - No Git overhead: mutable, non-versioned, overwrite-in-place
#   - Works from CLI, Python, or the Hub web UI
#

BUCKET="rajatarya/nvidia-demo-basics"

echo "============================================"
echo " Demo 2: Storage Bucket Basics"
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
echo "This bucket works like S3 — no Git, no versions, just fast mutable storage."

echo ""
echo "--- Press Enter to continue to CDN Pre-warming ---"
read -r

# --- CDN Pre-warming (talk track + Hub UI) ---
echo ""
echo "============================================"
echo " CDN Pre-warming"
echo "============================================"
echo ""
echo "This is best shown via the Hub UI."
echo ""
echo "Steps to show:"
echo "  1. Open bucket settings: https://huggingface.co/buckets/$BUCKET/settings"
echo "  2. Under 'CDN Pre-warming', select regions:"
echo "     - AWS us-east-1 (DGX Cloud cluster)"
echo "     - AWS us-west-2 (evaluation cluster)"
echo "  3. Save — HF pre-warms CDN in selected locations with files from bucket"
echo ""
echo "Result:"
echo "  - Training jobs read from CDN, not cross-region"
echo "  - Pre-warming means cache is already warm on 1st read — no cold start penalty"
echo "  - No changes to training code — same hf:// paths"
echo ""
echo "This matters for physical AI because:"
echo "  - Episode datasets are read many times (multiple training runs)"
echo "  - Video/sensor data is large — cross-region reads are slow and expensive"
echo "  - Multi-site teams (e.g., NVIDIA Santa Clara + research labs) share data"
echo ""
