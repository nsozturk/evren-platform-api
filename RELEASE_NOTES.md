# v0.1.0 (draft - not released)

First public version of evren-platform-api, an unofficial guide and toolkit for the EVREN AI platform's REST API. This file is the draft text for a future GitHub release; no release has been cut.

## Highlights

- API notes measured against the live API on 2026-10-26: key types and scopes, hosts and headers, creating **NLP** datasets through the API, the presign / PUT / confirm upload flow, SHA-256 dedup, item listing for verification, catalogue search, and the common 401/403 cases.
- `tools/evren_dataset_upload.py` (Python 3.9+, standard library only): `manifest`, `create`, `upload`, `verify`; resumable journal, retry with backoff on 5xx/429/network errors, streamed PUT, timestamped progress, `--dry-run`, exit codes 0/1/2.
- OpenCode support: `AGENTS.md`, `GLOBAL_AGENT_RULE.md`, the `/evren-publish-dataset` command and an example provider block for the LLM gateway.
- English and Turkish READMEs, offline test suite, `llms.txt`, `CITATION.cff`.

## Known limits

- Unofficial; behaviour may change when the platform changes.
- Changing a dataset's visibility through the API is not verified; use the web app.
- Versions and export endpoints are documented but were not exercised.
- Other agent CLIs (Claude Code, Codex, Gemini CLI, Cursor) are planned.

## Upgrade

Nothing to upgrade yet; this is the first version.
