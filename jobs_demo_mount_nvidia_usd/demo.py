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


def main() -> int:
    raise NotImplementedError("demo.py main() not yet wired")


if __name__ == "__main__":
    raise SystemExit(main())
