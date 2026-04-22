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


def main() -> int:
    raise NotImplementedError("demo.py main() not yet wired")


if __name__ == "__main__":
    raise SystemExit(main())
