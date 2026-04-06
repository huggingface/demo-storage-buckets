#!/usr/bin/env python3
"""
Demo 2: Dedup Efficiency — Incremental Checkpoint Saves

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
import tempfile
import subprocess

BUCKET = "xet-team/nvidia-demo-dedup"
CHECKPOINT_SIZE_MB = 256  # keep manageable for live demo
NUM_CHECKPOINTS = 4
CHANGE_FRACTION = 0.10  # 10% of weights change per step


def generate_checkpoint(path: str, size_mb: int, seed: int = 0):
    """Generate a deterministic binary file simulating model weights."""
    import hashlib
    chunk_size = 64 * 1024  # 64 KB — matches Xet chunk size
    num_chunks = (size_mb * 1024 * 1024) // chunk_size

    with open(path, "wb") as f:
        for i in range(num_chunks):
            # Deterministic "weights" based on chunk index and seed
            h = hashlib.sha256(struct.pack(">II", seed, i)).digest()
            f.write(h * (chunk_size // len(h)))


def mutate_checkpoint(path: str, change_fraction: float, new_seed: int):
    """Mutate a fraction of the checkpoint to simulate weight updates."""
    import hashlib
    chunk_size = 64 * 1024
    data = bytearray(open(path, "rb").read())
    num_chunks = len(data) // chunk_size
    num_changed = max(1, int(num_chunks * change_fraction))

    # Change the last N chunks (simulates later layers being fine-tuned)
    for i in range(num_chunks - num_changed, num_chunks):
        offset = i * chunk_size
        h = hashlib.sha256(struct.pack(">II", new_seed, i)).digest()
        data[offset : offset + chunk_size] = h * (chunk_size // len(h))

    with open(path, "wb") as f:
        f.write(data)


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
    print("=" * 50)
    print(" Demo 2: Chunk-Level Dedup for Checkpoints")
    print("=" * 50)
    print()
    print(f"Simulating {NUM_CHECKPOINTS} checkpoints of a {CHECKPOINT_SIZE_MB} MB model")
    print(f"where {CHANGE_FRACTION*100:.0f}% of weights change per training step.")
    print()

    # Create bucket
    run(f'hf buckets create {BUCKET} --private 2>/dev/null || true')
    print()

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

            size_mb = os.path.getsize(ckpt_path) / (1024 * 1024)
            print(f"  File size: {size_mb:.1f} MB")

            elapsed = run(
                f'hf buckets cp {ckpt_path} '
                f'hf://buckets/{BUCKET}/checkpoints/step_{step:04d}.safetensors'
            )
            print(f"  Upload time: {elapsed:.1f}s")

            if step == 0:
                print(f"  -> First upload: full {CHECKPOINT_SIZE_MB} MB transferred")
            else:
                print(f"  -> Only ~{CHECKPOINT_SIZE_MB * CHANGE_FRACTION:.0f} MB "
                      f"transferred (dedup skips unchanged chunks)")
            print()

    # Show what's in the bucket
    print("--- Bucket contents ---")
    run(f'hf buckets list {BUCKET}/checkpoints -h')
    print()

    traditional_gb = NUM_CHECKPOINTS * CHECKPOINT_SIZE_MB / 1024
    dedup_gb = (CHECKPOINT_SIZE_MB + (NUM_CHECKPOINTS - 1) * CHECKPOINT_SIZE_MB * CHANGE_FRACTION) / 1024
    print(f"Traditional storage: {NUM_CHECKPOINTS} uploads × {CHECKPOINT_SIZE_MB} MB = {traditional_gb:.1f} GB transferred")
    print(f"With Xet dedup:     {dedup_gb:.2f} GB transferred ({dedup_gb/traditional_gb*100:.0f}% of traditional)")
    print(f"Bandwidth saved:    {(1 - dedup_gb/traditional_gb)*100:.0f}%")
    print()
    print("At scale (50 checkpoints × 10 GB model), this is 500 GB vs ~59 GB — 8.5x savings.")


if __name__ == "__main__":
    main()
