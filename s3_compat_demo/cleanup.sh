#!/bin/bash
set -euo pipefail
#
# Remove the S3-compat demo objects, the demo bucket, and local temp files.
# Safe to re-run: "not found" style errors are ignored.
#
# Usage:
#   ./cleanup.sh [--namespace <ns>] [--bucket <name>]
# Env: HF_NAMESPACE, DEMO_BUCKET (default bucket: s3-compat-demo).
# Prereqs: aws CLI, [profile hf] configured (./setup_profile.sh).

PROFILE="hf"
BUCKET="${DEMO_BUCKET:-s3-compat-demo}"
NAMESPACE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --namespace) NAMESPACE="${2:-}"; shift 2 ;;
        --bucket)    BUCKET="${2:-}"; shift 2 ;;
        -h|--help)   grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

NAMESPACE="${NAMESPACE:-${HF_NAMESPACE:-}}"
if [ -z "$NAMESPACE" ]; then
    NAMESPACE="your-username"
    echo "WARNING: no --namespace/\$HF_NAMESPACE; using placeholder '$NAMESPACE'." >&2
fi

# Print the exact command, then run it. `|| true` keeps re-runs safe once the
# bucket/objects are already gone.
run() { echo "+ $*"; "$@"; }

WORKDIR="/tmp/s3-compat-demo"

echo "Cleaning up bucket 's3://$BUCKET' (namespace '$NAMESPACE')..."
run aws --profile "$PROFILE" s3 rm "s3://$BUCKET" --recursive || true
run aws --profile "$PROFILE" s3 rb "s3://$BUCKET" || true
echo ""

echo "Cleaning up local temp files under $WORKDIR ..."
run rm -rf "$WORKDIR" || true
echo ""

echo "Done. (Re-running is safe — missing bucket/files are ignored.)"
