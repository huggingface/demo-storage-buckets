#!/bin/bash
set -euo pipefail
#
# Demo 2 (the hero) — S3 conditional writes on HF Storage Buckets via `aws s3api`:
#   1) No-clobber create with --if-none-match '*'  (a second create -> 412)
#   2) Compare-and-swap with --if-match <etag>      (a stale ETag -> 412)
# Preconditions (If-None-Match / If-Match) are honored on PutObject (and the
# copy-source of CopyObject) but NOT on GetObject. A failed precondition returns
# HTTP 412 PreconditionFailed.
#
# Usage:
#   ./demo_02_conditional_ops.sh [--namespace <ns>] [--bucket <name>]
# Env: HF_NAMESPACE, DEMO_BUCKET (default bucket: s3-compat-demo).
# Prereqs: aws CLI >= 2.23, [profile hf] w/ a WRITE token, and the demo bucket to
#          exist (run ./demo_01_s3_basics.sh first, or `aws --profile hf s3 mb`).

PROFILE="hf"
BUCKET="${DEMO_BUCKET:-s3-compat-demo}"
NAMESPACE=""
KEY="manifest.json"

while [ $# -gt 0 ]; do
    case "$1" in
        --namespace) [ $# -ge 2 ] || { echo "ERROR: --namespace needs a value" >&2; exit 1; }; NAMESPACE="$2"; shift 2 ;;
        --bucket)    [ $# -ge 2 ] || { echo "ERROR: --bucket needs a value" >&2; exit 1; }; BUCKET="$2"; shift 2 ;;
        -h|--help)   grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

NAMESPACE="${NAMESPACE:-${HF_NAMESPACE:-}}"
if [ -z "$NAMESPACE" ]; then
    NAMESPACE="your-username"
    echo "WARNING: no --namespace/\$HF_NAMESPACE; using placeholder '$NAMESPACE'." >&2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$SCRIPT_DIR/sample_data/manifest.json"
WORKDIR="/tmp/s3-compat-demo"
mkdir -p "$WORKDIR"

# Print the exact command, then run it.
run() { echo "+ $*"; "$@"; }

# Run a write we EXPECT the gateway to reject with 412 PreconditionFailed, and
# assert on that *specific* failure. This matters: a plain `if <cmd>; then ...
# else "expected 412" fi` would treat ANY non-zero exit (a network blip, a 403,
# a 5xx) as success and falsely claim the conditional write worked. Here we
# capture the output and require it to actually be a 412 / PreconditionFailed.
expect_412() {
    local desc="$1"; shift
    echo "+ $*"
    local out rc
    set +e
    out="$("$@" 2>&1)"
    rc=$?
    set -e
    [ -n "$out" ] && printf '%s\n' "$out"
    if [ "$rc" -eq 0 ]; then
        echo "UNEXPECTED: $desc succeeded — the gateway did not enforce the precondition." >&2
        exit 1
    elif printf '%s' "$out" | grep -qiE '412|precondition ?failed'; then
        echo "✓ expected: $desc rejected (412 PreconditionFailed)."
    else
        echo "ERROR: $desc failed, but NOT with 412 — a real error, not the demo. See above." >&2
        exit 1
    fi
}

echo "============================================"
echo " Demo 2: Conditional writes (the hero)"
echo " profile=$PROFILE  bucket=$BUCKET  key=$KEY"
echo "============================================"
echo ""
echo "Two S3 preconditions the HF gateway honors on PutObject:"
echo "  --if-none-match '*'  -> create only if the key does NOT exist (no clobber)"
echo "  --if-match <etag>    -> overwrite only if the current ETag matches (CAS)"
echo "A failed precondition returns HTTP 412 PreconditionFailed."
echo ""

# Setup (quiet): make this re-runnable and self-sufficient — ensure the bucket
# exists and clear any leftover key so the no-clobber create below reliably
# wins. delete-object is idempotent (a no-op when the key is already absent).
echo ">>> (resetting demo state so this is safe to re-run)"
aws --profile "$PROFILE" s3 mb "s3://$BUCKET" >/dev/null 2>&1 || true
aws --profile "$PROFILE" s3api delete-object --bucket "$BUCKET" --key "$KEY" >/dev/null 2>&1 || true
echo ""

