# LLM gateway (short)

This repository is about the Platform REST API for datasets. The LLM gateway is a separate service; this page only orients you and links out. Community projects that cover it in depth are listed in the [README](../../README.md#related-projects-and-alternatives).

| | |
|---|---|
| Base URL | `https://evren-llmapi.ssyz.org.tr/v1` |
| Auth | `Authorization: Bearer <evren_llm_ key>` (`X-API-Key` is also accepted) |
| OpenAPI | `https://evren-llmapi.ssyz.org.tr/openapi.json` |
| Docs UI | `https://evren-llmapi.ssyz.org.tr/docs` |

Endpoints: `chat/completions`, `completions`, `messages` (Anthropic-style), `responses`, `embeddings`, `rerank`, `models`, `ocr`, `audio`, `media`, `quota`, and `terms/{status,text,accept}`.

Per the platform's pricing page the gateway is free, independent of credits, with limits of 15M tokens per day, 2.5M per 5 minutes and 32 concurrent requests.

## Terms must be accepted first

The first call with a new key returns `403 terms_not_accepted` until the account accepts the gateway terms:

1. `/v1/terms/status` shows whether they are accepted.
2. `GET /v1/terms/text` returns the terms. **Read them yourself.**
3. `POST /v1/terms/accept` with `{"version": 1}` records acceptance.

Accepting terms is a legal act by the account owner. Scripts and coding agents should not do it for you; see the safety rules in [../../AGENTS.md](../../AGENTS.md).

## Models (as listed on 2026-10-26)

| Model | Notes |
|---|---|
| `glm-5.3` | 524K context |
| `deepseek-v4.1-flash` | 1M context |
| `mimo-v2.6-pro` | 1M context |
| `qwen3.8-flash-next` | chat |
| `gemma-4-31b` | chat |
| `qwen3-vl-30b` | vision |
| `auto` | 32K router, no tool calls |

The list changes; ask `GET /v1/models` for the current one.

## Using it from OpenCode

See [../opencode.md](../opencode.md) for the provider block and the community installer.
