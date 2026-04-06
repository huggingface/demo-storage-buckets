#!/bin/bash
set -euo pipefail
#
# Demo 3: Large Dataset Sync — LeRobot-Scale Episode Data
#
# Talking points:
#   - Physical AI generates massive episode datasets (video, sensor, action)
#   - `hf buckets sync` works like `aws s3 sync` — only transfers diffs
#   - Add new episodes from a training run? Only the new files upload
#   - Overwrite a corrupted episode? Only that file re-uploads
#   - This is the workflow for continuous data collection pipelines
#

HF_USER=$(hf auth whoami 2>&1 | sed -n 's/^user=\([^ ]*\).*/\1/p')
BUCKET="${HF_USER}/nvidia-demo-dataset"
DATA_DIR="/tmp/demo-lerobot-episodes"

echo "============================================"
echo " Demo 3: Dataset Sync (LeRobot-Scale)"
echo "============================================"
echo ""

# Create bucket
hf buckets create "$BUCKET" --private 2>/dev/null || echo "(bucket already exists)"
echo ""

# --- Phase 1: Initial dataset upload ---
echo ">>> Phase 1: Initial dataset — 20 episodes from a robot training session"
rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR"

for i in $(seq 1 20); do
    ep=$(printf 'episode_%04d' $i)
    # Simulate parquet-like episode files (~5 MB each)
    dd if=/dev/urandom of="$DATA_DIR/$ep.parquet" bs=1M count=5 2>/dev/null
done
echo "    Generated 20 episodes ($(du -sh $DATA_DIR | cut -f1) total)"
echo ""

echo ">>> Syncing initial dataset to bucket..."
time hf buckets sync "$DATA_DIR" "hf://buckets/$BUCKET/episodes/"
echo ""

# --- Phase 2: Add new episodes (incremental) ---
echo ">>> Phase 2: Robot collected 5 more episodes overnight"
for i in $(seq 21 25); do
    ep=$(printf 'episode_%04d' $i)
    dd if=/dev/urandom of="$DATA_DIR/$ep.parquet" bs=1M count=5 2>/dev/null
done
echo "    Added episodes 21-25 (25 MB new data)"
echo ""

echo ">>> Re-syncing — only new episodes should transfer"
time hf buckets sync "$DATA_DIR" "hf://buckets/$BUCKET/episodes/"
echo ""

# --- Phase 3: Fix a corrupted episode ---
echo ">>> Phase 3: Episode 0003 had a sensor glitch — replacing it"
dd if=/dev/urandom of="$DATA_DIR/episode_0003.parquet" bs=1M count=5 2>/dev/null
echo ""

echo ">>> Re-syncing — only the replaced episode transfers"
time hf buckets sync "$DATA_DIR" "hf://buckets/$BUCKET/episodes/"
echo ""

echo ">>> Final bucket contents:"
hf buckets list "$BUCKET/episodes" -h | tail -5
echo "    ... (25 episodes total)"
echo ""

echo "Key takeaway: sync is incremental. For a 100 TB robotics dataset,"
echo "adding 1 TB of new episodes only transfers 1 TB — not 101 TB."
