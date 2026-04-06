#!/bin/bash
set -euo pipefail
#
# Clean up all demo buckets and local temp files
#

HF_USER=$(hf auth whoami 2>&1 | sed -n 's/^user=\([^ ]*\).*/\1/p')
echo "Cleaning up demo buckets for user: $HF_USER"

for bucket in \
    "${HF_USER}/nvidia-demo-basics" \
    "${HF_USER}/nvidia-demo-dedup" \
    "${HF_USER}/nvidia-demo-dataset" \
    "${HF_USER}/nvidia-demo-mount"; do
    echo "  Deleting $bucket..."
    hf buckets rm "$bucket" --recursive 2>/dev/null || true
    # Note: bucket deletion may need to be done via Hub UI or API
done

echo "Cleaning up local temp files..."
rm -rf /tmp/demo-config.json /tmp/demo-config-downloaded.json
rm -rf /tmp/demo-episodes /tmp/demo-lerobot-episodes
rm -rf /tmp/demo-hf-mount

echo "Done."
