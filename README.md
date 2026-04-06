# Storage Buckets Demo — NVIDIA Physical AI Meeting

Live demo scripts for the NVIDIA meeting (Apr 7, 2026).
See `TALK_TRACK.md` for the full talk track with transitions.

## Prerequisites

```bash
pip install huggingface_hub hf_xet
hf login  # or export HF_TOKEN=hf_...
```

## Demo Flow (Rajat's 20 min)

| Order | Script | Slide | Duration |
|-------|--------|-------|----------|
| 1 | `demo_01_xet_dedup.py` | Xet: The Storage Backend | ~5 min |
| 2 | `demo_02_bucket_basics.sh` | Storage Buckets | ~3 min |
| 3 | `demo_03_hf_mount.sh` | hf-mount: Filesystem Access | ~3 min |

Backup demos (for Q&A):

| # | Script | Topic |
|---|--------|-------|
| 4 | `demo_04_dataset_sync.sh` | Incremental sync for growing datasets |
| 5 | `demo_05_cdn_prewarm.sh` | CDN pre-warming (talk track only) |

### Pre-demo setup (run before the meeting)

```bash
# 1. Configure scripts with your HF username
./prep.sh

# 2. Clean up any buckets from a previous run
./cleanup.sh

# 3. Verify
hf auth whoami
grep BUCKET demo_01_xet_dedup.py  # should show your username
```

## Cleanup

```bash
./cleanup.sh
```
