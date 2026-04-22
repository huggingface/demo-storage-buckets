#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "polars>=1.0",
#   "pyarrow>=15",
#   "rich>=13",
# ]
# ///
"""Analytics payload run inside an HF Job. Mounts bucket rw at /workspace."""

from __future__ import annotations


def main(workspace: str) -> int:
    raise NotImplementedError("analytics.py main() not yet wired")


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1]))
