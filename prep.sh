#!/bin/bash
set -euo pipefail
#
# Run before the meeting to configure all demo scripts
# with the currently logged-in HF user.
#

HF_USER=$(hf auth whoami 2>&1 | sed -n 's/^user=\([^ ]*\).*/\1/p')

if [ -z "$HF_USER" ]; then
    echo "ERROR: Could not determine HF user. Run 'hf login' first." >&2
    exit 1
fi

echo "Configuring demos for user: $HF_USER"

# Patch all demo scripts and cleanup
sed -i '' "s|^BUCKET=.*|BUCKET=\"${HF_USER}/nvidia-demo-basics\"|" demo_02_bucket_basics.sh
sed -i '' "s|^BUCKET=.*|BUCKET=\"${HF_USER}/nvidia-demo-mount\"|" demo_03_hf_mount.sh
sed -i '' "s|^BUCKET=.*|BUCKET=\"${HF_USER}/nvidia-demo-dataset\"|" demo_04_dataset_sync.sh
sed -i '' "s|^BUCKET = .*|BUCKET = \"${HF_USER}/nvidia-demo-dedup\"|" demo_01_xet_dedup.py
sed -i '' "s|YOUR_USER|${HF_USER}|g" cleanup.sh
sed -i '' "s|YOUR_USER|${HF_USER}|g" demo_05_cdn_prewarm.sh

echo "Done. Verify with: grep -n BUCKET demo_*.{sh,py} cleanup.sh"
