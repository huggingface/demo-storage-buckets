# jobs_demo_mount_nvidia_usd — Design

**Date:** 2026-04-22
**Author:** Rajat Arya (HF)
**Audience:** NVIDIA researchers / POC engagement (via the `C098J1ZBGKY` Slack thread from 2026-04-09)
**Status:** proposed — pending implementation plan

## Goal

Build a self-contained, reproducible demo that shows NVIDIA how Hugging Face
Storage Buckets + `hf-mount` together support a Cosmos-style pre-training data
workflow:

1. Ingest the `nvidia/PhysicalAI-SimReady-Warehouse-01` dataset into a user-owned
   Storage Bucket with near-zero byte transfer (Xet-to-Xet chunk dedupe).
2. Launch a CPU-only HF Job that mounts the bucket read-write, runs polars
   analytics over the mounted dataset's CSV + USD + PNG files, and writes
   curation artifacts back into the same bucket.
3. Mutate the dataset's metadata (add a Cosmos-graspability column) and re-sync
   it, showing that Xet only uploads the delta bytes.

The demo is handed off to NVIDIA as a `uv` one-liner: `uv run demo.py`. It must
be idempotent and runnable without any prior setup beyond an HF token and the
`hf` + `hf-mount` CLIs.

## Non-goals

- No real Cosmos training (no GPU, no model weights).
- No mid- or post-training dedupe measurement — `basic_demo/demo_01_xet_dedup.py`
  already covers checkpoint saves. This demo is strictly pre-training / data
  side.
- No changes to the existing `basic_demo/` scripts beyond moving them into the
  `basic_demo/` subdirectory unchanged.
- No new CLI wrapper; reuse `hf` and `hf buckets` subcommands directly.

## Repository layout

```
demo-storage-buckets/
├── README.md                         # top-level: links both demos
├── basic_demo/                       # existing demos moved here, unchanged
│   ├── README.md
│   ├── TALK_TRACK.md
│   ├── demo_01_xet_dedup.py
│   ├── demo_02_bucket_basics.sh
│   ├── demo_03_hf_mount.sh
│   ├── demo_04_dataset_sync.sh
│   ├── prep.sh
│   ├── cleanup.sh
│   └── *.pdf
└── jobs_demo_mount_nvidia_usd/
    ├── README.md                     # setup + how to run + what it shows
    ├── demo.py                       # uv PEP 723 script, entry point
    ├── job/
    │   └── analytics.py              # uv PEP 723 script, runs inside the Job
    └── cleanup.sh                    # deletes bucket + local /tmp files
```

All existing files move verbatim into `basic_demo/`. `basic_demo/README.md` and
`basic_demo/TALK_TRACK.md` stay as they were — they reference bucket names
(`rajatarya/nvidia-demo-*`), not relative paths, so nothing breaks.

## End-to-end flow

```
Phase 1. Preflight         hf auth whoami, hf CLI version ≥ 1.10, hf jobs help,
                           default bucket name = "{user}/nvidia-simready"
Phase 2. Bucket            hf buckets create {bucket} --private || true
Phase 3. Upload code       hf buckets cp ./job/analytics.py → bucket/code/
Phase 4. Ingest + measure  hf buckets cp hf://datasets/nvidia/PhysicalAI-SimReady-Warehouse-01
                                           → hf://buckets/{bucket}/dataset/
                           parse "New Data Upload" stderr → bytes_transferred
                           print: 14.4 GB nominal → bytes_transferred → dedup %
Phase 5. Submit Job        hf jobs run --detach --flavor cpu-basic
                                       --volume hf://buckets/{bucket}:/workspace
                                       <uv-image>
                                       bash -c "cd /workspace &&
                                         uv run --with polars,pyarrow,rich
                                         /workspace/code/analytics.py /workspace"
                           capture job_id, build job_url
                           print job_url up-front so user can open in browser
Phase 6. Poll              every 3s, `hf jobs inspect <job_id>` (JSON)
                           ├─ pending/running: print progress dots; every 30s
                           │   print a heartbeat with elapsed time + job_url
                           ├─ succeeded: break, proceed to Phase 7
                           ├─ failed/cancelled: print last 30 `hf jobs logs` lines
                           │   + job_url, exit 2
                           └─ elapsed > 15 min: print job_url, exit 3
                           ctrl-C: print "Job still running at {job_url}", exit 0
Phase 7. Fetch summary     hf buckets cp bucket/analytics/summary.json -
                           pretty-print JSON via rich
                           hf buckets list bucket/analytics -h -R (shows artifacts)
Phase 8. Mutate + re-sync  hf buckets cp bucket/dataset/..._warehouse_01.csv → /tmp/original.csv
                           polars: add grasp_score = 1/(1 + mass.fill_null(1.0))
                           write /tmp/annotated.csv
                           hf buckets cp /tmp/annotated.csv
                                           → bucket/dataset/..._warehouse_01.csv
                           parse "New Data Upload" → delta_bytes
                           print full_size, delta_bytes, savings %
Phase 9. Done              print a "next steps" footer: where outputs live, how
                           to rerun, how to clean up
```

