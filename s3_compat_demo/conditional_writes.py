#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "boto3",
# ]
# ///
"""S3 conditional writes against the Hugging Face gateway, via boto3.

The HF Storage Buckets gateway speaks the S3 API, including the modern
conditional-write headers. This script demonstrates the two patterns that make
concurrent updates safe:

  1. No-clobber create  — PutObject with `If-None-Match: *`.
     Succeeds only if the key does not yet exist. A second writer racing to
     create the same key gets a 412 PreconditionFailed instead of clobbering.

  2. Compare-and-swap   — PutObject with `If-Match: <etag>`.
     Read-modify-write with optimistic concurrency: read the object + its ETag,
     mutate the bytes, then PUT guarded by the ETag we read. If a competing
     writer changed the object first, the PUT fails with 412 and we re-read and
     retry against the fresh object.

`main()` runs a DETERMINISTIC SEQUENTIAL simulation of two writers (A and B) —
no threads, fixed ordering — so the narrated output is reproducible for a live
demo. The conditional logic itself lives in small pure helpers
(`is_precondition_failed`, `create_if_absent`, `compare_and_swap`) that take a
client and are unit-tested offline with a mock.

NOTE (per the HF docs): `If-Match` / `If-None-Match` are honored on PutObject
(and on the copy-source of CopyObject) but NOT on GetObject.

Reference: https://huggingface.co/docs/hub/storage-buckets-s3
Run live (needs real HFAK... creds in the `hf` AWS profile):
    uv run conditional_writes.py --namespace your-username
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# ─── Defaults ───────────────────────────────────────────────────────────────

DEFAULT_BUCKET = "s3-compat-demo"
PROFILE_NAME = "hf"
MANIFEST_KEY = "manifest.json"
# The same shared object demo_02 uses, so both demos operate on one manifest.
MANIFEST_PATH = Path(__file__).parent / "sample_data" / "manifest.json"


# ─── Pure helpers (no argparse, no printing — unit-testable with a mock) ──────


def is_precondition_failed(err: ClientError) -> bool:
    """True if `err` is an S3 conditional-write rejection (HTTP 412).

    The gateway returns 412 PreconditionFailed when an `If-None-Match` /
    `If-Match` guard is not satisfied. botocore surfaces this either as an HTTP
    status code or as an error `Code` string depending on the path, so check
    both.
    """
    response = getattr(err, "response", None) or {}
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    code = response.get("Error", {}).get("Code")
    return status == 412 or code in {"PreconditionFailed", "412"}


def create_if_absent(client, bucket: str, key: str, body: bytes) -> bool:
    """No-clobber create: write `key` only if it does not already exist.

    Uses `If-None-Match: *`, honored by the gateway on PutObject. Returns True
    if we created the object, False if it already existed (412 caught). Any
    other error is re-raised.
    """
    try:
        client.put_object(Bucket=bucket, Key=key, Body=body, IfNoneMatch="*")
        return True
    except ClientError as err:
        if is_precondition_failed(err):
            return False
        raise


def compare_and_swap(
    client,
    bucket: str,
    key: str,
    mutate_fn: Callable[[bytes], bytes],
    max_retries: int = 5,
) -> dict:
    """Atomic read-modify-write of `key` via optimistic concurrency.

    Reads the current object + ETag, computes `mutate_fn(old_bytes) -> bytes`,
    then PUTs the result guarded by `If-Match: <etag>`. If a competing writer
    changed the object first, the gateway returns 412; we re-read and retry up
    to `max_retries` times. Returns the successful put_object response dict.
    Raises RuntimeError if every attempt is exhausted.
    """
    for _attempt in range(max_retries):
        current = client.get_object(Bucket=bucket, Key=key)
        old_bytes = current["Body"].read()
        # ETag from get_object is a quoted string (e.g. '"abc123"'); the gateway
        # expects that exact form in If-Match, so pass it through unchanged.
        etag = current["ETag"]
        new_body = mutate_fn(old_bytes)
        try:
            return client.put_object(
                Bucket=bucket, Key=key, Body=new_body, IfMatch=etag
            )
        except ClientError as err:
            if is_precondition_failed(err):
                # Someone else won the race; loop back and re-read the fresh object.
                continue
            raise
    raise RuntimeError(
        f"compare_and_swap: exhausted {max_retries} retries for "
        f"s3://{bucket}/{key} (object kept changing under us)"
    )


# ─── Wiring (namespace/bucket resolution + client) ───────────────────────────


def resolve_namespace(cli_value: str | None) -> str | None:
    """The namespace from `--namespace` or $HF_NAMESPACE, or None if neither is set.

    Unlike the shell demos (which read the endpoint from the `hf` profile), this
    script builds the gateway endpoint from the namespace directly, so it must be
    given explicitly — main() refuses to run against a guessed placeholder.
    """
    return cli_value or os.environ.get("HF_NAMESPACE")


def resolve_bucket(cli_value: str | None) -> str:
    """`--bucket`, else $DEMO_BUCKET, else the default demo bucket."""
    return cli_value or os.environ.get("DEMO_BUCKET") or DEFAULT_BUCKET


def build_client(namespace: str):
    """Build an S3 client pointed at the HF gateway for `namespace`.

    Mirrors the boto3 example in the HF docs: creds come from the `hf` profile
    in ~/.aws/credentials, the endpoint is the namespace-scoped gateway, and the
    checksum settings disable the trailing aws-chunked CRC32 the gateway does
    not parse.
    """
    session = boto3.Session(profile_name=PROFILE_NAME)
    return session.client(
        "s3",
        endpoint_url=f"https://s3.hf.co/{namespace}",
        config=Config(
            region_name="us-east-1",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def ensure_bucket(client, bucket: str) -> None:
    """Create `bucket` if it does not already exist (idempotent).

    Lets the script run standalone — the shell demos also self-provision the
    bucket. Already-exists is fine; any other error is a real problem.
    """
    try:
        client.create_bucket(Bucket=bucket)
    except ClientError as err:
        code = (getattr(err, "response", None) or {}).get("Error", {}).get("Code", "")
        if code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise


# ─── Narrated demo (talks to the real gateway; run live by the presenter) ─────


def pause(enabled: bool) -> None:
    """Wait for the presenter to press Enter between steps.

    No-op when disabled (--no-pause / NO_PAUSE) or when stdin is not a TTY, so
    automated runs do not hang.
    """
    if not enabled or not sys.stdin.isatty():
        return
    try:
        input("\n  [Enter] to continue... ")
    except EOFError:
        pass


def main() -> int:
    """Run the deterministic two-writer conditional-writes story."""
    parser = argparse.ArgumentParser(
        description="Demonstrate S3 conditional writes against the HF gateway."
    )
    parser.add_argument("--namespace", default=None, help="HF username or org")
    parser.add_argument("--bucket", default=None, help="bucket name")
    parser.add_argument(
        "--no-pause", action="store_true",
        help="don't pause for Enter between steps (also via NO_PAUSE=1)",
    )
    args = parser.parse_args()

    paused = not args.no_pause and not os.environ.get("NO_PAUSE")

    namespace = resolve_namespace(args.namespace)
    if not namespace:
        print(
            "ERROR: no namespace. Pass --namespace <your-username-or-org> or set "
            "HF_NAMESPACE.\nThis script builds the gateway endpoint from the "
            "namespace directly (the shell demos read it from the `hf` profile).",
            file=sys.stderr,
        )
        return 2
    bucket = resolve_bucket(args.bucket)
    key = MANIFEST_KEY
    client = build_client(namespace)

    print(f"\nendpoint: https://s3.hf.co/{namespace}")
    print(f"target:   s3://{bucket}/{key}\n")

    # Make this runnable standalone and repeatable: create the bucket if needed
    # and clear any leftover key so "Writer A creates" reliably wins.
    ensure_bucket(client, bucket)
    try:
        client.delete_object(Bucket=bucket, Key=key)
    except ClientError:
        pass

    # The shared manifest demo_02 also uses — both demos operate on one object.
    manifest_bytes = MANIFEST_PATH.read_bytes()

    # Step 1 — Writer A creates the manifest (wins the no-clobber race).
    pause(paused)
    print("[1] Writer A: create_if_absent (If-None-Match:*)")
    if create_if_absent(client, bucket, key, manifest_bytes):
        print("    -> created")
    else:
        print("    -> already existed (a previous run left it behind)")

    # Step 2 — Writer B tries the same create and is rejected (no clobber).
    pause(paused)
    print("\n[2] Writer B: create_if_absent on the same key (If-None-Match:*)")
    if create_if_absent(client, bucket, key, manifest_bytes):
        print("    -> created (unexpected: key was absent)")
    else:
        print("    -> rejected: already exists, no clobber")

    # Step 3 — Compare-and-swap: read, bump the version field, put with If-Match.
    pause(paused)
    print("\n[3] Writer B: compare_and_swap — bump the version field")

    def bump_version(old_bytes: bytes) -> bytes:
        doc = json.loads(old_bytes)
        doc["version"] = int(doc.get("version", 0)) + 1
        doc["updated_by"] = "writer-B"
        return json.dumps(doc, indent=2).encode()

    resp = compare_and_swap(client, bucket, key, bump_version)
    print(f"    -> CAS succeeded; new ETag {resp.get('ETag')}")

    # Step 4 — A stale-ETag conflict, absorbed by the retry loop.
    # To show the loop deterministically against a live gateway, the mutate
    # function injects ONE competing write the first time it runs: it commits an
    # unconditional put (standing in for another process winning the race) after
    # compare_and_swap has already read the ETag. That first If-Match PUT then
    # fails with 412; the loop re-reads and retries, uncontested this time, and
    # succeeds.
    pause(paused)
    print("\n[4] Writer A: compare_and_swap racing a competing writer")
    interference = {"fired": False}

    def bump_with_one_conflict(old_bytes: bytes) -> bytes:
        if not interference["fired"]:
            interference["fired"] = True
            sneaky = json.loads(old_bytes)
            sneaky["version"] = int(sneaky.get("version", 0)) + 1
            sneaky["updated_by"] = "competing-writer"
            # Unconditional put == "someone else committed first", invalidating
            # the ETag compare_and_swap just read.
            client.put_object(
                Bucket=bucket, Key=key, Body=json.dumps(sneaky, indent=2).encode()
            )
            print("    .. a competing writer slipped in (ETag now stale)")
        doc = json.loads(old_bytes)
        doc["version"] = int(doc.get("version", 0)) + 1
        doc["updated_by"] = "writer-A"
        return json.dumps(doc, indent=2).encode()

    resp = compare_and_swap(client, bucket, key, bump_with_one_conflict)
    print(f"    -> retry loop absorbed the 412; CAS succeeded; ETag {resp.get('ETag')}")

    print("\nDone. Conditional writes kept every update safe.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
