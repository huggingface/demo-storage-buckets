#!/bin/bash
set -euo pipefail
#
# Demo 1 — "Your S3 tools just work": mb / cp / ls / rm against an HF Storage
# Bucket through the stock AWS CLI. The only HF-specific thing is --profile hf,
# whose endpoint_url points at the HF S3 gateway.
#
# Runs step by step, pausing for Enter between steps so you can narrate.
#
# Usage:
#   ./demo_01_s3_basics.sh [--namespace <ns>] [--bucket <name>] [--no-pause]
# Env: HF_NAMESPACE, DEMO_BUCKET (default bucket: s3-compat-demo);
#      NO_PAUSE=1 disables the between-step pauses (e.g. automated runs).
# Prereqs: aws CLI >= 2.23, [profile hf] configured (./setup_profile.sh) + S3 creds.

PROFILE="hf"
BUCKET="${DEMO_BUCKET:-s3-compat-demo}"
NAMESPACE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --namespace) [ $# -ge 2 ] || { echo "ERROR: --namespace needs a value" >&2; exit 1; }; NAMESPACE="$2"; shift 2 ;;
        --bucket)    [ $# -ge 2 ] || { echo "ERROR: --bucket needs a value" >&2; exit 1; }; BUCKET="$2"; shift 2 ;;
        --no-pause)  NO_PAUSE=1; shift ;;
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

# Pause between steps so the presenter can talk. Skipped when stdin isn't a TTY
# or NO_PAUSE=1 (so automated runs and shellcheck don't hang).
pause() {
    [ "${NO_PAUSE:-}" = "1" ] && return 0
    [ -t 0 ] || return 0
    printf '\n  [Enter] to continue... '
    read -r _ || true
    echo ""
}

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

pause
echo ">>> Create the bucket (CreateBucket; fine if it already exists)"
echo "+ aws --profile $PROFILE s3 mb s3://$BUCKET"
set +e
mb_out="$(aws --profile "$PROFILE" s3 mb "s3://$BUCKET" 2>&1)"
mb_rc=$?
set -e
[ -n "$mb_out" ] && printf '%s\n' "$mb_out"
if [ "$mb_rc" -ne 0 ]; then
    if printf '%s' "$mb_out" | grep -qiE 'BucketAlreadyOwnedByYou|BucketAlreadyExists|already (exists|owned)'; then
        echo "(bucket already exists — continuing)"
    else
        echo "ERROR: could not create the bucket, and this is NOT an 'already exists' error." >&2
        echo "       Run ./check.sh to diagnose (often a Read-only token or wrong credentials)." >&2
        exit 1
    fi
fi
echo ""

pause
echo ">>> Create a small local file to upload"
echo "hello from the HF S3 gateway" > "$LOCAL_FILE"
run cat "$LOCAL_FILE"
echo ""

pause
echo ">>> Upload it (PutObject)"
run aws --profile "$PROFILE" s3 cp "$LOCAL_FILE" "s3://$BUCKET/hello.txt"
echo ""

pause
echo ">>> List the bucket (served by ListObjectsV2 under the hood)"
run aws --profile "$PROFILE" s3 ls "s3://$BUCKET"
echo ""

# GetObject: the gateway PROXIES bytes for aws-cli/botocore (those SDKs don't
# follow S3-endpoint redirects); other clients get a 302 to the nearest CDN edge.
pause
echo ">>> Download it back (GetObject; proxied through the gateway for the AWS CLI)"
run aws --profile "$PROFILE" s3 cp "s3://$BUCKET/hello.txt" "$DOWNLOAD"
run cat "$DOWNLOAD"
echo ""

pause
echo ">>> Remove the object (DeleteObject)"
run aws --profile "$PROFILE" s3 rm "s3://$BUCKET/hello.txt"
echo ""

echo "Done. Bucket 's3://$BUCKET' is live under namespace '$NAMESPACE'."
echo "Next: ./demo_02_conditional_ops.sh  (conditional writes — the hero)."