### Job payload — `job/analytics.py`

PEP 723 single-file script. Declares `polars`, `pyarrow`, `rich` inline so
`uv run --with ...` in the Job container picks them up with no pyproject.toml.

Takes one positional arg: workspace root (bucket mount point, `/workspace`).

```
Phase A. Discover           csv  = workspace/dataset/physical_ai_simready_warehouse_01.csv
                           root = workspace/dataset/
                           assert csv exists (fail fast with helpful message)
Phase B. Read CSV          meta = polars.read_csv(csv)            # 753 rows × 8 cols
Phase C. Stat files         os.scandir walk of root/Props/**/*.usd → usd_df
                           os.scandir walk of root/computex_handmanip_renders/*.png → png_df
                           (each scandir stat() is a lazy mount read — exercises
                            hf-mount's metadata-only fast path)
Phase D. Join              joined = meta.join(usd_df, on=relative_path)
                                         .join(png_df, on=thumbnail_path)
Phase E. Aggregate         top_labels = meta.group_by("label").count().sort().head(10)
                           by_classification = meta.group_by("classification").count()
                           mass_stats = meta["mass"].drop_nulls().describe() (p50/p90/p99)
                           size_stats = joined["usd_size_bytes", "thumbnail_size_bytes"].describe()
Phase F. Curate            grasp = joined.filter(
                             (pl.col("mass") <= 2.0) &
                             (pl.col("classification") == "Prop general hand manipulation"))
                           select asset_name, relative_path, label, q_code, mass,
                                   usd_size_bytes, thumbnail_size_bytes
Phase G. Write              workspace/analytics/summary.json        (aggregates + counts)
                           workspace/analytics/assets_by_category.parquet
                           workspace/analytics/training_manifest.parquet (curated subset)
                           rich-print the top labels + counts to stdout (→ Job logs)
```

### `demo.py` — CLI surface

```
uv run demo.py [--bucket NAME] [--poll-interval SECS] [--job-timeout SECS]
               [--skip-ingest] [--skip-job] [--skip-mutate]

  --bucket NAME        default: "{hf whoami}/nvidia-simready"
  --poll-interval 3    seconds between `hf jobs inspect` calls
  --job-timeout 900    max seconds to wait for Job (default: 15 min)
  --skip-ingest        skip Phase 4 (useful when re-running)
  --skip-job           skip Phase 5–7
  --skip-mutate        skip Phase 8
```

Phase 2 (bucket create) always runs — `hf buckets create ... || true` is
idempotent, no flag needed. Skip-flags exist so NVIDIA can repeat partial
runs cheaply (e.g., `--skip-ingest` after the dataset is already in their
bucket).

### `uv` + deps

- `demo.py` declares inline (PEP 723):
  ```python
  # /// script
  # requires-python = ">=3.11"
  # dependencies = ["huggingface_hub>=1.10", "rich>=13"]
  # ///
  ```
  Runs as `uv run demo.py` with zero setup.
- `job/analytics.py` declares inline:
  ```python
  # /// script
  # requires-python = ">=3.11"
  # dependencies = ["polars>=1.0", "pyarrow>=15", "rich>=13"]
  # ///
  ```
  The Job container uses the public `ghcr.io/astral-sh/uv:python3.12-bookworm`
  image. `uv run /workspace/code/analytics.py /workspace` picks up the inline
  deps. No image build, no pyproject.toml.

