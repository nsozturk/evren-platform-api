# Uploading files

Uploading is a three-step flow per file: **presign**, **PUT**, **confirm**. A file that is not confirmed is not added to the dataset.

Base URL `https://api.ssyz.org.tr/api/v1`, header `X-API-Key: <evren_plt_ key>` on all three steps. You need the dataset `id` from [datasets.md](datasets.md).

## What you can upload

`GET /datasets/upload/extensions` returns `{extensions: [...], by_file_type: {image, video, audio, text, ...}}`. The accepted list includes `.parquet`, `.arrow`, `.feather`, `.sqlite`, `.db`, `.csv`, `.tsv`, `.json`, `.jsonl`, `.ndjson`, `.txt`, `.md`, `.pdf`, `.tar`, `.tgz`, `.tar.gz`, common image, audio and video formats, and `.dcm`.

**`.npy` is not accepted.** Convert NumPy arrays to Parquet first (see below).

## Step 1 - presign

`POST /datasets/{id}/upload/presign`

```json
{"files": [{"filename": "train-00000.parquet", "sha256_hash": "<hex>", "file_size": 82455248}]}
```

`client_uid` is an optional extra field on each file entry. Response:

```json
{
  "presigned_urls": [
    {"filename": "train-00000.parquet", "sha256_hash": "<hex>",
     "upload_url": "/datasets/<id>/upload/put?key=<object key>",
     "direct_upload_url": "...", "object_key": "<object key>"}
  ],
  "duplicates": ["<sha256 of files the dataset already has>"]
}
```

- `upload_url` is **relative**. Prefix it with the API base (`https://api.ssyz.org.tr/api/v1`).
- If the dataset already contains a file with the same SHA-256, that hash comes back in `duplicates` and you skip the file. This makes re-runs cheap and safe.

## Step 2 - PUT the bytes

`PUT <api base><upload_url>` with the raw file as the body, headers `X-API-Key` and `Content-Type: application/octet-stream`. Response: `{"ok": true, "key": "...", "size": N}`.

Stream the file from disk instead of reading it into memory.

## Step 3 - confirm

`POST /datasets/{id}/upload/confirm`

```json
{"items": [{"object_key": "<object key>", "sha256_hash": "<hex>", "filename": "train-00000.parquet", "file_size": 82455248}]}
```

Returns `201` with `{created, ids, actual_count, batch_duplicates}`.

## Size and sharding

Single files of 0.7 KB, 105 MB and 316 MB all uploaded fine, at roughly 8-11 MB/s from Türkiye. No per-file limit was hit up to 316 MB. This project shards at 280 MB or less so every file stays inside what was actually tested. Split large Parquet or JSONL files into numbered shards (`train-00000-of-00009.parquet`) before uploading.

## Example: curl

A complete single-file script lives in [`examples/curl-upload.sh`](../../examples/curl-upload.sh). The core calls:

```bash
API=https://api.ssyz.org.tr/api/v1
SHA=$(shasum -a 256 train-00000.parquet | cut -d' ' -f1)      # sha256sum on Linux
SIZE=$(wc -c < train-00000.parquet | tr -d ' ')

# 1) presign
curl -sS -X POST "$API/datasets/$DATASET_ID/upload/presign" \
  -H "X-API-Key: $EVREN_PLATFORM_KEY" -H "Content-Type: application/json" \
  -d "{\"files\":[{\"filename\":\"train-00000.parquet\",\"sha256_hash\":\"$SHA\",\"file_size\":$SIZE}]}"

# 2) PUT (use the relative upload_url from step 1; -T streams the file)
curl -sS -T train-00000.parquet "$API<upload_url>" \
  -H "X-API-Key: $EVREN_PLATFORM_KEY" -H "Content-Type: application/octet-stream"

# 3) confirm
curl -sS -X POST "$API/datasets/$DATASET_ID/upload/confirm" \
  -H "X-API-Key: $EVREN_PLATFORM_KEY" -H "Content-Type: application/json" \
  -d "{\"items\":[{\"object_key\":\"<object_key>\",\"sha256_hash\":\"$SHA\",\"filename\":\"train-00000.parquet\",\"file_size\":$SIZE}]}"
```

## Example: Python standard library

```python
import hashlib, json, os, urllib.request

API = "https://api.ssyz.org.tr/api/v1"
KEY = os.environ["EVREN_PLATFORM_KEY"]


def call(method, path, body=None, stream=None, size=None):
    headers = {"X-API-Key": KEY}
    data = None
    if stream is not None:                      # open file object: streamed, not read into memory
        data = stream
        headers.update({"Content-Type": "application/octet-stream", "Content-Length": str(size)})
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=1800) as r:
        raw = r.read()
        return json.loads(raw) if raw.strip() else {}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def upload(dataset_id, path):
    name, size, sha = os.path.basename(path), os.path.getsize(path), sha256(path)
    pre = call("POST", f"/datasets/{dataset_id}/upload/presign",
               {"files": [{"filename": name, "sha256_hash": sha, "file_size": size}]})
    if sha in (pre.get("duplicates") or []):
        return "duplicate, skipped"
    u = pre["presigned_urls"][0]
    with open(path, "rb") as f:
        call("PUT", u["upload_url"], stream=f, size=size)
    return call("POST", f"/datasets/{dataset_id}/upload/confirm",
                {"items": [{"object_key": u["object_key"], "sha256_hash": sha, "filename": name, "file_size": size}]})
```

This sketch has no retries or journal. For real jobs use [`tools/evren_dataset_upload.py`](../../tools/evren_dataset_upload.py), which adds retry with backoff on 5xx, 429 and network errors, a resumable journal, progress lines and `verify`.

## Verify

After confirming, page through `GET /datasets/{id}/items?limit=200` (follow `next_cursor` until it is empty) and compare the `sha256_hash` values with your local manifest. Every file should be there with `status: ready`, and nothing extra. With the bundled tool:

```bash
python3 tools/evren_dataset_upload.py verify ./my-dataset
# verify my-dataset: server 9 / manifest 9 | missing [] | extra [] | not ready [] -> OK
```

## Converting `.npy` to Parquet

The platform rejects `.npy`, but Parquet is accepted and is a better container for embeddings anyway. This needs `pyarrow` and `numpy` (not required by the uploader itself). It assumes a 2-D array `(rows, dims)` and writes in chunks so large arrays do not have to fit in memory:

```python
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

arr = np.load("vectors.npy", mmap_mode="r")          # shape (rows, dims)
writer = None
for start in range(0, len(arr), 100_000):
    chunk = np.ascontiguousarray(arr[start:start + 100_000])
    table = pa.table({
        "id": np.arange(start, start + len(chunk)),
        "vector": pa.FixedSizeListArray.from_arrays(pa.array(chunk.reshape(-1)), chunk.shape[1]),
    })
    writer = writer or pq.ParquetWriter("vectors.parquet", table.schema, compression="zstd")
    writer.write_table(table)
writer.close()
```

Shard the result if it is larger than about 280 MB.
