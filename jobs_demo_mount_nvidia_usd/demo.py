#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "huggingface_hub>=1.11",
#   "polars>=1.0",
#   "pyarrow>=15",
#   "rich>=13",
# ]
# ///
"""HF Buckets + hf-mount + HF Jobs demo for NVIDIA Cosmos pre-training data.

Run: uv run demo.py
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, Literal

_UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
_NEW_DATA_RE = re.compile(r'([\d.]+)([KMGT]?B)\s*/\s*([\d.]+)([KMGT]?B)')


def parse_new_data_bytes(stderr_text: str) -> int:
    """Parse `hf buckets cp` stderr for the last "New Data Upload" line and
    return its total-new bytes. Returns -1 if no match."""
    last_match = None
    for line in stderr_text.splitlines():
        if "New Data Upload" not in line:
            continue
        m = _NEW_DATA_RE.search(line)
        if m:
            last_match = m
    if last_match is None:
        return -1
    return int(float(last_match.group(3)) * _UNITS.get(last_match.group(4), 1))


def build_job_url(namespace: str, job_id: str) -> str:
    """Return the Hub URL for a Job."""
    return f"https://huggingface.co/jobs/{namespace}/{job_id}"


JobStatus = Literal["pending", "running", "succeeded", "failed", "cancelled", "timeout", "interrupted"]


@dataclass
class JobResult:
    status: JobStatus
    elapsed_s: float


def poll_job(
    job_id: str,
    poll_interval: float,
    timeout: float,
    inspector: Callable[[str], str],
) -> JobResult:
    """Block until the Job reaches a terminal state, times out, or is
    interrupted. `inspector(job_id)` must return 'pending' | 'running' |
    'succeeded' | 'failed' | 'cancelled'. Ctrl-C yields 'interrupted' and
    leaves the remote Job running."""
    TERMINAL_OK = {"succeeded"}
    TERMINAL_BAD = {"failed", "cancelled"}
    start = time.monotonic()
    while True:
        try:
            status = inspector(job_id)
        except KeyboardInterrupt:
            return JobResult(status="interrupted", elapsed_s=time.monotonic() - start)

        if status in TERMINAL_OK or status in TERMINAL_BAD:
            return JobResult(status=status, elapsed_s=time.monotonic() - start)

        now = time.monotonic()
        if (now - start) >= timeout:
            return JobResult(status="timeout", elapsed_s=now - start)

        time.sleep(poll_interval)


def mutate_csv_add_grasp_score(src_csv: str, dst_csv: str) -> None:
    """Read `src_csv`, add `grasp_score = 1/(1+mass)` (nulls→1.0), write to `dst_csv`."""
    import polars as pl
    df = pl.read_csv(src_csv)
    df = df.with_columns(
        (1.0 / (1.0 + pl.col("mass").fill_null(1.0))).alias("grasp_score")
    )
    df.write_csv(dst_csv)


import subprocess
import tempfile
from pathlib import Path


class HFCliError(RuntimeError):
    pass


def hf_whoami() -> str:
    """Return the authenticated HF username. Raises HFCliError if not logged in."""
    r = subprocess.run(
        ["hf", "auth", "whoami"], capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        raise HFCliError(f"hf auth whoami failed: {r.stderr.strip()}")
    return r.stdout.strip().splitlines()[0].strip()


def ensure_bucket(bucket: str) -> None:
    """Create the bucket private; silently no-op if it already exists."""
    subprocess.run(
        ["hf", "buckets", "create", bucket, "--private"],
        capture_output=True, text=True, check=False,
    )


def run_hf_cp_capture(src: str, dst: str) -> tuple[int, int, str]:
    """Run `hf buckets cp SRC DST`, stream stderr to terminal, return
    (elapsed_ms, new_bytes, full_stderr). new_bytes is -1 if unparsed."""
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as log:
        log_path = log.name
    cmd = f"hf buckets cp {src} {dst} 2> >(tee {log_path} >&2)"
    t0 = time.monotonic()
    proc = subprocess.run(cmd, shell=True, executable="/bin/bash")
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    stderr_text = Path(log_path).read_text()
    Path(log_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise HFCliError(f"hf buckets cp failed (exit {proc.returncode}): {src} -> {dst}")
    return elapsed_ms, parse_new_data_bytes(stderr_text), stderr_text


def submit_job(script_path: str, bucket: str, flavor: str = "cpu-basic") -> str:
    """Submit `script_path` to HF Jobs via `hf jobs uv run --detach`. Returns job_id."""
    r = subprocess.run(
        [
            "hf", "jobs", "uv", "run", "--detach",
            "--flavor", flavor,
            "-v", f"hf://buckets/{bucket}:/workspace",
            script_path, "/workspace",
        ],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        raise HFCliError(f"hf jobs uv run failed: {r.stderr.strip()}")
    job_id = r.stdout.strip().splitlines()[-1].strip()
    if not job_id:
        raise HFCliError(f"hf jobs uv run returned no job_id. stdout={r.stdout!r}")
    return job_id


def inspect_job_status(job_id: str) -> str:
    """Return the Job's lowercase status ('pending'|'running'|'succeeded'|'failed'|'cancelled')."""
    import json
    r = subprocess.run(
        ["hf", "jobs", "inspect", job_id],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        raise HFCliError(f"hf jobs inspect failed: {r.stderr.strip()}")
    data = json.loads(r.stdout)
    obj = data[0] if isinstance(data, list) else data
    status = obj.get("status", {})
    stage = status.get("stage") if isinstance(status, dict) else status
    return str(stage).lower() if stage else "unknown"


def main() -> int:
    raise NotImplementedError("demo.py main() not yet wired")


if __name__ == "__main__":
    raise SystemExit(main())
