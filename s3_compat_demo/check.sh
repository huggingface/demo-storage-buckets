#!/bin/bash
set -euo pipefail
#
# Doctor for the HF S3-compat demo: verifies the AWS CLI, the [profile hf]
# profile, resolvable credentials, and gateway connectivity — and maps common
# failures to the config field that fixes them.
#
# Usage:
#   ./check.sh
# Env: AWS_CONFIG_FILE (default ~/.aws/config),
#      AWS_SHARED_CREDENTIALS_FILE (default ~/.aws/credentials).
# Prereqs: aws CLI >= 2.23, [profile hf] configured (./setup_profile.sh) + S3 creds.

PROFILE="hf"
MIN_VERSION="2.23.0"
CONFIG_FILE="${AWS_CONFIG_FILE:-$HOME/.aws/config}"
CREDENTIALS_FILE="${AWS_SHARED_CREDENTIALS_FILE:-$HOME/.aws/credentials}"

fails=0
pass() { echo "  [OK]   $*"; }
fail() { echo "  [FAIL] $*"; fails=$((fails + 1)); }
note() { echo "         -> $*"; }

echo "S3-compat demo doctor"
echo "  config file      : $CONFIG_FILE"
echo "  credentials file : $CREDENTIALS_FILE"
echo ""

# 1. AWS CLI present + version >= MIN_VERSION.
if ! command -v aws >/dev/null 2>&1; then
    fail "aws CLI not found on PATH."
    note "Install AWS CLI v2 (>= $MIN_VERSION): https://docs.aws.amazon.com/cli/"
    echo ""
    echo "$fails check(s) failed."
    exit 1
fi

ver_full="$(aws --version 2>&1 | sed -n 's|^aws-cli/\([0-9.][0-9.]*\).*|\1|p')"
if [ -z "$ver_full" ]; then
    fail "could not parse 'aws --version' output."
else
    lowest="$(printf '%s\n%s\n' "$ver_full" "$MIN_VERSION" | sort -V | head -n1)"
    if [ "$lowest" = "$MIN_VERSION" ] || [ "$ver_full" = "$MIN_VERSION" ]; then
        pass "aws CLI $ver_full (>= $MIN_VERSION)"
    else
        fail "aws CLI $ver_full is older than $MIN_VERSION."
        note "Conditional writes + 'when_required' checksums need AWS CLI >= $MIN_VERSION."
    fi
fi

# 2. [profile hf] present in the config file.
if grep -qE '^\[profile hf\][[:space:]]*$' "$CONFIG_FILE" 2>/dev/null; then
    pass "[profile hf] found in $CONFIG_FILE"
else
    fail "[profile hf] not found in $CONFIG_FILE."
    note "Run ./setup_profile.sh --namespace <your-hf-username-or-org>."
fi

# 3. Credentials resolve for the profile.
if [ -n "$(aws configure get aws_access_key_id --profile "$PROFILE" 2>/dev/null || true)" ]; then
    pass "credentials resolve for profile '$PROFILE'"
else
    fail "no aws_access_key_id for profile '$PROFILE'."
    note "Add a [hf] block with aws_access_key_id/aws_secret_access_key to $CREDENTIALS_FILE."
    note "Generate S3 creds: HF Settings -> Access Tokens -> token dropdown -> Generate S3 credentials."
fi

# 4. Connectivity: aws --profile hf s3 ls (interpret any failure).
echo ""
echo "  Probing gateway: aws --profile $PROFILE s3 ls"
set +e
probe_out="$(aws --profile "$PROFILE" s3 ls 2>&1)"
probe_rc=$?
set -e

if [ "$probe_rc" -eq 0 ]; then
    pass "'aws --profile $PROFILE s3 ls' succeeded — gateway reachable."
else
    fail "'aws --profile $PROFILE s3 ls' failed (exit $probe_rc)."
    printf '%s\n' "$probe_out" | sed 's/^/         | /'
    lc="$(printf '%s' "$probe_out" | tr '[:upper:]' '[:lower:]')"
    if printf '%s' "$lc" | grep -q 'checksum'; then
        note "Checksum error: set request_checksum_calculation and"
        note "response_checksum_validation = when_required in [profile hf]."
    fi
    if printf '%s' "$lc" | grep -Eq 'could not resolve host|name or service not known|nodename nor servname|getaddrinfo|failed to establish'; then
        note "Hostname/endpoint error: set addressing_style = path in the [profile hf] s3 block"
        note "(HF buckets are path segments, not virtual-host subdomains)."
    fi
    if printf '%s' "$lc" | grep -Eq '403|forbidden|accessdenied|access denied'; then
        note "HTTP 403: the token lacks Write permission or the credentials are wrong."
        note "Regenerate S3 credentials from an HF token with Write access."
    fi
fi

echo ""
if [ "$fails" -eq 0 ]; then
    echo "All checks passed. You're ready: ./demo_01_s3_basics.sh"
    exit 0
else
    echo "$fails check(s) failed. Fix the items above, then re-run ./check.sh"
    exit 1
fi
