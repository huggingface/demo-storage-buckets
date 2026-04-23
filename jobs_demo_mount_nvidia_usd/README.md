# jobs_demo_mount_nvidia_usd

Pre-training data workflow for [`nvidia/PhysicalAI-SimReady-Warehouse-01`](https://huggingface.co/datasets/nvidia/PhysicalAI-SimReady-Warehouse-01) using HF Storage Buckets, `hf-mount`, and HF Jobs.

## Flow

1. **Ingest** — `hf buckets cp` the dataset into your bucket. Near-zero byte transfer (Xet dedupe).
2. **Analyze** — HF Job mounts the bucket rw, runs polars over the CSV + USD + PNG files, writes `analytics/` back.
3. **Mutate** — add a `grasp_score` column to the CSV and re-sync. Only delta bytes transfer.

## Prereqs

```bash
curl -LsSf https://hf.co/cli/install.sh | bash   # hf CLI >= 1.11
curl -LsSf https://astral.sh/uv/install.sh | sh  # uv
hf auth login                                     # or export HF_TOKEN=hf_...
```

## Run

```bash
uv run demo.py
```

Options:

```bash
uv run demo.py --bucket my-org/cosmos-simready   # override bucket
uv run demo.py --dataset org/other-dataset       # override dataset repo
uv run demo.py --skip-ingest                      # dataset already in bucket
uv run demo.py --skip-job                         # skip Job phase
uv run demo.py --skip-mutate                      # skip mutation beat
```

## Tests

```bash
uv run --with pytest --with polars --with pyarrow pytest tests/ -v
```

## Clean up

```bash
./cleanup.sh
```
