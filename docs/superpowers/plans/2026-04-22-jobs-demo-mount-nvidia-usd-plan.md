# jobs_demo_mount_nvidia_usd Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained `uv`-driven demo (`uv run demo.py`) that shows Hugging Face Storage Buckets + `hf-mount` + HF Jobs powering a Cosmos-style pre-training data workflow — ingest `nvidia/PhysicalAI-SimReady-Warehouse-01` into a bucket, run polars analytics in a Job, mutate the CSV and re-sync to demonstrate Xet dedupe.

**Architecture:** Two PEP 723 single-file scripts. `demo.py` runs locally and orchestrates `hf` CLI calls (`auth whoami`, `buckets create/cp`, `jobs uv run --detach`, `jobs inspect`). `job/analytics.py` runs inside an HF Job (`hf jobs uv run` handles upload + deps), mounts the user's bucket rw at `/workspace`, reads the ingested dataset, and writes analytics + curated manifests back. Helpers factored into importable functions so pytest can exercise the poll loop, bytes parser, and polars mutation without Job submission.

**Tech Stack:** Python 3.11+, `uv`, `huggingface_hub>=1.11`, `polars`, `pyarrow`, `rich`, `pytest`. HF CLI `hf` ≥ 1.11 (confirmed `hf jobs uv run` + `-d/--detach` + `--volume` exist).

---

## File Structure

```
demo-storage-buckets/
├── README.md                                    # MODIFY: top-level, links both demos
├── basic_demo/                                  # CREATE: existing files moved here
│   ├── README.md                                # (moved)
│   ├── TALK_TRACK.md                            # (moved)
│   ├── demo_01_xet_dedup.py                     # (moved)
│   ├── demo_02_bucket_basics.sh                 # (moved)
│   ├── demo_03_hf_mount.sh                      # (moved)
│   ├── demo_04_dataset_sync.sh                  # (moved)
│   ├── prep.sh                                  # (moved)
│   ├── cleanup.sh                               # (moved)
│   └── *.pdf                                    # (moved)
└── jobs_demo_mount_nvidia_usd/
    ├── README.md                                # CREATE: setup + how to run
    ├── demo.py                                  # CREATE: PEP 723 entry point
    ├── job/
    │   └── analytics.py                         # CREATE: PEP 723 Job payload
    ├── cleanup.sh                               # CREATE: idempotent teardown
    └── tests/
        ├── conftest.py                          # CREATE: sys.path injection
        ├── fixtures/
        │   └── tiny_metadata.csv                # CREATE: 5-row polars fixture
        ├── test_demo_helpers.py                 # CREATE: unit tests
        └── test_analytics_helpers.py            # CREATE: unit tests
```

**Responsibility boundaries:**
- `demo.py` — CLI orchestration, subprocess wrappers, poll loop, bytes parsing, CSV mutation. Must stay importable (no top-level side effects; everything behind `main()` + `if __name__ == "__main__"`).
- `job/analytics.py` — data-plane only. Takes workspace path, reads CSV + stats files, produces 3 artifacts. No CLI calls, no network beyond the hf-mount-backed filesystem.
- `tests/test_demo_helpers.py` — unit tests for the 4 testable functions (`parse_new_data_bytes`, `poll_job`, `mutate_csv_add_grasp_score`, `build_job_url`). No subprocess calls to real `hf`.
- `tests/test_analytics_helpers.py` — unit tests for `aggregate_by_label`, `curate_grasp_ready`. Uses `fixtures/tiny_metadata.csv`.

---

## Task 1: Move existing demos into `basic_demo/` subdir

**Files:**
- Move: `TALK_TRACK.md`, `cleanup.sh`, `demo_01_xet_dedup.py`, `demo_02_bucket_basics.sh`, `demo_03_hf_mount.sh`, `demo_04_dataset_sync.sh`, `prep.sh`, `README.md`, `Hugging_Face_Storage_Buckets_for_NVIDIA_Research.docx.pdf`, `Hugging_Face_Storage_Buckets_for_NVIDIA_Research.pptx.pdf` → `basic_demo/`
- Leave in place: `.git/`, `.gitignore`, `.venv/`

- [ ] **Step 1: Create `basic_demo/` and move files with `git mv`**

```bash
cd ~/code/hf/demo-storage-buckets
mkdir basic_demo
git mv TALK_TRACK.md cleanup.sh demo_01_xet_dedup.py demo_02_bucket_basics.sh \
       demo_03_hf_mount.sh demo_04_dataset_sync.sh prep.sh README.md \
       Hugging_Face_Storage_Buckets_for_NVIDIA_Research.docx.pdf \
       Hugging_Face_Storage_Buckets_for_NVIDIA_Research.pptx.pdf \
       basic_demo/
```

- [ ] **Step 2: Verify the move preserved prior uncommitted edits**

Run: `git status` — expect all moved files listed as `R  basic_demo/<file>` (rename) with their prior modifications still present.

- [ ] **Step 3: Commit the move**

```bash
git commit -m "Move existing demos to basic_demo/ subdir

Make room for the new jobs_demo_mount_nvidia_usd/ sibling. No content
changes; file modifications preserved as part of the rename.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Create top-level `README.md`

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the new top-level README**

```markdown
# demo-storage-buckets

Demos showcasing Hugging Face Storage Buckets, Xet, `hf-mount`, and HF Jobs.

## [`basic_demo/`](./basic_demo/)

Original demos for the Apr 7 2026 NVIDIA meeting. Covers Xet checkpoint
dedupe, bucket basics + CDN pre-warming, `hf-mount` filesystem access,
and dataset sync. See [`basic_demo/TALK_TRACK.md`](./basic_demo/TALK_TRACK.md)
for the 20-min talk track.

