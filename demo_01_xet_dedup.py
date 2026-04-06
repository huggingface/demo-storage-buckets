#!/usr/bin/env python3
"""
Demo 1: Dedup Efficiency — Incremental Checkpoint Saves

Talking points:
  - Traditional storage: every checkpoint save re-uploads the FULL model
  - Xet chunk-level dedup: only changed bytes get uploaded
  - For a 1 GB model where 10% of layers change per checkpoint,
    you upload ~100 MB instead of 1 GB — 10x savings
  - This compounds: 50 checkpoints × 1 GB = 50 GB transferred (traditional)
    vs. 1 GB + 49 × 100 MB ≈ 6 GB (Xet) — 8x less bandwidth

This script simulates a training run that saves checkpoints where most
of the model weights are frozen (common in fine-tuning / RL from human
feedback / physical AI policy training).
"""

import os
import random
import sys
import time
import struct
import tempfile
import subprocess

BUCKET = "rajatarya/nvidia-demo-dedup"
CHECKPOINT_SIZE_MB = 256  # large enough for visible upload time difference
NUM_CHECKPOINTS = 4
CHANGE_FRACTION = 0.10  # 10% of weights change per step

# Progress bar config
BAR_WIDTH = 40


def generate_checkpoint(path: str, size_mb: int, seed: int = 0):
    """Generate a deterministic binary file simulating model weights."""
    import hashlib
    chunk_size = 64 * 1024  # 64 KB — matches Xet chunk size
    num_chunks = (size_mb * 1024 * 1024) // chunk_size

    with open(path, "wb") as f:
        for i in range(num_chunks):
            h = hashlib.sha256(struct.pack(">II", seed, i)).digest()
            f.write(h * (chunk_size // len(h)))


def mutate_checkpoint(path: str, change_fraction: float, new_seed: int):
    """Mutate a fraction of the checkpoint to simulate weight updates."""
    import hashlib
    chunk_size = 64 * 1024
    data = bytearray(open(path, "rb").read())
    num_chunks = len(data) // chunk_size
    num_changed = max(1, int(num_chunks * change_fraction))

    for i in range(num_chunks - num_changed, num_chunks):
        offset = i * chunk_size
        h = hashlib.sha256(struct.pack(">II", new_seed, i)).digest()
        data[offset : offset + chunk_size] = h * (chunk_size // len(h))

    with open(path, "wb") as f:
        f.write(data)


def parse_new_data_bytes(output: str) -> int:
    """Parse the 'New Data Upload' line to get actual bytes transferred."""
    import re
    # Match lines like: "New Data Upload  : 100%|...|  1.05MB / 1.05MB"
    # or "New Data Upload  : |...|  0.00B / 0.00B"
    # We want the second value (total new data) from the last such line.
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    last_match = None
    for line in output.split("\n"):
        if "New Data Upload" not in line:
            continue
        # Find patterns like "1.05MB" or "0.00B" — grab the "X / Y" part
        m = re.search(r'([\d.]+)([KMGT]?B)\s*/\s*([\d.]+)([KMGT]?B)', line)
        if m:
            last_match = m
    if last_match:
        val = float(last_match.group(3))
        unit = last_match.group(4)
        return int(val * units.get(unit, 1))
    return -1  # unknown


def upload(local_path: str, remote_path: str) -> tuple[float, int]:
    """Upload a file, showing real hf CLI output. Returns (elapsed_seconds, new_bytes_uploaded)."""
    import tempfile as _tf
    cmd = f'hf buckets cp {local_path} {remote_path}'
    print(f"  $ {cmd}")

    # Let stderr (progress bars) display to terminal AND capture to a file for parsing
    stderr_log = _tf.NamedTemporaryFile(mode='w+', suffix='.log', delete=False)
    t0 = time.time()
    proc = subprocess.Popen(
        f'{cmd} 2> >(tee {stderr_log.name} >&2)',
        shell=True, executable='/bin/bash',
        stdout=None, stderr=None,  # inherit terminal
    )
    proc.wait()
    elapsed = time.time() - t0

    if proc.returncode != 0:
        sys.exit(1)

    # Parse new data bytes from captured stderr
    stderr_log.seek(0)
    stderr_text = open(stderr_log.name).read()
    os.unlink(stderr_log.name)
    new_bytes = parse_new_data_bytes(stderr_text)
    return elapsed, new_bytes


def run(cmd: str):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        sys.exit(1)


def main():
    print("=" * 55)
    print("  Demo 1: Chunk-Level Dedup for Checkpoints")
    print("=" * 55)
    print()
    print(f"  Model size:    {CHECKPOINT_SIZE_MB} MB")
    print(f"  Checkpoints:   {NUM_CHECKPOINTS}")
    print(f"  Changed/step:  {CHANGE_FRACTION*100:.0f}% of weights")
    print()

    # Random seed per run so global dedup doesn't mask the demo
    run_seed = random.randint(0, 2**31)
    print(f"  Run seed:      {run_seed}")
    print()

    # Create bucket
    run(f'hf buckets create {BUCKET} --private 2>/dev/null || true')
    print()

    results = []  # list of (elapsed, new_bytes)

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt_path = os.path.join(tmpdir, "checkpoint.safetensors")

        for step in range(NUM_CHECKPOINTS):
            print(f"--- Checkpoint step {step} ---")

            if step == 0:
                print(f"  Generating initial {CHECKPOINT_SIZE_MB} MB checkpoint...")
                generate_checkpoint(ckpt_path, CHECKPOINT_SIZE_MB, seed=run_seed)
            else:
                changed_mb = CHECKPOINT_SIZE_MB * CHANGE_FRACTION
                print(f"  Mutating {changed_mb:.0f} MB ({CHANGE_FRACTION*100:.0f}% of weights)...")
                mutate_checkpoint(ckpt_path, CHANGE_FRACTION, new_seed=run_seed + step)

            elapsed, new_bytes = upload(
                ckpt_path,
                f'hf://buckets/{BUCKET}/checkpoints/step_{step:04d}.safetensors'
            )
            results.append((elapsed, new_bytes))
            print()

    # Summary
    file_bytes = CHECKPOINT_SIZE_MB * 1024 * 1024
    print("=" * 55)
    print("  Results")
    print("=" * 55)
    print()

    # Show what's in the bucket
    run(f'hf buckets list {BUCKET}/checkpoints -h')
    print()

    # Transfer comparison
    max_bytes = max(b for _, b in results if b >= 0) if any(b >= 0 for _, b in results) else file_bytes
    print("  Data transferred per checkpoint:")
    total_new = 0
    for i, (t, new_bytes) in enumerate(results):
        if new_bytes >= 0:
            new_mb = new_bytes / (1024 * 1024)
            total_new += new_bytes
            bar_len = max(1, int(BAR_WIDTH * new_bytes / max_bytes)) if max_bytes > 0 else 1
            bar = "█" * bar_len
            pct = (new_bytes / file_bytes) * 100 if file_bytes > 0 else 0
            label = "full upload" if i == 0 else "dedup"
            print(f"    Step {i}: {bar:<{BAR_WIDTH}} {new_mb:>7.1f} MB  ({pct:.0f}% of file)  {t:.1f}s  [{label}]")
        else:
            print(f"    Step {i}: {'?' * 5:<{BAR_WIDTH}} ?.? MB  {t:.1f}s")
    print()

    # Speedup
    if len(results) > 1 and results[0][0] > 0:
        avg_dedup_time = sum(t for t, _ in results[1:]) / len(results[1:])
        if avg_dedup_time > 0:
            speedup = results[0][0] / avg_dedup_time
            print(f"  Dedup uploads are ~{speedup:.1f}x faster than the initial upload")
            print()

    # Bandwidth summary
    traditional_total = NUM_CHECKPOINTS * file_bytes
    traditional_mb = traditional_total / (1024 * 1024)
    actual_mb = total_new / (1024 * 1024)
    if total_new > 0:
        saved_pct = (1 - total_new / traditional_total) * 100
        print(f"  Without dedup: {NUM_CHECKPOINTS} × {CHECKPOINT_SIZE_MB} MB = {traditional_mb:.0f} MB transferred")
        print(f"  With Xet:      {actual_mb:.0f} MB actually transferred")
        print(f"  Saved:         {saved_pct:.0f}% bandwidth")
    print()
    print("  At scale: 50 checkpoints x 10 GB model")
    print("                          Traditional Transfer = 500 GB")
    print("                          Xet dedup = ~59 GB - 8.5x savings")


if __name__ == "__main__":
    main()
