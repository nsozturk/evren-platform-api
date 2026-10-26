# API keys and authentication

EVREN exposes two separate HTTP surfaces. They use different hosts, different headers and different key types. Mixing them up is the most common cause of `401` and `403` errors (see [errors.md](errors.md)).

| Surface | Base URL | Auth header | Key prefix |
|---|---|---|---|
| Platform REST API (datasets, models, billing, catalogue) | `https://api.ssyz.org.tr/api/v1` | `X-API-Key: <key>` | `evren_plt_` (full access), `evren_mdl_` (models and inference only) |
| LLM gateway (chat, embeddings, OCR, ...) | `https://evren-llmapi.ssyz.org.tr/v1` | `Authorization: Bearer <key>` (`X-API-Key` is also accepted) | `evren_llm_` |

For `evren_` keys the Platform API rejects `Authorization: Bearer` with a `401` ("Geçersiz token"). Always send `X-API-Key` there.

## Creating a key

Keys are created in the EVREN web app under **Settings -> API Keys** (`/api-keys` on `https://evren.ssyz.org.tr`). The full key is shown once; copy it when it appears.

Pick the type from what you need:

- Creating, listing or uploading datasets -> `evren_plt_`.
- Only running models / inference -> `evren_mdl_`.
- Only calling the LLM gateway -> `evren_llm_`.

## What each key can call

Measured against the live API on 2026-10-26:

| Key | `GET /auth/me` | `GET /datasets` | `GET /models` | LLM gateway `GET /v1/models` |
|---|---|---|---|---|
| `evren_plt_` | 200 | 200 | 200 | 401 |
| `evren_mdl_` | 403 "only inference and model endpoints" | 403 | 200 | 401 |
| `evren_llm_` | 401 | 401 | 401 | 200 after the terms are accepted, otherwise 403 `terms_not_accepted` |

So dataset work needs an `evren_plt_` key, and an LLM-gateway key cannot touch the Platform API at all.

## Keeping the key out of your repo

This toolkit reads the Platform key from one environment variable:

```bash
export EVREN_PLATFORM_KEY="evren_plt_..."   # paste your own key; never commit it
```

Optional, macOS only: store it in the login Keychain once and load it per command so it never sits in your shell history or dotfiles.

```bash
security add-generic-password -s evren-platform-key -a "$USER" -w     # prompts for the value
EVREN_PLATFORM_KEY="$(security find-generic-password -s evren-platform-key -a "$USER" -w)" \
  python3 tools/evren_dataset_upload.py verify ./my-dataset
```

For the LLM gateway, OpenCode reads `EVREN_LLM_API_KEY` (see [../opencode.md](../opencode.md)).

## Smoke test

```bash
curl -sS https://api.ssyz.org.tr/api/v1/auth/me -H "X-API-Key: $EVREN_PLATFORM_KEY"
curl -sS https://api.ssyz.org.tr/api/v1/billing/balance -H "X-API-Key: $EVREN_PLATFORM_KEY"
```

`/billing/balance` returns `{balance, available, held, total_earned, total_spent}` in credits (CR).

## Response envelope

Most endpoints answer `{success, data, message}`. Some return the object directly: `POST /datasets` returns the dataset, `GET /datasets` returns a bare list and `GET /models` returns `{items, total}`. Write client code that tolerates both shapes. The bundled uploader unwraps `{success, data}` when present.