## [`jobs_demo_mount_nvidia_usd/`](./jobs_demo_mount_nvidia_usd/)

Cosmos-style pre-training data workflow:

1. Ingest `nvidia/PhysicalAI-SimReady-Warehouse-01` into a user bucket —
   near-zero byte transfer (Xet-to-Xet).
2. Launch a CPU HF Job that mounts the bucket read-write and runs
   polars analytics over the USD + CSV + PNG assets.
3. Mutate the dataset metadata (add a Cosmos-graspability column) and
   re-sync to show Xet chunk-level dedupe on the data side.

Run with `uv run jobs_demo_mount_nvidia_usd/demo.py`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Add top-level README linking basic_demo/ and jobs_demo_mount_nvidia_usd/

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Scaffold `jobs_demo_mount_nvidia_usd/` directory

**Files:**
- Create: `jobs_demo_mount_nvidia_usd/demo.py` (stub)
- Create: `jobs_demo_mount_nvidia_usd/job/analytics.py` (stub)
- Create: `jobs_demo_mount_nvidia_usd/tests/conftest.py`
- Create: `jobs_demo_mount_nvidia_usd/tests/fixtures/tiny_metadata.csv`

- [ ] **Step 1: Create `demo.py` stub with PEP 723 header and `main` stub**

```python
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
"""Jobs + hf-mount + Storage Buckets demo for NVIDIA Cosmos pre-training.

Run:    uv run demo.py
Docs:   see README.md and ../docs/superpowers/specs/2026-04-22-jobs-demo-mount-nvidia-usd-design.md
"""

from __future__ import annotations


def main() -> int:
    raise NotImplementedError("demo.py main() not yet wired")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Create `job/analytics.py` stub with PEP 723 header**

```python
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
```

- [ ] **Step 3: Create `tests/conftest.py` to make `demo.py` and `analytics.py` importable**

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "job"))
```

- [ ] **Step 4: Create `tests/fixtures/tiny_metadata.csv` — a 5-row fixture modeled on the real dataset schema**

```csv
asset_preview,asset_name,relative_path,classification,label,q_code,mass,thumbnail_path
https://example.com/a.png,sm_book_a,Props/HM/book/sm_book_a.usd,Prop general hand manipulation,book,Q571,0.4,renders/sm_book_a.png
https://example.com/b.png,sm_mug_a,Props/HM/mug/sm_mug_a.usd,Prop general hand manipulation,mug,Q1057697,0.3,renders/sm_mug_a.png
https://example.com/c.png,sm_crate_a,Assembly/crate/sm_crate_a.usd,Assembly,crate,Q605384,15.0,renders/sm_crate_a.png
https://example.com/d.png,sm_brush_a,Props/HM/brush/sm_brush_a.usd,Prop general hand manipulation,paintbrush,Q1402267,0.05,renders/sm_brush_a.png
https://example.com/e.png,sm_warehouse_a,Scenario/warehouse/sm_warehouse_a.usd,Scenario,warehouse,Q196426,,renders/sm_warehouse_a.png
```

- [ ] **Step 5: Commit the scaffold**

```bash
git add jobs_demo_mount_nvidia_usd/
git commit -m "Scaffold jobs_demo_mount_nvidia_usd/ with PEP 723 stubs + test fixtures

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: TDD `parse_new_data_bytes` in demo.py

Lift the logic from `basic_demo/demo_01_xet_dedup.py:64` and test it directly instead of leaving it untested.

**Files:**
- Modify: `jobs_demo_mount_nvidia_usd/demo.py`
- Modify: `jobs_demo_mount_nvidia_usd/tests/test_demo_helpers.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_demo_helpers.py`:

```python
import demo


def test_parse_new_data_bytes_megabytes():
    stderr = (
        "Computing xorbs: 100%|#####| 2/2 [00:00<00:00]\n"
        "New Data Upload  : 100%|#####|  1.05MB / 1.05MB\n"
    )
    assert demo.parse_new_data_bytes(stderr) == int(1.05 * 1024 * 1024)


def test_parse_new_data_bytes_zero_bytes():
    stderr = "New Data Upload  : |#####|  0.00B / 0.00B\n"
    assert demo.parse_new_data_bytes(stderr) == 0


def test_parse_new_data_bytes_missing_returns_negative_one():
    assert demo.parse_new_data_bytes("nothing relevant here") == -1


def test_parse_new_data_bytes_uses_last_match():
    stderr = (
        "New Data Upload  : 50%|##|  0.10MB / 1.05MB\n"
        "New Data Upload  : 100%|#####|  1.05MB / 1.05MB\n"
    )
    assert demo.parse_new_data_bytes(stderr) == int(1.05 * 1024 * 1024)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/code/hf/demo-storage-buckets/jobs_demo_mount_nvidia_usd
uv run --with pytest pytest tests/test_demo_helpers.py -v
```

Expected: 4 failures with `AttributeError: module 'demo' has no attribute 'parse_new_data_bytes'`.

- [ ] **Step 3: Implement `parse_new_data_bytes`**

Add to `demo.py` above `main()`:

```python
import re

_UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
_NEW_DATA_RE = re.compile(r'([\d.]+)([KMGT]?B)\s*/\s*([\d.]+)([KMGT]?B)')


