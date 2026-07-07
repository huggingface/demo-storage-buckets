#!/bin/bash
set -euo pipefail
#
# Write the [profile hf] AWS CLI profile for HF Storage Buckets (S3 gateway),
# substituting your namespace into endpoint_url. Idempotent: replaces an
# existing [profile hf] block and leaves other profiles untouched.
# Does NOT write credentials — prints how to add them to ~/.aws/credentials.
#
# Usage:
#   ./setup_profile.sh --namespace <hf-username-or-org>
#   HF_NAMESPACE=<ns> ./setup_profile.sh
# Env: AWS_CONFIG_FILE (default ~/.aws/config).
# Prereqs: awk; an HF token with Write permission (to generate S3 credentials).

NAMESPACE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --namespace) [ $# -ge 2 ] || { echo "ERROR: --namespace needs a value" >&2; exit 1; }; NAMESPACE="$2"; shift 2 ;;
        -h|--help)   grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# Namespace: --namespace, else $HF_NAMESPACE, else a loud placeholder.
NAMESPACE="${NAMESPACE:-${HF_NAMESPACE:-}}"
if [ -z "$NAMESPACE" ]; then
    NAMESPACE="your-username"
    echo "WARNING: no --namespace or \$HF_NAMESPACE given; using placeholder '$NAMESPACE'." >&2
    echo "         Re-run with --namespace <your-hf-username-or-org> before the demo." >&2
fi

CONFIG_FILE="${AWS_CONFIG_FILE:-$HOME/.aws/config}"
CREDENTIALS_FILE="${AWS_SHARED_CREDENTIALS_FILE:-$HOME/.aws/credentials}"
mkdir -p "$(dirname "$CONFIG_FILE")"

# Back up any existing config before editing. Use a timestamped name so a
# re-run never clobbers an earlier (pristine) backup.
if [ -f "$CONFIG_FILE" ]; then
    BACKUP="${CONFIG_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
    cp "$CONFIG_FILE" "$BACKUP"
    echo "Backed up $CONFIG_FILE -> $BACKUP"
fi

NEW="$(mktemp)"
trap 'rm -f "$NEW"' EXIT

# 1. Existing content minus any [profile hf] block, with trailing blanks trimmed.
if [ -f "$CONFIG_FILE" ]; then
    awk '
        /^\[/ { keep = ($0 !~ /^\[profile hf\][[:space:]]*$/) }
        keep
    ' keep=1 "$CONFIG_FILE" \
    | awk 'NF { last = NR } { line[NR] = $0 } END { for (i = 1; i <= last; i++) print line[i] }' \
    > "$NEW"
fi

# 2. Separate previous content from the new block with one blank line.
if [ -s "$NEW" ]; then
    echo "" >> "$NEW"
fi

# 3. Append the non-secret [profile hf] block (namespace baked into endpoint_url).
cat >> "$NEW" <<EOF
[profile hf]
region = us-east-1
endpoint_url = https://s3.hf.co/${NAMESPACE}
s3 =
    addressing_style = path
    multipart_threshold = 2GB
    multipart_chunksize = 2GB
request_checksum_calculation = when_required
response_checksum_validation = when_required
EOF

mv "$NEW" "$CONFIG_FILE"
trap - EXIT

echo "Wrote [profile hf] to $CONFIG_FILE (endpoint_url = https://s3.hf.co/$NAMESPACE)."
echo ""
echo "NEXT — add S3 credentials (this script never writes secrets):"
echo "  1. HF Settings -> Access Tokens: https://huggingface.co/settings/tokens"
echo "     Create a token. Its Read/Write permission becomes the S3 credential's"
echo "     permission; conditional writes (demo 2) need Write."
echo "  2. Open the token's dropdown -> 'Generate S3 credentials'."
echo "  3. Copy the access key ID (prefixed HFAK...) and secret access key"
echo "     (the secret is shown only once)."
echo ""
echo "Then add this block to $CREDENTIALS_FILE:"
echo ""
echo "  [hf]"
echo "  aws_access_key_id = HFAK..."
echo "  aws_secret_access_key = ..."
echo ""
echo "Verify everything with: ./check.sh"
