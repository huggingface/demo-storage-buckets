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
import sys
import time
import struct
import shutil
import tempfile
import subprocess

BUCKET = "rajatarya/nvidia-demo-dedup"
CHECKPOINT_SIZE_MB = 512  # large enough for visible upload time difference
NUM_CHECKPOINTS = 4
CHANGE_FRACTION = 0.10  # 10% of weights change per step

# Progress bar config
BAR_WIDTH = 40


def progress_bar(current: int, total: int, prefix: str = "", suffix: str = "", elapsed: float = 0):
    """Render a progress bar to stderr."""
    frac = current / total if total > 0 else 1.0
    filled = int(BAR_WIDTH * frac)
    bar = "█" * filled + "░" * (BAR_WIDTH - filled)
    pct = frac * 100
    mb_done = current / (1024 * 1024)
    mb_total = total / (1024 * 1024)
    speed = mb_done / elapsed if elapsed > 0 else 0
    sys.stderr.write(f"\r  {prefix} |{bar}| {pct:5.1f}%  {mb_done:.0f}/{mb_total:.0f} MB  {speed:.0f} MB/s {suffix}")
    sys.stderr.flush()
    if current >= total:
        sys.stderr.write("\n")


def generate_checkpoint(path: str, size_mb: int, seed: int = 0):
    """Generate a deterministic binary file simulating model weights."""
    import hashlib
    chunk_size = 64 * 1024  # 64 KB — matches Xet chunk size
    num_chunks = (size_mb * 1024 * 1024) // chunk_size
    total_bytes = num_chunks * chunk_size
    t0 = time.time()

    with open(path, "wb") as f:
        for i in range(num_chunks):
            h = hashlib.sha256(struct.pack(">II", seed, i)).digest()
            f.write(h * (chunk_size // len(h)))
            if i % 128 == 0 or i == num_chunks - 1:
                progress_bar(f.tell(), total_bytes, prefix="Generating", elapsed=time.time() - t0)


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


def upload_with_progress(local_path: str, remote_path: str) -> float:
    """Upload a file, streaming hf output and showing a progress bar."""
    file_size = os.path.getsize(local_path)
    cmd = f'hf buckets cp {local_path} {remote_path}'
    print(f"    $ {cmd}")

    t0 = time.time()
    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    # Show a simple progress animation while upload runs
    spin = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while proc.poll() is None:
        elapsed = time.time() - t0
        sys.stderr.write(f"\r  {spin[i % len(spin)]} Uploading... {elapsed:.1f}s")
        sys.stderr.flush()
        time.sleep(0.1)
        i += 1

    elapsed = time.time() - t0
    rc = proc.returncode

    if rc != 0:
        output = proc.stdout.read() if proc.stdout else ""
        sys.stderr.write(f"\r  ERROR: upload failed (exit {rc})\n")
        print(f"    {output.strip()}")
        sys.exit(1)

    mb = file_size / (1024 * 1024)
    sys.stderr.write(f"\r  ✓ Uploaded {mb:.0f} MB in {elapsed:.1f}s" + " " * 20 + "\n")
    return elapsed


def run(cmd: str):
    print(f"    $ {cmd}")
    t = time.time()
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    elapsed = time.time() - t
    if result.returncode != 0:
        print(f"    ERROR: {result.stderr.strip()}")
        sys.exit(1)
    return elapsed


def main():
    print("=" * 55)
    print("  Demo 1: Chunk-Level Dedup for Checkpoints")
    print("=" * 55)
    print()
    print(f"  Model size:    {CHECKPOINT_SIZE_MB} MB")
    print(f"  Checkpoints:   {NUM_CHECKPOINTS}")
    print(f"  Changed/step:  {CHANGE_FRACTION*100:.0f}% of weights")
    print()

    # Create bucket
    run(f'hf buckets create {BUCKET} --private 2>/dev/null || true')
    print()

    upload_times = []

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt_path = os.path.join(tmpdir, "checkpoint.safetensors")

        for step in range(NUM_CHECKPOINTS):
            print(f"--- Checkpoint step {step} ---")

            if step == 0:
                print(f"  Generating initial {CHECKPOINT_SIZE_MB} MB checkpoint...")
                generate_checkpoint(ckpt_path, CHECKPOINT_SIZE_MB, seed=42)
            else:
                changed_mb = CHECKPOINT_SIZE_MB * CHANGE_FRACTION
                print(f"  Mutating {changed_mb:.0f} MB ({CHANGE_FRACTION*100:.0f}% of weights)...")
                mutate_checkpoint(ckpt_path, CHANGE_FRACTION, new_seed=42 + step)

            elapsed = upload_with_progress(
                ckpt_path,
                f'hf://buckets/{BUCKET}/checkpoints/step_{step:04d}.safetensors'
            )
            upload_times.append(elapsed)

            if step == 0:
                print(f"  → First upload: full {CHECKPOINT_SIZE_MB} MB transferred")
            else:
                print(f"  → Only ~{CHECKPOINT_SIZE_MB * CHANGE_FRACTION:.0f} MB "
                      f"transferred (dedup skips unchanged chunks)")
            print()

    # Summary
    print("=" * 55)
    print("  Results")
    print("=" * 55)
    print()

    # Show what's in the bucket
    run(f'hf buckets list {BUCKET}/checkpoints -h')
    print()

    # Timing comparison
    print("  Upload times:")
    for i, t in enumerate(upload_times):
        marker = "(full)" if i == 0 else "(dedup)"
        bar_len = int(BAR_WIDTH * t / max(upload_times))
        bar = "█" * bar_len
        print(f"    Step {i}: {bar} {t:.1f}s {marker}")
    print()

    if len(upload_times) > 1 and upload_times[0] > 0:
        speedup = upload_times[0] / (sum(upload_times[1:]) / len(upload_times[1:]))
        print(f"  Dedup uploads are ~{speedup:.1f}x faster than the initial upload")
        print()

    traditional_gb = NUM_CHECKPOINTS * CHECKPOINT_SIZE_MB / 1024
    dedup_gb = (CHECKPOINT_SIZE_MB + (NUM_CHECKPOINTS - 1) * CHECKPOINT_SIZE_MB * CHANGE_FRACTION) / 1024
    print(f"  Traditional: {NUM_CHECKPOINTS} × {CHECKPOINT_SIZE_MB} MB = {traditional_gb:.1f} GB transferred")
    print(f"  With dedup:  {dedup_gb:.2f} GB transferred ({dedup_gb/traditional_gb*100:.0f}%)")
    print(f"  Saved:       {(1 - dedup_gb/traditional_gb)*100:.0f}% bandwidth")
    print()
    print("  At scale: 50 checkpoints × 10 GB model = 500 GB (traditional)")
    print("            vs ~59 GB with Xet dedup — 8.5x savings")


if __name__ == "__main__":
    main()