def parse_new_data_bytes(stderr_text: str) -> int:
    """Parse the 'New Data Upload' line from `hf buckets cp` stderr.

    Returns the total-new bytes (the value after the '/' in the last matching
    progress line), or -1 if no matching line is found.
    """
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --with pytest pytest tests/test_demo_helpers.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add jobs_demo_mount_nvidia_usd/demo.py jobs_demo_mount_nvidia_usd/tests/test_demo_helpers.py
git commit -m "Add parse_new_data_bytes helper with tests

Lifts the stderr parser from basic_demo/demo_01_xet_dedup.py:64 and
tests it for MB / zero-bytes / missing / last-match-wins cases.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: TDD `build_job_url` in demo.py

**Files:**
- Modify: `jobs_demo_mount_nvidia_usd/demo.py`
- Modify: `jobs_demo_mount_nvidia_usd/tests/test_demo_helpers.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_demo_helpers.py`:

```python
def test_build_job_url_with_namespace():
    assert (
        demo.build_job_url("rajatarya", "abc123def")
        == "https://huggingface.co/jobs/rajatarya/abc123def"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run --with pytest pytest tests/test_demo_helpers.py::test_build_job_url_with_namespace -v
```

Expected: `AttributeError: module 'demo' has no attribute 'build_job_url'`.

- [ ] **Step 3: Implement `build_job_url`**

Add to `demo.py`:

```python
def build_job_url(namespace: str, job_id: str) -> str:
    """Build the Hub URL for a Job so the user can open it in a browser."""
    return f"https://huggingface.co/jobs/{namespace}/{job_id}"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run --with pytest pytest tests/test_demo_helpers.py::test_build_job_url_with_namespace -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add jobs_demo_mount_nvidia_usd/demo.py jobs_demo_mount_nvidia_usd/tests/test_demo_helpers.py
git commit -m "Add build_job_url helper"
```

---

## Task 6: TDD `poll_job` (success / failure / timeout / interrupt)

This is the most behavior-rich helper. The function takes an `inspector` callable so tests can fully control the status sequence without spawning subprocesses.

**Files:**
- Modify: `jobs_demo_mount_nvidia_usd/demo.py`
- Modify: `jobs_demo_mount_nvidia_usd/tests/test_demo_helpers.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_demo_helpers.py`:

```python
import pytest


def _inspector_from_sequence(statuses):
    """Returns an inspector callable that yields one status per call."""
    it = iter(statuses)

    def inspect(_job_id):
        return next(it)
    return inspect


def test_poll_job_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)  # fast-forward
    inspector = _inspector_from_sequence(["pending", "running", "succeeded"])
    result = demo.poll_job(
        job_id="abc", poll_interval=0.01, timeout=30, inspector=inspector
    )
    assert result.status == "succeeded"
    assert result.elapsed_s >= 0


def test_poll_job_fails(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)
    inspector = _inspector_from_sequence(["running", "failed"])
    result = demo.poll_job(
        job_id="abc", poll_interval=0.01, timeout=30, inspector=inspector
    )
    assert result.status == "failed"


def test_poll_job_cancelled(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)
    inspector = _inspector_from_sequence(["cancelled"])
    result = demo.poll_job(
        job_id="abc", poll_interval=0.01, timeout=30, inspector=inspector
    )
    assert result.status == "cancelled"


def test_poll_job_times_out(monkeypatch):
    # Always-running inspector; timeout should kick in.
    monkeypatch.setattr("time.sleep", lambda _s: None)
    monotonic_vals = iter([0.0, 0.1, 0.2, 99.0])
    monkeypatch.setattr("time.monotonic", lambda: next(monotonic_vals))
    inspector = lambda _j: "running"
    result = demo.poll_job(
        job_id="abc", poll_interval=0.01, timeout=1.0, inspector=inspector
    )
    assert result.status == "timeout"


def test_poll_job_keyboard_interrupt_returns_interrupted(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)

    def inspect(_j):
        raise KeyboardInterrupt

    result = demo.poll_job(
        job_id="abc", poll_interval=0.01, timeout=30, inspector=inspect
    )
    assert result.status == "interrupted"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --with pytest pytest tests/test_demo_helpers.py -v -k poll_job
```

Expected: 5 failures with `AttributeError: module 'demo' has no attribute 'poll_job'`.

- [ ] **Step 3: Implement `poll_job` and its result dataclass**

Add to `demo.py`:

```python
import time
from dataclasses import dataclass
from typing import Callable, Literal

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
    """Block until the Job reaches a terminal state or timeout.

    `inspector(job_id)` is called every `poll_interval` seconds. It must
    return one of 'pending', 'running', 'succeeded', 'failed', 'cancelled'.
    KeyboardInterrupt returns an 'interrupted' result (leaves the Job
    running on HF).
    """
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

        if (time.monotonic() - start) >= timeout:
            return JobResult(status="timeout", elapsed_s=time.monotonic() - start)

        time.sleep(poll_interval)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --with pytest pytest tests/test_demo_helpers.py -v -k poll_job
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add jobs_demo_mount_nvidia_usd/demo.py jobs_demo_mount_nvidia_usd/tests/test_demo_helpers.py
git commit -m "Add poll_job with terminal-state/timeout/interrupt handling"
```

---

## Task 7: TDD `mutate_csv_add_grasp_score`

**Files:**
- Modify: `jobs_demo_mount_nvidia_usd/demo.py`
- Modify: `jobs_demo_mount_nvidia_usd/tests/test_demo_helpers.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_demo_helpers.py`:

