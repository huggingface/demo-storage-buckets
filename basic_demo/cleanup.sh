#!/bin/bash
set -euo pipefail
#
# Clean up all demo buckets and local temp files.
#
# Usage:
#   ./cleanup.sh          # delete buckets and temp files
#   ./cleanup.sh --reset  # also reset scripts to require ./prep.sh again
#

echo "Cleaning up demo buckets..."

for bucket in \
    your-username/nvidia-demo-basics \
    your-username/nvidia-demo-dedup \
    your-username/nvidia-demo-dataset \
    your-username/nvidia-demo-mount; do
    echo "  Deleting $bucket..."
    hf buckets rm "$bucket" --recursive 2>/dev/null || true
done

echo "Cleaning up local temp files..."
rm -rf /tmp/demo-config.json /tmp/demo-config-downloaded.json
rm -rf /tmp/demo-episodes /tmp/demo-lerobot-episodes
rm -rf /tmp/demo-hf-mount

if [ "${1:-}" = "--reset" ]; then
    echo "Resetting scripts to require ./prep.sh..."
    sed -i '' 's|^BUCKET=.*|BUCKET="your-username/nvidia-demo-basics"|' demo_02_bucket_basics.sh
    sed -i '' 's|^BUCKET=.*|BUCKET="your-username/nvidia-demo-mount"|' demo_03_hf_mount.sh
    sed -i '' 's|^BUCKET=.*|BUCKET="your-username/nvidia-demo-dataset"|' demo_04_dataset_sync.sh
    sed -i '' 's|^BUCKET = .*|BUCKET = "your-username/nvidia-demo-dedup"|' demo_01_xet_dedup.py
    sed -i '' "s|[a-zA-Z0-9_-]*your-username/nvidia-demo-|your-username/nvidia-demo-|g" cleanup.sh
    echo "  Done. Run ./prep.sh <username> before next demo."
fi

echo "Done."
