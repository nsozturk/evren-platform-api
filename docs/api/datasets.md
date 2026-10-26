# Datasets

Base URL `https://api.ssyz.org.tr/api/v1`, header `X-API-Key: <evren_plt_ key>`. File upload has its own page: [upload.md](upload.md).

Status legend: **verified** means exercised against the live API on 2026-10-26. **documented** means taken from the platform's own guide and not exercised by this project.

## Create a dataset - `POST /datasets` (verified)

```json
{
  "name": "my-text-dataset",
  "modality": "NLP",
  "description": "What it contains.",
  "readme": "# My dataset\n\nMarkdown card.",
  "visibility": "private",
  "license": "MIT",
  "tags": ["nlp", "text"]
}
```

| Field | Notes |
|---|---|
| `name`, `modality`, `visibility` | Required. `modality` is one of `VISION`, `AUDIO`, `NLP`, `MULTIMODAL`, `MEDICAL`. `visibility` is `public`, `private` or `unlisted`. |
| `description`, `readme`, `license` | Optional. |
| `tags` | Optional, at most 10. |
| `contributions_enabled`, `org_id` | Optional. |
| `task_profile` | Optional, used with `MEDICAL`. |

The response is the dataset object itself (not wrapped): `id`, `slug`, `owner_username`, and more. Keep the `id`; every other call uses it.

**NLP datasets work through the API.** The web "new dataset" form only enables `VISION` and `MEDICAL`, but the API accepts `"modality": "NLP"`. This is the main non-obvious fact this project documents. Start with `"visibility": "private"` and change it only after you have verified the contents.

Change visibility with `PATCH /datasets/{id}` and body `{"visibility": "public"}` (or `private` / `unlisted`); it returns 200 with the updated dataset (verified 2026-10-26). The dataset settings page in the web app does the same.

## List datasets - `GET /datasets` (verified)

Query parameters:

- `scope` = `all`, `owned` or `shared`. Any other value returns `VALIDATION_ERROR`.
- `visibility` and `modality` filters.

The response is a bare JSON list.

```bash
curl -sS "https://api.ssyz.org.tr/api/v1/datasets?scope=owned&modality=NLP" -H "X-API-Key: $EVREN_PLATFORM_KEY"
```

## Resolve by owner and slug - `GET /datasets/{owner}/{slug}` (documented)

Useful when you only know the public name.

## List items - `GET /datasets/{id}/items` (verified)

Query: `limit` (200 at most) and `cursor`. Response:

```json
{
  "items": [
    {"id": "...", "original_filename": "train-00000.parquet", "file_type": "document",
     "sha256_hash": "...", "status": "ready", "split": "..."}
  ],
  "next_cursor": ""
}
```

Page until `next_cursor` is empty. Items carry the SHA-256 you uploaded, so you can verify a dataset against a local manifest by hash. `tools/evren_dataset_upload.py verify` does exactly that. In practice a `.jsonl` file becomes `file_type: text`, a `.parquet` file becomes `file_type: document`, and `status` is `ready` right after confirmation.

## Delete - `DELETE /datasets/{id}` (verified)

Returns `204`. This removes the dataset; treat it as irreversible and only run it on datasets you created for testing.

## Search the public catalogue - `GET /universe/search` (verified)

Query: `q`, `type` (`dataset` or `model`), `modality`, `limit`, `offset`.

```bash
curl -sS "https://api.ssyz.org.tr/api/v1/universe/search?q=cve&type=dataset&limit=5" -H "X-API-Key: $EVREN_PLATFORM_KEY"
```

## Versions and export (documented, not exercised)

| Call | Purpose |
|---|---|
| `GET /datasets/{id}/versions` | List dataset versions. |
| `GET /datasets/{id}/export/formats` | Export formats available for the dataset. |
| `GET /datasets/{id}/export/download?format=<fmt>&version_tag=<tag>` | Download an export. `format` is `YOLO_TXT`, `COCO_JSON`, `VOC_XML` or `CSV`. |

The annotation formats are aimed at vision datasets. Check `export/formats` for what a given dataset offers before relying on one.

## Credits

Publishing and growing datasets earns credits, and GPU training spends them. See the credits section of the [README](../../README.md#does-publishing-earn-credits). The LLM gateway is free and independent of credits.