```python
def test_mutate_csv_add_grasp_score(tmp_path):
    import polars as pl
    src = tmp_path / "in.csv"
    src.write_text(
        "asset_name,mass\n"
        "a,0.5\n"
        "b,\n"        # null mass
        "c,4.0\n"
    )
    dst = tmp_path / "out.csv"

    demo.mutate_csv_add_grasp_score(str(src), str(dst))

    df = pl.read_csv(str(dst))
    assert df.columns == ["asset_name", "mass", "grasp_score"]
    scores = df["grasp_score"].to_list()
    # grasp_score = 1 / (1 + mass.fill_null(1.0))
    assert abs(scores[0] - (1.0 / 1.5)) < 1e-6
    assert abs(scores[1] - (1.0 / 2.0)) < 1e-6  # null -> 1.0
    assert abs(scores[2] - (1.0 / 5.0)) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run --with pytest pytest tests/test_demo_helpers.py::test_mutate_csv_add_grasp_score -v
```

Expected: `AttributeError: module 'demo' has no attribute 'mutate_csv_add_grasp_score'`.

- [ ] **Step 3: Implement `mutate_csv_add_grasp_score`**

Add to `demo.py`:

```python
def mutate_csv_add_grasp_score(src_csv: str, dst_csv: str) -> None:
    """Read the SimReady metadata CSV, add `grasp_score = 1 / (1 + mass)`,
    write the augmented CSV. Null mass values are treated as 1.0 kg."""
    import polars as pl
    df = pl.read_csv(src_csv)
    df = df.with_columns(
        (1.0 / (1.0 + pl.col("mass").fill_null(1.0))).alias("grasp_score")
    )
    df.write_csv(dst_csv)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run --with pytest pytest tests/test_demo_helpers.py::test_mutate_csv_add_grasp_score -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add jobs_demo_mount_nvidia_usd/demo.py jobs_demo_mount_nvidia_usd/tests/test_demo_helpers.py
git commit -m "Add mutate_csv_add_grasp_score (pre-training curation column)"
```

---

## Task 8: Subprocess helpers (`hf_whoami`, `run_hf_cp_capture`, `submit_job`, `inspect_job_status`)

These wrap `hf` CLI calls. They're thin and the heavy lifting lives in CLI parity, so we smoke-test with a fake `hf` shim rather than full unit tests.

**Files:**
- Modify: `jobs_demo_mount_nvidia_usd/demo.py`

- [ ] **Step 1: Add the four wrappers**

Add to `demo.py`:

```python
import subprocess
import tempfile
from pathlib import Path


class HFCliError(RuntimeError):
    pass


def hf_whoami() -> str:
    """Return the current HF username. Raises HFCliError if not authenticated."""
    r = subprocess.run(
        ["hf", "auth", "whoami"], capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        raise HFCliError(f"hf auth whoami failed: {r.stderr.strip()}")
    # `hf auth whoami` prints one line with the username.
    return r.stdout.strip().splitlines()[0].strip()


def ensure_bucket(bucket: str) -> None:
    """Create the bucket private; no-op if it already exists."""
    subprocess.run(
        ["hf", "buckets", "create", bucket, "--private"],
        capture_output=True, text=True, check=False,
    )
    # Any error (including already-exists) is silently accepted here;
    # subsequent `hf buckets cp` will surface real auth/quota problems.


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
    """Submit the analytics Job in detached mode. Returns the job_id
    printed by `hf jobs uv run -d`."""
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
    # Detach mode prints the job_id on stdout.
    job_id = r.stdout.strip().splitlines()[-1].strip()
    if not job_id:
        raise HFCliError(f"hf jobs uv run returned no job_id. stdout={r.stdout!r}")
    return job_id


def inspect_job_status(job_id: str) -> str:
    """Return the Job's status as a lowercase string. Parses `hf jobs inspect`
    JSON output. If the CLI surface evolves, adapt the JSON path here."""
    import json
    r = subprocess.run(
        ["hf", "jobs", "inspect", job_id],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        raise HFCliError(f"hf jobs inspect failed: {r.stderr.strip()}")
    # `hf jobs inspect` prints a JSON array with one object. The object has
    # a "status" field like {"stage": "RUNNING"} or similar. Verify the
    # exact shape on first run and adjust this extraction.
    data = json.loads(r.stdout)
    obj = data[0] if isinstance(data, list) else data
    status = obj.get("status", {})
    stage = status.get("stage") if isinstance(status, dict) else status
    return str(stage).lower() if stage else "unknown"
```

- [ ] **Step 2: Verify `hf jobs inspect` JSON shape against a real Job (one-time)**

Against a running or completed real Job (from a prior run or `hf jobs ps -a`):

```bash
JOB_ID=$(hf jobs ps -a -q | head -1)
hf jobs inspect "$JOB_ID"
```

If the printed JSON's status field is not at `[0].status.stage`, adjust `inspect_job_status` accordingly. Expected terminal values to map from: `SUCCEEDED`, `FAILED`, `CANCELLED`, `RUNNING`, `PENDING` → lowercased versions.

- [ ] **Step 3: Commit**

```bash
git add jobs_demo_mount_nvidia_usd/demo.py
git commit -m "Add hf CLI subprocess wrappers (whoami, cp, submit, inspect)"
```

---

## Task 9: Wire `demo.py main()` — CLI + phase orchestration

**Files:**
- Modify: `jobs_demo_mount_nvidia_usd/demo.py`

- [ ] **Step 1: Replace the `main()` stub with the full orchestration**

Replace the `NotImplementedError` body in `main()` with:

