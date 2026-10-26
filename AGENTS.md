# AGENTS.md - contract for coding agents

This file tells coding agents (OpenCode first; Claude Code, Codex, Gemini CLI and Cursor can read it too) how to work in this repository and how to use its tool. The project is an **unofficial** guide and toolkit for the EVREN platform's REST API; it is not affiliated with or endorsed by SSB or the EVREN platform.

## What is here

| Path | Purpose |
|---|---|
| `tools/evren_dataset_upload.py` | Resumable dataset uploader. Python 3.9+, standard library only. |
| `docs/api/*.md` | API notes: keys, datasets, upload, LLM gateway, errors. |
| `.opencode/command/evren-publish-dataset.md` | OpenCode command: folder -> private NLP dataset -> verified. |
| `tests/test_offline.py` | Offline tests with a fake HTTP layer. |

## Environment

| Variable | Used by | Notes |
|---|---|---|
| `EVREN_PLATFORM_KEY` | `tools/evren_dataset_upload.py` | An `evren_plt_` key. `evren_mdl_` and `evren_llm_` keys cannot call dataset endpoints and are refused up front. Never print or write it. |
| `EVREN_LLM_API_KEY` | OpenCode provider block | An `evren_llm_` key for the LLM gateway. Unrelated to datasets. |

## Commands

Run from the repository root. `DIR` is a dataset folder.

| Task | Command |
|---|---|
| Build the manifest (filename, bytes, sha256) | `python3 tools/evren_dataset_upload.py manifest DIR` |
| Preview dataset creation | `python3 tools/evren_dataset_upload.py create --card DIR/card.json --readme DIR/README.md --dry-run` |
| Create a private NLP dataset | `python3 tools/evren_dataset_upload.py create --card DIR/card.json --readme DIR/README.md --visibility private` |
| Preview an upload | `python3 tools/evren_dataset_upload.py upload DIR --dry-run` |
| Upload (resumable) | `python3 tools/evren_dataset_upload.py upload DIR` |
| Verify against the server by SHA-256 | `python3 tools/evren_dataset_upload.py verify DIR` |
| Run the tests | `python3 -m unittest discover -s tests` |

Useful flags: `--log FILE`, `--retries N`, `--journal FILE` (upload), `--modality`, `--dir` (create), `--glob` and `--exclude` (manifest). Defaults inside `DIR`: `.evren_dataset.json` (dataset id, written by `create`), `.evren_upload_journal.jsonl` (progress journal), `.evren_upload.log`.

`manifest` skips `manifest.json`, `card.json`, `README.md`, hidden files and `.npy` files by default.

## Exit codes

| Code | Meaning | What to do |
|---|---|---|
| 0 | Success. | - |
| 1 | Operation failed: a file failed, `verify` reported FAIL, or the API returned an error. | Read the log. For upload failures re-run the same command; it resumes. |
| 2 | Usage or configuration error (key missing or wrong type, missing manifest or state file). | Fix the input; do not retry blindly. |

## Operational truths

- The Platform API authenticates with `X-API-Key`, not `Authorization: Bearer`. The LLM gateway is the other way round. See `docs/api/keys.md`.
- The API accepts `"modality": "NLP"` even though the web form does not offer it.
- Upload is presign -> PUT -> confirm; unconfirmed files are not added. The server dedups by SHA-256.
- `.npy` is not accepted; convert to Parquet. Shard files to 280 MB or less.
- Re-running `upload` is always safe: finished files are skipped from the journal, and the server dedups the rest.
- 401 or 403 from the API means the wrong key type; the tool aborts instead of failing every file.

## Safety rules (hard)

1. **Never print, log, echo, commit or write an API key**, including in examples, test fixtures, shell history you generate or command output. Only test that it is set.
2. **Never accept the LLM gateway terms on the user's behalf.** Point the user to `GET /v1/terms/text` and let them accept.
3. **Never make a dataset public or unlisted without the user explicitly asking in the current conversation.** Create datasets as `private`. When the user asks, flip with `PATCH /datasets/{id}` `{"visibility": "public"}`.
4. **Do not delete datasets** (`DELETE /datasets/{id}`) unless the user asks for that specific dataset.
5. Uploaded data may be used by the platform for training under its user agreement. Do not upload personal, confidential or licensed-restricted data without the user's confirmation.
6. Do not commit `.evren_*` files, manifests of private data, or dataset contents. `.gitignore` already covers the state, journal and log files.
7. Do not copy text from the EVREN website or in-app guide into this repository; describe behaviour in your own words.
8. Do not add EVREN logos, colours or branding. The name is used only to state compatibility.

## Editing this repository

- Keep the tool Python 3.9+ and standard-library only. No new dependencies.
- Keep tests offline; `tests/test_offline.py` must pass before and after a change.
- Docs state what was measured. Mark anything unverified as such.
- Primary language is English; `README.tr.md` is the Turkish mirror and should change with `README.md`.
