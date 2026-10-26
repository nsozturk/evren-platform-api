# Errors

## Shape

Failed Platform API calls normally answer:

```json
{"success": false, "error": {"code": "VALIDATION_ERROR", "message": "...", "details": {}}}
```

Successful calls usually answer `{success, data, message}`, though some return the object or list directly (see [keys.md](keys.md#response-envelope)). Check the HTTP status first, then read `error.code` and `error.message`.

## Cases seen while testing

All observed on 2026-10-26.

| Situation | Status | What it means / fix |
|---|---|---|
| `Authorization: Bearer evren_plt_...` against the Platform API | 401 "Geçersiz token" | Use the `X-API-Key` header instead. |
| `evren_mdl_` key on `/auth/me` or `/datasets` | 403 "only inference and model endpoints" | A models-only key. Create an `evren_plt_` key for dataset work. |
| `evren_llm_` key on the Platform API (`/auth/me`, `/datasets`, `/models`) | 401 | LLM-gateway keys do not work on the Platform API. |
| `evren_plt_` key on the LLM gateway (`/v1/models`) | 401 | Platform keys do not work on the gateway. Use an `evren_llm_` key. |
| `evren_llm_` key on the gateway before accepting terms | 403 `terms_not_accepted` | Read and accept the terms yourself; see [llm-gateway.md](llm-gateway.md). |
| `GET /datasets?scope=<anything but all/owned/shared>` | `VALIDATION_ERROR` | Use `all`, `owned` or `shared`. |
| Uploading a `.npy` file | rejected by the extension check | Convert to Parquet; see [upload.md](upload.md#converting-npy-to-parquet). |

The exact wording and code of the `.npy` rejection were not captured; check `GET /datasets/upload/extensions` before uploading.

## Retrying

- `5xx`, `429` and network failures are worth retrying with exponential backoff. `tools/evren_dataset_upload.py` waits 5 s, 10 s, 20 s, ... (capped at 120 s) for up to 4 attempts by default.
- Other `4xx` responses are not transient. Fix the request or the key instead of retrying.
- A repeated upload is safe: the server dedups by SHA-256, and the tool's journal skips files it already finished.

## Tool exit codes

| Code | Meaning |
|---|---|
| 0 | Success. |
| 1 | The operation failed: a file failed to upload, `verify` found a mismatch, or the API returned an error. |
| 2 | Usage or configuration error, such as a missing `EVREN_PLATFORM_KEY` or a missing manifest. |