```python
import argparse
import json
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

NVIDIA_DATASET = "hf://datasets/nvidia/PhysicalAI-SimReady-Warehouse-01"
NOMINAL_DATASET_BYTES = 14 * 1024**3 + 400 * 1024**2  # 14.4 GB
DATASET_CSV = "physical_ai_simready_warehouse_01.csv"

console = Console()


def _print_bytes_panel(title: str, nominal: int, transferred: int, elapsed_ms: int) -> None:
    if transferred < 0:
        body = "(new-bytes metric not reported by this CLI version)"
    else:
        pct_saved = (1 - transferred / nominal) * 100 if nominal > 0 else 0
        body = (
            f"nominal      : {nominal / 1024**2:>8.1f} MB\n"
            f"transferred  : {transferred / 1024**2:>8.1f} MB\n"
            f"dedup saved  : {pct_saved:>8.1f} %\n"
            f"elapsed      : {elapsed_ms / 1000:>8.1f} s"
        )
    console.print(Panel(body, title=title))


def main() -> int:
    p = argparse.ArgumentParser(description="HF Buckets + hf-mount + HF Jobs demo")
    p.add_argument("--bucket", default=None,
                   help="override bucket name (default: <user>/nvidia-simready)")
    p.add_argument("--poll-interval", type=float, default=3.0)
    p.add_argument("--job-timeout", type=float, default=15 * 60)
    p.add_argument("--skip-ingest", action="store_true")
    p.add_argument("--skip-job", action="store_true")
    p.add_argument("--skip-mutate", action="store_true")
    p.add_argument("--flavor", default="cpu-basic")
    args = p.parse_args()

    # --- Phase 1: preflight ---
    console.rule("[bold]Phase 1 — preflight")
    user = hf_whoami()
    bucket = args.bucket or f"{user}/nvidia-simready"
    console.print(f"user:   {user}\nbucket: {bucket}")

    # --- Phase 2: ensure bucket ---
    console.rule("[bold]Phase 2 — ensure bucket")
    ensure_bucket(bucket)
    console.print(f"[green]bucket ready[/green]: hf://buckets/{bucket}")

    # --- Phase 3: ingest ---
    if not args.skip_ingest:
        console.rule("[bold]Phase 3 — ingest dataset → bucket")
        elapsed_ms, new_bytes, _ = run_hf_cp_capture(
            NVIDIA_DATASET, f"hf://buckets/{bucket}/dataset/"
        )
        _print_bytes_panel(
            "Pre-training ingest", NOMINAL_DATASET_BYTES, new_bytes, elapsed_ms
        )
    else:
        console.print("[yellow]--skip-ingest: phase 3 skipped[/yellow]")

    # --- Phase 4-6: Job lifecycle ---
    if not args.skip_job:
        console.rule("[bold]Phase 4 — submit Job")
        script_path = str(Path(__file__).parent / "job" / "analytics.py")
        job_id = submit_job(script_path, bucket, flavor=args.flavor)
        job_url = build_job_url(user, job_id)
        console.print(Panel(
            f"job_id: {job_id}\nurl:    {job_url}",
            title="Job submitted — open in browser if you like",
            border_style="cyan",
        ))

        console.rule("[bold]Phase 5 — poll (every {:.0f}s)".format(args.poll_interval))
        result = poll_job(job_id, args.poll_interval, args.job_timeout, inspect_job_status)
        console.print(f"job finished: status={result.status} elapsed={result.elapsed_s:.1f}s")
        if result.status != "succeeded":
            console.print(f"[red]Job did not succeed. URL: {job_url}[/red]")
            if result.status == "failed":
                subprocess.run(["hf", "jobs", "logs", job_id])
                return 2
            if result.status == "timeout":
                return 3
            if result.status == "interrupted":
                console.print(f"[yellow]Job still running at {job_url}[/yellow]")
                return 0
            return 1

        # --- Phase 6: fetch summary ---
        console.rule("[bold]Phase 6 — fetch summary")
        summary_json = subprocess.run(
            ["hf", "buckets", "cp",
             f"hf://buckets/{bucket}/analytics/summary.json", "-"],
            capture_output=True, text=True, check=True,
        ).stdout
        summary = json.loads(summary_json)
        table = Table(title="analytics/summary.json")
        for k, v in summary.items():
            table.add_row(str(k), json.dumps(v, default=str)[:200])
        console.print(table)
        subprocess.run(["hf", "buckets", "list",
                        f"{bucket}/analytics", "-h", "-R"])
    else:
        console.print("[yellow]--skip-job: phases 4-6 skipped[/yellow]")

    # --- Phase 7: mutate + resync ---
    if not args.skip_mutate:
        console.rule("[bold]Phase 7 — mutate CSV + re-sync")
        original = Path("/tmp/original.csv")
        annotated = Path("/tmp/annotated.csv")
        subprocess.run(
            ["hf", "buckets", "cp",
             f"hf://buckets/{bucket}/dataset/{DATASET_CSV}", str(original)],
            check=True,
        )
        mutate_csv_add_grasp_score(str(original), str(annotated))
        full_bytes = annotated.stat().st_size
        elapsed_ms, new_bytes, _ = run_hf_cp_capture(
            str(annotated), f"hf://buckets/{bucket}/dataset/{DATASET_CSV}"
        )
        _print_bytes_panel(
            "Mutate + re-sync", full_bytes, new_bytes, elapsed_ms
        )
    else:
        console.print("[yellow]--skip-mutate: phase 7 skipped[/yellow]")

    console.rule("[bold green]Done")
    console.print(
        "Outputs:\n"
        f"  hf://buckets/{bucket}/dataset/         # ingested + annotated dataset\n"
        f"  hf://buckets/{bucket}/analytics/       # Job outputs\n"
        "To clean up: ./cleanup.sh"
    )
    return 0
```

