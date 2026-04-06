#!/bin/bash
set -euo pipefail
#
# Demo 4: CDN Pre-warming — Data Close to Compute
#
# Talking points:
#   - Training clusters need data locally, not pulled across regions
#   - Pre-warming caches bucket data at edge locations near your compute
#   - Works for multi-region setups (e.g., DGX clusters in us-east,
#     evaluation jobs in us-west)
#   - No data movement by the user — HF handles replication
#
# NOTE: This demo is talk-track only with screenshots / Hub UI walkthrough.
# Pre-warming is configured via the bucket settings page on the Hub.
#

echo "============================================"
echo " Demo 4: CDN Pre-warming"
echo "============================================"
echo ""
echo "This is best shown via the Hub UI."
echo ""
echo "Steps to show:"
echo "  1. Open bucket settings: https://huggingface.co/buckets/rajatarya/nvidia-demo-dataset/settings"
echo "  2. Under 'CDN Pre-warming', select regions:"
echo "     - AWS us-east-1 (DGX Cloud cluster)"
echo "     - AWS us-west-2 (evaluation cluster)"
echo "  3. Save — HF replicates data to edge locations"
echo ""
echo "Result:"
echo "  - Training jobs read from local cache, not cross-region"
echo "  - First read is cached; subsequent reads are fast"
echo "  - No changes to training code — same hf:// paths"
echo ""
echo "This matters for physical AI because:"
echo "  - Episode datasets are read many times (multiple training runs)"
echo "  - Video/sensor data is large — cross-region reads are slow and expensive"
echo "  - Multi-site teams (e.g., NVIDIA Santa Clara + research labs) share data"
