#!/bin/bash
set -euo pipefail
#
# Idempotent cleanup: delete demo bucket + local temp files.
#

BUCKET="${1:-$(hf auth whoami | grep -oE 'user=[^ ]+' | cut -d= -f2)/nvidia-simready}"

echo ">>> Deleting bucket $BUCKET (if exists)"
hf buckets delete "$BUCKET" --yes 2>/dev/null || echo "    (bucket did not exist)"

echo ">>> Removing local temp files"
rm -f /tmp/original.csv /tmp/annotated.csv

echo "Done."
