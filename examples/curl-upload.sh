#!/usr/bin/env bash
# Upload ONE file to an existing EVREN dataset with plain curl (3-step flow). Placeholders only.
#   export EVREN_PLATFORM_KEY=<your evren_plt_ key>
#   ./curl-upload.sh <dataset-id> <file>
# Needs: curl, jq, shasum (macOS) or sha256sum (Linux). For many files or resuming, use tools/evren_dataset_upload.py.
set -euo pipefail

API="https://api.ssyz.org.tr/api/v1"
: "${EVREN_PLATFORM_KEY:?set EVREN_PLATFORM_KEY first}"
DATASET_ID="${1:?usage: $0 <dataset-id> <file>}"
FILE="${2:?usage: $0 <dataset-id> <file>}"

NAME="$(basename "$FILE")"
if command -v sha256sum >/dev/null; then SHA="$(sha256sum "$FILE" | cut -d' ' -f1)"; else SHA="$(shasum -a 256 "$FILE" | cut -d' ' -f1)"; fi
SIZE="$(wc -c < "$FILE" | tr -d ' ')"

# 1) presign
PRE="$(curl -fsS -X POST "$API/datasets/$DATASET_ID/upload/presign" \
  -H "X-API-Key: $EVREN_PLATFORM_KEY" -H "Content-Type: application/json" \
  -d "$(jq -n --arg n "$NAME" --arg s "$SHA" --argjson z "$SIZE" '{files:[{filename:$n,sha256_hash:$s,file_size:$z}]}')")"

if [ "$(echo "$PRE" | jq --arg s "$SHA" '[.duplicates[]? | select(. == $s)] | length')" != "0" ]; then
  echo "already on the server (same SHA-256), nothing to do"; exit 0
fi
UPLOAD_URL="$(echo "$PRE" | jq -r '.presigned_urls[0].upload_url')"   # relative path
OBJECT_KEY="$(echo "$PRE" | jq -r '.presigned_urls[0].object_key')"

# 2) PUT the raw bytes (-T streams the file from disk instead of loading it into memory)
curl -fsS -T "$FILE" "$API$UPLOAD_URL" \
  -H "X-API-Key: $EVREN_PLATFORM_KEY" -H "Content-Type: application/octet-stream"

# 3) confirm - files that are not confirmed are not added to the dataset
curl -fsS -X POST "$API/datasets/$DATASET_ID/upload/confirm" \
  -H "X-API-Key: $EVREN_PLATFORM_KEY" -H "Content-Type: application/json" \
  -d "$(jq -n --arg k "$OBJECT_KEY" --arg s "$SHA" --arg n "$NAME" --argjson z "$SIZE" \
        '{items:[{object_key:$k,sha256_hash:$s,filename:$n,file_size:$z}]}')"
echo
