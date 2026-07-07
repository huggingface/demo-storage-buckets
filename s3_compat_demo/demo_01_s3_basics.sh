#!/bin/bash
set -euo pipefail
#
# Demo 1 — "Your S3 tools just work": mb / cp / ls / rm against an HF Storage
# Bucket through the stock AWS CLI. The only HF-specific thing is --profile hf,
# whose endpoint_url points at the HF S3 gateway.
#
# Usage:
#   ./demo_01_s3_basics.sh [--namespace <ns>] [--bucket <name>]
# Env: HF_NAMESPACE, DEMO_BUCKET (default bucket: s3-compat-demo).
# Prereqs: aws CLI >= 2.23, [profile hf] configured (./setup_profile.sh) + S3 creds.

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
    echo "         (Namespace is informational here; the real one is baked into" >&2
    echo "          [profile hf]'s endpoint_url by ./setup_profile.sh.)" >&2
fi

# Print the exact command, then run it — so the audience sees stock AWS CLI.
run() { echo "+ $*"; "$@"; }

WORKDIR="/tmp/s3-compat-demo"
mkdir -p "$WORKDIR"
LOCAL_FILE="$WORKDIR/hello.txt"
DOWNLOAD="$WORKDIR/hello.downloaded.txt"

echo "============================================"
echo " Demo 1: Your S3 tools just work"
echo " profile=$PROFILE  bucket=$BUCKET  namespace=$NAMESPACE"
echo "============================================"
echo ""
echo "Stock AWS CLI. Nothing below is HF-specific except --profile $PROFILE, whose"
echo "endpoint_url points at the HF S3 gateway. Same mb/cp/ls/rm you already know."
echo ""

echo ">>> Create the bucket (CreateBucket; fine if it already exists)"
if ! run aws --profile "$PROFILE" s3 mb "s3://$BUCKET"; then
    echo "(bucket already exists — continuing)"
fi
echo ""

echo ">>> Create a small local file to upload"
echo "hello from the HF S3 gateway" > "$LOCAL_FILE"
run cat "$LOCAL_FILE"
echo ""

echo ">>> Upload it (PutObject)"
run aws --profile "$PROFILE" s3 cp "$LOCAL_FILE" "s3://$BUCKET/hello.txt"
echo ""

echo ">>> List the bucket (served by ListObjectsV2 under the hood)"
run aws --profile "$PROFILE" s3 ls "s3://$BUCKET"
echo ""

# GetObject usually 302-redirects to the CDN; botocore/aws-cli follow the redirect.
echo ">>> Download it back (GetObject; may 302-redirect to the CDN, the CLI follows it)"
run aws --profile "$PROFILE" s3 cp "s3://$BUCKET/hello.txt" "$DOWNLOAD"
run cat "$DOWNLOAD"
echo ""

echo ">>> Remove the object (DeleteObject)"
run aws --profile "$PROFILE" s3 rm "s3://$BUCKET/hello.txt"
echo ""

echo "Done. Bucket 's3://$BUCKET' is live under namespace '$NAMESPACE'."
echo "Next: ./demo_02_conditional_ops.sh  (conditional writes — the hero)."
