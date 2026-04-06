#!/bin/bash
set -euo pipefail
#
# Clean up all demo buckets and local temp files
#

echo "Cleaning up demo buckets..."

for bucket in \
    rajatarya/nvidia-demo-basics \
    rajatarya/nvidia-demo-dedup \
    rajatarya/nvidia-demo-dataset \
    rajatarya/nvidia-demo-mount; do
    echo "  Deleting $bucket..."
    hf buckets rm "$bucket" --recursive 2>/dev/null || true
    # Note: bucket deletion may need to be done via Hub UI or API
done

echo "Cleaning up local temp files..."
rm -rf /tmp/demo-config.json /tmp/demo-config-downloaded.json
rm -rf /tmp/demo-episodes /tmp/demo-lerobot-episodes
rm -rf /tmp/demo-hf-mount

echo "Done."