### Code delivery into the Job

Bucket-as-workspace: `demo.py` uploads `job/analytics.py` to `bucket/code/`
before submitting the Job (Phase 3). The Job mounts the bucket rw at
`/workspace` and runs `uv run /workspace/code/analytics.py /workspace`. One
mount covers code, inputs, and outputs — no image rebuild, no git clone.

## Implementation notes

### HF Jobs CLI unknowns to verify

The CLI subcommands `hf jobs run --detach`, `hf jobs inspect`, `hf jobs logs`
are assumed to exist but must be verified against the installed `hf` version
(≥ 1.10) at the start of implementation. If `--detach` or `inspect` differ,
the poller adapts to whatever `hf jobs` exposes (e.g., a JSON status endpoint
via `huggingface_hub.jobs` Python API). The spec does not pin the exact CLI
form — the implementation plan will confirm and document the real commands.

### Bytes-transferred parsing

`demo.py` reuses the `parse_new_data_bytes()` pattern from
`basic_demo/demo_01_xet_dedup.py:64`: run `hf buckets cp ...` with stderr
tee'd to a temp file, then regex the "New Data Upload  : ... X MB / Y MB"
line. The function is lifted with attribution in a comment — it's simple
enough to copy rather than factor into a shared helper (YAGNI, only 2 demos).

### Mutation that exercises Xet dedupe

The CSV is ~200 KB. Adding one float column adds ~10 KB of raw bytes but
shifts line endings, which breaks naive byte-for-byte dedupe. Xet's CDC
handles this: the first ~8 original columns still chunk the same way
(the column values are unchanged), and the new column bytes produce new
chunks. Expected transfer: on the order of the new column's bytes, not the
full file. The demo asserts `new_bytes < full_size * 0.5` as a smoke check
and prints whichever ratio it actually observes — conservatively framed as
"Xet transferred X KB of an X+Y KB file; traditional storage would re-upload
the full file."

### Output-free paths

If the Job failed, Phase 7–8 are skipped. Output artifacts from a prior run
(if bucket was not cleaned) remain in place; `demo.py` overwrites them on
success. No explicit "zero prior state" precondition — mutation is idempotent
since `grasp_score` is deterministic from `mass`.

## Testing strategy

The implementation plan will cover these tests, roughly in order of cost:

1. **Local dry-run mode** — `demo.py --skip-job` runs Phases 1–4 + 8 only; no
   Job launched. Smoke-tests the CLI plumbing, bucket creation, bytes parsing,
   and polars mutation without spending Job compute. Runs in <30s.
2. **Phase 6 poller unit test** — mock `hf jobs inspect` with a fixture stream
   (pending → running → succeeded), assert the poll loop transitions correctly
   and respects `--poll-interval`. Also test the failed and timeout branches.
3. **Analytics.py locally** — pointing `analytics.py` at a locally-mounted
   hf-mount of the dataset verifies the polars logic without Job submission.
   Validates `training_manifest.parquet` schema.
4. **End-to-end run against a throwaway bucket** — the integration smoke-test.
   Run `uv run demo.py --bucket rajatarya/nvidia-simready-test`, let it execute
   end to end, assert final summary bytes + presence of all 3 analytics
   artifacts.

Test 4 is the only one that costs compute; 1–3 are free and should be the
default pre-commit check.

## Open questions

None blocking. Two implementation-time confirmations:
- The exact `hf jobs` CLI verbs and their JSON output shape.
- Whether the `ghcr.io/astral-sh/uv:python3.12-bookworm` image is the right
  baseline or whether HF Jobs provides a preferred uv-bearing image.

Both resolved during implementation; neither changes the design.

## References

- Slack thread that motivated this demo:
  https://huggingface.slack.com/archives/C098J1ZBGKY/p1775769570325329
- Dataset: https://huggingface.co/datasets/nvidia/PhysicalAI-SimReady-Warehouse-01
- Existing `basic_demo/` for pattern consistency (especially
  `demo_01_xet_dedup.py` for bytes-parsing and `demo_03_hf_mount.sh` for
  `hf jobs run --volume` syntax)
- `hf-mount` README: `~/code/hf/hf-mount/README.md`
