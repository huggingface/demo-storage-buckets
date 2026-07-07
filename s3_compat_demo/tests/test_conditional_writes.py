#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest",
#   "boto3",
# ]
# ///
"""Offline unit tests for conditional_writes.py.

Fully offline: no network, no real boto3 client. The S3 client is a MagicMock,
and ClientError instances are constructed by hand. Run either as:
    uv run pytest tests/test_conditional_writes.py -q
    uv run tests/test_conditional_writes.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

# conditional_writes.py is a sibling of this tests/ directory's parent.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import conditional_writes as cw  # noqa: E402


# ─── Test helpers ─────────────────────────────────────────────────────────────


def make_client_error(code="PreconditionFailed", status=412, op="PutObject"):
    """Build a botocore ClientError mimicking a gateway response."""
    return ClientError(
        {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}},
        op,
    )


def fake_get_response(body: bytes, etag: str = '"etag-1"'):
    """A get_object-shaped dict whose Body.read() returns `body`."""
    resp = {"Body": MagicMock(), "ETag": etag}
    resp["Body"].read.return_value = body
    return resp


# ─── is_precondition_failed ─────────────────────────────────────────────────


def test_is_precondition_failed_true_for_412_status():
    assert cw.is_precondition_failed(make_client_error(status=412)) is True


def test_is_precondition_failed_true_for_412_status_without_matching_code():
    # 412 status but Code does NOT say PreconditionFailed — this isolates the
    # `status == 412` disjunct (the gateway can surface 412 as an HTTP status
    # with no parseable Error.Code, per is_precondition_failed's docstring). If
    # someone drops the status check, only this test fails.
    err = ClientError(
        {"Error": {"Code": "SomethingElse"}, "ResponseMetadata": {"HTTPStatusCode": 412}},
        "PutObject",
    )
    assert cw.is_precondition_failed(err) is True


def test_is_precondition_failed_true_for_code_only():
    err = ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
    assert cw.is_precondition_failed(err) is True


def test_is_precondition_failed_false_for_404():
    err = make_client_error(code="NoSuchKey", status=404)
    assert cw.is_precondition_failed(err) is False


def test_is_precondition_failed_false_for_403():
    err = make_client_error(code="AccessDenied", status=403)
    assert cw.is_precondition_failed(err) is False


# ─── create_if_absent ────────────────────────────────────────────────────────


def test_create_if_absent_returns_true_on_success():
    client = MagicMock()
    client.put_object.return_value = {"ETag": '"new"'}
    assert cw.create_if_absent(client, "bkt", "k", b"data") is True
    client.put_object.assert_called_once_with(
        Bucket="bkt", Key="k", Body=b"data", IfNoneMatch="*"
    )


def test_create_if_absent_returns_false_on_412():
    client = MagicMock()
    client.put_object.side_effect = make_client_error(status=412)
    assert cw.create_if_absent(client, "bkt", "k", b"data") is False


def test_create_if_absent_reraises_other_errors():
    client = MagicMock()
    client.put_object.side_effect = make_client_error(code="AccessDenied", status=403)
    with pytest.raises(ClientError):
        cw.create_if_absent(client, "bkt", "k", b"data")


# ─── compare_and_swap ────────────────────────────────────────────────────────


def test_compare_and_swap_succeeds_first_try():
    client = MagicMock()
    client.get_object.return_value = fake_get_response(b'{"v": 1}', etag='"e1"')
    client.put_object.return_value = {"ETag": '"e2"'}

    resp = cw.compare_and_swap(client, "bkt", "k", lambda old: old + b"!")

    assert resp == {"ETag": '"e2"'}
    assert client.get_object.call_count == 1
    client.put_object.assert_called_once_with(
        Bucket="bkt", Key="k", Body=b'{"v": 1}!', IfMatch='"e1"'
    )


def test_compare_and_swap_retries_after_one_412_then_succeeds():
    client = MagicMock()
    # Two reads: stale ETag first, fresh ETag on retry.
    client.get_object.side_effect = [
        fake_get_response(b"old", etag='"stale"'),
        fake_get_response(b"fresh", etag='"current"'),
    ]
    # First PUT hits the conditional guard; second PUT wins.
    client.put_object.side_effect = [
        make_client_error(status=412),
        {"ETag": '"final"'},
    ]

    resp = cw.compare_and_swap(client, "bkt", "k", lambda old: old + b"+")

    assert resp == {"ETag": '"final"'}
    assert client.get_object.call_count == 2
    assert client.put_object.call_count == 2
    # The winning PUT used the freshly re-read ETag and the re-mutated body.
    last_call = client.put_object.call_args_list[-1]
    assert last_call.kwargs["IfMatch"] == '"current"'
    assert last_call.kwargs["Body"] == b"fresh+"


def test_compare_and_swap_raises_after_exhausting_retries():
    client = MagicMock()
    client.get_object.return_value = fake_get_response(b"data", etag='"e"')
    client.put_object.side_effect = make_client_error(status=412)

    with pytest.raises(RuntimeError):
        cw.compare_and_swap(client, "bkt", "k", lambda old: old, max_retries=3)

    assert client.get_object.call_count == 3
    assert client.put_object.call_count == 3


def test_compare_and_swap_reraises_non_precondition_errors():
    client = MagicMock()
    client.get_object.return_value = fake_get_response(b"data", etag='"e"')
    client.put_object.side_effect = make_client_error(code="AccessDenied", status=403)

    with pytest.raises(ClientError):
        cw.compare_and_swap(client, "bkt", "k", lambda old: old)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
