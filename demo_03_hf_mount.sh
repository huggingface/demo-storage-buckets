#!/bin/bash
set -euo pipefail
#
# Demo 5: FUSE Mount + Jobs — Read/Write Buckets Like a Local Filesystem
#
# Talking points:
#   - `hf mount` gives you a POSIX filesystem view of any bucket
#   - Training code reads/writes files normally — no SDK changes needed
#   - Combined with HF Jobs: mount a bucket into a GPU job, write
#     checkpoints directly, read datasets without downloading first
#   - This is the "it just works" story for researchers who don't want
#     to learn a new storage API
#

BUCKET="rajatarya/nvidia-demo-mount"
MOUNT_DIR="/tmp/demo-hf-mount"

echo "============================================"
echo " Demo 5: FUSE Mount + HF Jobs"
echo "============================================"
echo ""

# --- Part A: Local mount demo ---
echo ">>> Part A: Mount a bucket as a local filesystem"
echo ""

hf buckets create "$BUCKET" --private 2>/dev/null || echo "(bucket already exists)"

# Seed some data
echo '{"episode": 1, "reward": 0.85}' | hf buckets cp - "hf://buckets/$BUCKET/results/ep_0001.json"
echo '{"episode": 2, "reward": 0.91}' | hf buckets cp - "hf://buckets/$BUCKET/results/ep_0002.json"
echo ""

# Mount
mkdir -p "$MOUNT_DIR"
echo ">>> Mounting bucket to $MOUNT_DIR"
hf mount "hf://buckets/$BUCKET" "$MOUNT_DIR" &
MOUNT_PID=$!
sleep 2  # wait for mount

echo ">>> Reading files through the mount (standard POSIX):"
echo "    $ ls $MOUNT_DIR/results/"
ls "$MOUNT_DIR/results/"
echo ""
echo "    $ cat $MOUNT_DIR/results/ep_0001.json"
cat "$MOUNT_DIR/results/ep_0001.json"
echo ""

echo ">>> Writing a new file through the mount:"
echo '{"episode": 3, "reward": 0.97}' > "$MOUNT_DIR/results/ep_0003.json"
echo "    Wrote ep_0003.json via filesystem — synced to bucket automatically"
echo ""

echo ">>> Verifying it's in the bucket:"
hf buckets list "$BUCKET/results" -h
echo ""

# Cleanup mount
fusermount -u "$MOUNT_DIR" 2>/dev/null || umount "$MOUNT_DIR" 2>/dev/null || true
kill $MOUNT_PID 2>/dev/null || true

# --- Part B: Jobs integration (talk track) ---
echo ""
echo ">>> Part B: HF Jobs with mounted storage"
echo ""
echo "In an HF Job, you can mount buckets read/write directly:"
echo ""
echo '  hf jobs run \\'
echo '    --mount "hf://buckets/my-org/training-data:/data:ro" \\'
echo '    --mount "hf://buckets/my-org/checkpoints:/checkpoints:rw" \\'
echo '    --gpu a100 \\'
echo '    python train.py --data-dir /data --checkpoint-dir /checkpoints'
echo ""
echo "Your training script just reads /data and writes /checkpoints."
echo "No S3 SDK, no download step, no upload step."
echo ""
echo "For physical AI training:"
echo "  - Mount 100 TB episode dataset read-only at /data"
echo "  - Mount checkpoint bucket read-write at /checkpoints"
echo "  - Training code uses standard open()/torch.save()"
echo "  - Checkpoints appear in the bucket immediately"
echo "  - Other jobs (eval, visualization) can mount the same bucket"
