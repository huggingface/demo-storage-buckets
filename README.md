# demo-storage-buckets

Demos of Hugging Face Storage Buckets, Xet, `hf-mount`, and HF Jobs.

## [`basic_demo/`](./basic_demo/)

Checkpoint dedupe, bucket basics + CDN pre-warming, `hf-mount`, and dataset sync.
See [`basic_demo/TALK_TRACK.md`](./basic_demo/TALK_TRACK.md).

## [`jobs_demo_mount_nvidia_usd/`](./jobs_demo_mount_nvidia_usd/)

Pre-training data workflow for the NVIDIA `PhysicalAI-SimReady-Warehouse-01`
dataset: ingest into a bucket, run polars analytics in a mounted HF Job,
mutate the CSV and re-sync to show Xet dedupe.

```bash
uv run jobs_demo_mount_nvidia_usd/demo.py
```