- [ ] **Step 2: Smoke-test the `--skip-*` combined dry path (requires HF auth)**

```bash
cd ~/code/hf/demo-storage-buckets/jobs_demo_mount_nvidia_usd
uv run demo.py --skip-ingest --skip-job --skip-mutate
```

Expected output (tracing the rules, but not actually spending network/compute):
- "Phase 1 — preflight" with your user + bucket name
- "Phase 2 — ensure bucket" with bucket-ready line
- Yellow lines for skipped phases 3, 4-6, 7
- "Done" with outputs footer

- [ ] **Step 3: Commit**

```bash
git add jobs_demo_mount_nvidia_usd/demo.py
git commit -m "Wire demo.py main(): CLI + 7-phase orchestration with rich output"
```

---

## Task 10: TDD analytics helpers (`walk_file_sizes`, `aggregate_by_label`, `curate_grasp_ready`)

**Files:**
- Modify: `jobs_demo_mount_nvidia_usd/job/analytics.py`
- Create: `jobs_demo_mount_nvidia_usd/tests/test_analytics_helpers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_analytics_helpers.py`:

```python
import polars as pl
import analytics


FIXTURE = "tests/fixtures/tiny_metadata.csv"


def test_aggregate_by_label_returns_per_label_count():
    meta = pl.read_csv(FIXTURE)
    agg = analytics.aggregate_by_label(meta)
    labels = dict(zip(agg["label"].to_list(), agg["count"].to_list()))
    assert labels == {"book": 1, "mug": 1, "crate": 1, "paintbrush": 1, "warehouse": 1}


def test_aggregate_by_classification():
    meta = pl.read_csv(FIXTURE)
    agg = analytics.aggregate_by_classification(meta)
    # 3 in Prop general hand manipulation, 1 in Assembly, 1 in Scenario
    result = dict(zip(agg["classification"].to_list(), agg["count"].to_list()))
    assert result["Prop general hand manipulation"] == 3
    assert result["Assembly"] == 1
    assert result["Scenario"] == 1


def test_curate_grasp_ready_filters_by_mass_and_classification():
    meta = pl.read_csv(FIXTURE)
    curated = analytics.curate_grasp_ready(meta)
    names = curated["asset_name"].to_list()
    # mass ≤ 2kg AND classification == "Prop general hand manipulation"
    assert "sm_book_a" in names          # mass=0.4, correct class → yes
    assert "sm_mug_a" in names           # mass=0.3, correct class → yes
    assert "sm_brush_a" in names         # mass=0.05, correct class → yes
    assert "sm_crate_a" not in names     # mass=15, Assembly → no
    assert "sm_warehouse_a" not in names # null mass, Scenario → no
    assert len(curated) == 3


def test_walk_file_sizes_empty_dir_returns_empty_df(tmp_path):
    df = analytics.walk_file_sizes(str(tmp_path), "*.usd")
    assert df.height == 0
    assert set(df.columns) == {"relative_path", "size_bytes"}


def test_walk_file_sizes_finds_files(tmp_path):
    (tmp_path / "a.usd").write_bytes(b"x" * 100)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.usd").write_bytes(b"y" * 200)
    (tmp_path / "c.png").write_bytes(b"z" * 50)  # wrong extension
    df = analytics.walk_file_sizes(str(tmp_path), "*.usd").sort("relative_path")
    assert df["relative_path"].to_list() == ["a.usd", "sub/b.usd"]
    assert df["size_bytes"].to_list() == [100, 200]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/code/hf/demo-storage-buckets/jobs_demo_mount_nvidia_usd
uv run --with pytest --with polars --with pyarrow pytest tests/test_analytics_helpers.py -v
```

Expected: 5 failures, all `AttributeError: module 'analytics' has no attribute '<fn>'`.

- [ ] **Step 3: Implement the helpers in `analytics.py`**

Replace the stub body of `analytics.py` (keep the PEP 723 header and `main()` signature) with:

