#!/bin/bash
set -euo pipefail
#
# Run before the meeting to configure all demo scripts.
#
# Usage:
#   ./prep.sh rajatarya
#

if [ -z "${1:-}" ]; then
    echo "Usage: ./prep.sh <hf-username>" >&2
    exit 1
fi

HF_USER="$1"
echo "Configuring demos for user: $HF_USER"

sed -i '' "s|^BUCKET=.*|BUCKET=\"${HF_USER}/nvidia-demo-basics\"|" demo_02_bucket_basics.sh
sed -i '' "s|^BUCKET=.*|BUCKET=\"${HF_USER}/nvidia-demo-mount\"|" demo_03_hf_mount.sh
sed -i '' "s|^BUCKET=.*|BUCKET=\"${HF_USER}/nvidia-demo-dataset\"|" demo_04_dataset_sync.sh
sed -i '' "s|^BUCKET = .*|BUCKET = \"${HF_USER}/nvidia-demo-dedup\"|" demo_01_xet_dedup.py
sed -i '' "s|[a-zA-Z0-9_-]*/nvidia-demo-|${HF_USER}/nvidia-demo-|g" cleanup.sh
sed -i '' "s|[a-zA-Z0-9_-]*/nvidia-demo-|${HF_USER}/nvidia-demo-|g" demo_05_cdn_prewarm.sh

echo "Done."
grep -n 'nvidia-demo' demo_*.{sh,py} cleanup.sh