# ---------------------------------------------------------------------------
# Part 1 — No-clobber create with If-None-Match: *
# ---------------------------------------------------------------------------
echo ">>> Part 1: no-clobber create with --if-none-match '*'"
echo ">>> First create should SUCCEED (the key does not exist yet)"
echo "+ aws --profile $PROFILE s3api put-object --bucket $BUCKET --key $KEY --if-none-match '*' --body $MANIFEST"
set +e
create_out="$(aws --profile "$PROFILE" s3api put-object \
    --bucket "$BUCKET" --key "$KEY" --if-none-match '*' --body "$MANIFEST" 2>&1)"
create_rc=$?
set -e
[ -n "$create_out" ] && printf '%s\n' "$create_out"
if [ "$create_rc" -ne 0 ]; then
    if printf '%s' "$create_out" | grep -qiE '412|precondition ?failed'; then
        echo "NOTE: the key already existed (a prior object survived the reset). Run ./cleanup.sh, then retry." >&2
    else
        echo "ERROR: initial create failed (not a 412). Run ./check.sh to diagnose." >&2
    fi
    exit 1
fi
echo ""

# The second identical create must be rejected — with a 412 specifically.
echo ">>> Same create again should FAIL with 412 (the key now exists)"
expect_412 "second no-clobber create" \
    aws --profile "$PROFILE" s3api put-object \
        --bucket "$BUCKET" --key "$KEY" --if-none-match '*' --body "$MANIFEST"
echo ""

# ---------------------------------------------------------------------------
# Part 2 — Compare-and-swap with If-Match: <etag>
# ---------------------------------------------------------------------------
echo ">>> Part 2: compare-and-swap with --if-match <etag>"
echo ">>> Read the current ETag via head-object (S3 ETags include the quotes)"
echo "+ aws --profile $PROFILE s3api head-object --bucket $BUCKET --key $KEY --query ETag --output text"
ETAG="$(aws --profile "$PROFILE" s3api head-object \
    --bucket "$BUCKET" --key "$KEY" \
    --query ETag --output text)"
echo "  current ETag = $ETAG"
echo ""

# After the successful update below, this original ETag no longer matches — it
# becomes the "stale" ETag held by a slower, conflicting writer.
STALE_ETAG="$ETAG"

echo ">>> Prepare an updated manifest (writer B bumps version -> 2)"
CAS_BODY="$WORKDIR/manifest.cas.json"
cat > "$CAS_BODY" <<'JSON'
{"version": 2, "updated_by": "writer-b", "entries": [{"name": "model-a", "sha": "1a2b3c4d"}, {"name": "model-b", "sha": "5e6f7a8b"}]}
JSON
run cat "$CAS_BODY"
echo ""

echo ">>> Overwrite only if the ETag still matches -> SUCCEEDS (we hold the fresh ETag)"
run aws --profile "$PROFILE" s3api put-object \
    --bucket "$BUCKET" --key "$KEY" \
    --if-match "$ETAG" \
    --body "$CAS_BODY"
echo "✓ update applied; the object's ETag has now changed."
echo ""

# A conflicting writer still holding the pre-update ETag must lose the race.
echo ">>> A second writer still holding the OLD ETag ($STALE_ETAG) tries to write..."
STALE_BODY="$WORKDIR/manifest.stale.json"
cat > "$STALE_BODY" <<'JSON'
{"version": 99, "updated_by": "writer-a-stale", "entries": [{"name": "model-a", "sha": "deadbeef"}]}
JSON
expect_412 "stale-ETag write" \
    aws --profile "$PROFILE" s3api put-object \
        --bucket "$BUCKET" --key "$KEY" --if-match "$STALE_ETAG" --body "$STALE_BODY"
echo "  Optimistic concurrency: the losing writer must re-read the ETag and retry."
echo ""

echo "Reality check: --if-none-match / --if-match are honored on put-object (and the"
echo "copy-source of copy-object) but NOT on get-object. Clean up with ./cleanup.sh."