```python
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

import json
import os
from pathlib import Path

import polars as pl


def walk_file_sizes(root: str, pattern: str) -> pl.DataFrame:
    """Recursively walk `root` collecting relative paths matching `pattern`
    (e.g. `*.usd`) and their byte sizes. Returns a DataFrame with columns
    `relative_path` and `size_bytes`. Uses os.scandir for a metadata-only
    read pattern that's friendly to hf-mount."""
    root_path = Path(root)
    rows_path: list[str] = []
    rows_size: list[int] = []
    # Simple recursive scandir walker — avoids glob's pattern overhead and
    # gives us one scandir per directory (hf-mount readdir).
    from fnmatch import fnmatch
    stack = [root_path]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False) and fnmatch(entry.name, pattern):
                        rows_path.append(str(Path(entry.path).relative_to(root_path)))
                        rows_size.append(entry.stat().st_size)
        except (PermissionError, FileNotFoundError):
            continue
    return pl.DataFrame({"relative_path": rows_path, "size_bytes": rows_size})


def aggregate_by_label(meta: pl.DataFrame) -> pl.DataFrame:
    """Top labels by count, descending."""
    return (
        meta.group_by("label")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )


def aggregate_by_classification(meta: pl.DataFrame) -> pl.DataFrame:
    return (
        meta.group_by("classification")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )


def curate_grasp_ready(meta: pl.DataFrame, max_mass_kg: float = 2.0) -> pl.DataFrame:
    """Return the subset of assets suitable for graspable manipulation
    pre-training: mass ≤ max_mass_kg AND classification is the hand
    manipulation Prop class. Nulls in mass are excluded."""
    return meta.filter(
        pl.col("mass").is_not_null()
        & (pl.col("mass") <= max_mass_kg)
        & (pl.col("classification") == "Prop general hand manipulation")
    )


def main(workspace: str) -> int:
    workspace_path = Path(workspace)
    dataset = workspace_path / "dataset"
    csv = dataset / "physical_ai_simready_warehouse_01.csv"
    if not csv.exists():
        print(f"ERROR: dataset CSV not found at {csv} — run ingest phase first.",
              flush=True)
        return 1

    meta = pl.read_csv(str(csv))
    usd = walk_file_sizes(str(dataset / "Props"), "*.usd")
    png = walk_file_sizes(str(dataset / "computex_handmanip_renders"), "*.png")

    by_label = aggregate_by_label(meta).head(10)
    by_class = aggregate_by_classification(meta)
    mass_stats = meta["mass"].drop_nulls().describe()
    curated = curate_grasp_ready(meta)

    summary = {
        "n_assets": int(meta.height),
        "n_usd_files": int(usd.height),
        "n_thumbnails": int(png.height),
        "total_usd_bytes": int(usd["size_bytes"].sum()) if usd.height else 0,
        "total_thumbnail_bytes": int(png["size_bytes"].sum()) if png.height else 0,
        "top_labels": {r["label"]: r["count"] for r in by_label.iter_rows(named=True)},
        "by_classification": {r["classification"]: r["count"] for r in by_class.iter_rows(named=True)},
        "mass_stats": mass_stats.to_dicts(),
        "n_grasp_ready": int(curated.height),
        "xet_mount_note": f"dataset bytes were read via the bucket mount at {dataset}",
    }

    out = workspace_path / "analytics"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    # Full per-asset join (metadata + usd size + thumbnail size).
    joined = (
        meta.join(usd.rename({"size_bytes": "usd_size_bytes"}),
                  left_on="relative_path", right_on="relative_path", how="left")
            .join(png.rename({"size_bytes": "thumbnail_size_bytes",
                              "relative_path": "thumbnail_path"}),
                  on="thumbnail_path", how="left")
    )
    joined.write_parquet(str(out / "assets_by_category.parquet"))
    curated.write_parquet(str(out / "training_manifest.parquet"))

    print(f"wrote {out}/summary.json")
    print(f"wrote {out}/assets_by_category.parquet ({joined.height} rows)")
    print(f"wrote {out}/training_manifest.parquet ({curated.height} rows)")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1]))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --with pytest --with polars --with pyarrow pytest tests/test_analytics_helpers.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add jobs_demo_mount_nvidia_usd/job/analytics.py jobs_demo_mount_nvidia_usd/tests/test_analytics_helpers.py
git commit -m "Wire analytics.py: walk_file_sizes, aggregates, curate + main"
```

---

## Task 11: Write `jobs_demo_mount_nvidia_usd/README.md`

**Files:**
- Create: `jobs_demo_mount_nvidia_usd/README.md`

- [ ] **Step 1: Write the README**

```markdown
# jobs_demo_mount_nvidia_usd

End-to-end demo of Hugging Face Storage Buckets + `hf-mount` + HF Jobs for
a Cosmos-style pre-training data workflow.

## What it does

1. **Preflight.** Verify `hf` auth and pick a bucket name (default
   `<user>/nvidia-simready`).
2. **Ensure bucket.** Idempotent `hf buckets create --private`.
3. **Ingest.** `hf buckets cp hf://datasets/nvidia/PhysicalAI-SimReady-Warehouse-01 → bucket/dataset/`.
   Measures bytes transferred — expected to be near-zero (Xet chunks already
   in CAS), answering the pre-training dedupe question.
4. **Submit Job.** `hf jobs uv run --detach --flavor cpu-basic -v hf://buckets/.../:/workspace job/analytics.py /workspace`.
   Prints the Job URL so you can watch it in a browser.
5. **Poll.** Every 3 s, `hf jobs inspect <job_id>`. Breaks on
   succeeded/failed/cancelled/timeout. Ctrl-C leaves the Job running.
6. **Fetch summary.** Pretty-prints `analytics/summary.json`.
7. **Mutate + re-sync.** Download the dataset's CSV, add a
   `grasp_score = 1 / (1 + mass)` column, upload it back. Measures bytes —
   demonstrates Xet chunk-level dedupe (original 8 columns recognized as
   unchanged, only the 9th column's bytes transfer).

## Prerequisites

```bash
curl -LsSf https://hf.co/cli/install.sh | bash   # hf CLI ≥ 1.11
curl -fsSL https://raw.githubusercontent.com/huggingface/hf-mount/main/install.sh | sh
hf auth login                                     # or export HF_TOKEN=hf_...
curl -LsSf https://astral.sh/uv/install.sh | sh   # uv
```

## Run it

```bash
uv run demo.py
```

Or with a specific bucket name:

```bash
uv run demo.py --bucket my-org/cosmos-simready
```

Partial re-runs:

```bash
uv run demo.py --skip-ingest            # dataset already in bucket
uv run demo.py --skip-job               # skip Job; just ingest + mutate
uv run demo.py --skip-mutate            # skip the curation/resync beat
```

## Tests

```bash
uv run --with pytest --with polars --with pyarrow pytest tests/ -v
```

Fast (<5 s), no network. Covers the bytes parser, poll-loop state machine,
CSV mutation, polars aggregation, and filesystem walk.

## Clean up

```bash
./cleanup.sh
```
```

- [ ] **Step 2: Commit**

```bash
git add jobs_demo_mount_nvidia_usd/README.md
git commit -m "Add README for jobs_demo_mount_nvidia_usd"
```

---

## Task 12: Write `cleanup.sh`

**Files:**
- Create: `jobs_demo_mount_nvidia_usd/cleanup.sh`

- [ ] **Step 1: Write cleanup.sh**

```bash
#!/bin/bash
set -euo pipefail
#
# Idempotent cleanup for jobs_demo_mount_nvidia_usd.
# Deletes the demo bucket and local temp files.
#

BUCKET="${1:-$(hf auth whoami | head -1)/nvidia-simready}"

echo ">>> Deleting bucket $BUCKET (if exists)"
hf buckets delete "$BUCKET" --yes 2>/dev/null || echo "    (bucket did not exist)"

echo ">>> Removing local temp files"
rm -f /tmp/original.csv /tmp/annotated.csv

echo "Done."
```

- [ ] **Step 2: Make it executable and commit**

```bash
chmod +x jobs_demo_mount_nvidia_usd/cleanup.sh
git add jobs_demo_mount_nvidia_usd/cleanup.sh
git commit -m "Add cleanup.sh for jobs_demo_mount_nvidia_usd"
```

---

## Task 13: End-to-end smoke test

**Files:** (none modified — verification only)

- [ ] **Step 1: Run all tests**

```bash
cd ~/code/hf/demo-storage-buckets/jobs_demo_mount_nvidia_usd
uv run --with pytest --with polars --with pyarrow pytest tests/ -v
```

Expected: all tests (from Tasks 4, 5, 6, 7, 10) pass — ≥10 passed, 0 failed.

- [ ] **Step 2: Dry-run (no network, verifies CLI plumbing)**

```bash
uv run demo.py --skip-ingest --skip-job --skip-mutate
```

Expected: preflight + ensure-bucket run, three yellow "skipped" lines, done footer. Exit 0.

- [ ] **Step 3: Full end-to-end against a real throwaway bucket**

```bash
uv run demo.py --bucket $(hf auth whoami | head -1)/nvidia-simready-smoke
```

Expected flow, timings are illustrative:
- Phase 1–2 finishes in <5 s.
- Phase 3 (ingest 14.4 GB dataset → bucket): prints a dedup panel showing ≪14.4 GB transferred (Xet→Xet should be near-zero).
- Phase 4 prints job URL immediately; Phase 5 polls with visible progress; typical Job runtime <3 min on cpu-basic.
- Phase 6 prints `summary.json` table with ~753 assets, top 10 labels, classifications.
- Phase 7 prints a mutate-resync panel with full_bytes ≈ 200 KB and transferred bytes ≪ full_bytes.
- Done.

If any phase fails, inspect its output, adjust, then run `cleanup.sh` and re-run.

- [ ] **Step 4: Commit tests-passing status (no code changes, informational)**

If anything needed adjustment during E2E (CLI output parsing shape drift, etc.), commit those adjustments. Otherwise the smoke test is verification-only — nothing new to commit here.

---

## Self-Review

**Spec coverage:**
- §Repo layout → Tasks 1, 2, 3 ✓
- §Phase 1 preflight → Task 8 (`hf_whoami`), Task 9 (wiring) ✓
- §Phase 2 bucket → Task 8 (`ensure_bucket`), Task 9 ✓
- ~~§Phase 3 Upload code~~ — dropped; `hf jobs uv run` handles script delivery directly (noted in plan header)
- §Phase 4 ingest + measure → Task 4 (`parse_new_data_bytes`), Task 8 (`run_hf_cp_capture`), Task 9 ✓
- §Phase 5 submit Job → Task 5 (`build_job_url`), Task 8 (`submit_job`), Task 9 ✓
- §Phase 6 poll → Task 6 (`poll_job`), Task 8 (`inspect_job_status`), Task 9 ✓
- §Phase 7 fetch summary → Task 9 (inline) ✓
- §Phase 8 mutate + resync → Task 7 (`mutate_csv_add_grasp_score`), Task 9 ✓
- §Phase 9 done → Task 9 footer ✓
- §Job payload `analytics.py` → Task 10 ✓
- §uv + deps (PEP 723) → Task 3 (stubs), Task 9 (demo.py), Task 10 (analytics.py) ✓
- §Error handling → Task 9 (status-to-exit-code mapping) ✓
- §Testing strategy (4 categories) → Tests in Tasks 4, 6, 7, 10 + smoke in Task 13 ✓
- §Open questions — resolved: `hf jobs uv run` confirmed (used); image baseline — HF default uv image (no `--image` flag) ✓

**Placeholder scan:** No TBDs, TODOs, or "add appropriate error handling" lines. Task 8 Step 2 flags a verification check against the real CLI for the `hf jobs inspect` JSON shape — this is an explicit check with a fallback plan, not a placeholder.

**Type consistency:**
- `parse_new_data_bytes` signature consistent across Tasks 4, 8, 9 ✓
- `poll_job(job_id, poll_interval, timeout, inspector)` → `JobResult(status, elapsed_s)` consistent Tasks 6, 9 ✓
- `mutate_csv_add_grasp_score(src_csv, dst_csv)` consistent Tasks 7, 9 ✓
- `submit_job(script_path, bucket, flavor)` → `str` (job_id) consistent Tasks 8, 9 ✓
- `inspect_job_status(job_id)` → `str` (lowercase stage) consistent with `poll_job`'s `inspector` contract ✓
- `walk_file_sizes(root, pattern)` → DataFrame with `{relative_path, size_bytes}` — tested in Task 10, used in `main()` of Task 10 ✓
- `aggregate_by_label` / `aggregate_by_classification` / `curate_grasp_ready` signatures consistent Task 10 ✓
