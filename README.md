<p align="center">
  <img src="assets/banner.png" alt="evren-platform-api - dataset upload guide and toolkit for the EVREN platform REST API" width="100%">
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"></a>
  <img alt="Version 0.1.0" src="https://img.shields.io/badge/version-0.1.0-blue">
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="Python stdlib only" src="https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen">
  <img alt="Unofficial" src="https://img.shields.io/badge/status-unofficial-orange">
  <a href="AGENTS.md"><img alt="AI Agent ready" src="https://img.shields.io/badge/AI%20Agent-ready-8b5cf6"></a>
  <a href="docs/opencode.md"><img alt="OpenCode ready" src="https://img.shields.io/badge/OpenCode-ready-0ea5e9"></a>
</p>

<p align="center">
  <code>evren</code> <code>evren-platform</code> <code>rest-api</code> <code>dataset-upload</code> <code>resumable-upload</code>
  <code>nlp-datasets</code> <code>turkish-ai</code> <code>opencode</code> <code>ai-agents</code> <code>python-stdlib</code>
</p>

**evren-platform-api is a free, open-source, unofficial guide and toolkit for the EVREN AI platform's REST API that shows how to create datasets, upload files resumably and publish them, with a ready OpenCode workflow.**

English | [Türkçe](README.tr.md)

> **Unofficial.** This project is not affiliated with or endorsed by SSB or the EVREN platform. "EVREN" is used only to say which API the code works with. No EVREN logo, colours or branding are used. You act under your own account and under the platform's terms; uploaded datasets and models may be used by the platform for training under its user agreement, so read that agreement before you upload.

## Why this exists

Community projects already cover EVREN's **LLM gateway**: an OpenCode provider installer, command-line clients, chat UIs, and an MCP server for training. What nobody had written down is the **Platform REST API for datasets**:

- which API key type can call which endpoint,
- that an **NLP dataset can be created through the API** even though the web form only offers vision and medical,
- the three-step upload (presign, PUT, confirm), how deduplication works, and how to verify the result,
- how to do all of it resumably, from a script or from an AI coding agent.

This repository documents those facts as they were measured against the live API on 2026-10-26, and ships one small tool that does the work.

## Quick start

You need Python 3.9 or newer. There is nothing to install.

**1. Get a key.** In the EVREN web app open Settings -> API Keys and create an `evren_plt_` key (it is shown once).

```bash
git clone https://github.com/nsozturk/evren-platform-api
cd evren-platform-api
export EVREN_PLATFORM_KEY="evren_plt_..."     # your own key; never commit it
```

**2. Prepare a dataset folder** with your data files, a dataset card and a README:

```bash
mkdir my-dataset                               # put train.parquet, data.jsonl, ... in it
cp examples/card.example.json my-dataset/card.json   # edit name, description, license, tags
$EDITOR my-dataset/README.md                   # the dataset card shown on the platform
```

**3. Create the dataset** (private NLP; preview first):

```bash
python3 tools/evren_dataset_upload.py manifest my-dataset
python3 tools/evren_dataset_upload.py create --card my-dataset/card.json --readme my-dataset/README.md --dry-run
python3 tools/evren_dataset_upload.py create --card my-dataset/card.json --readme my-dataset/README.md --visibility private
```

**4. Upload.** Safe to stop and re-run at any point; it resumes.

```bash
python3 tools/evren_dataset_upload.py upload my-dataset
```

**5. Verify** that every file is on the server with a matching SHA-256:

```bash
python3 tools/evren_dataset_upload.py verify my-dataset
# verify my-dataset: server 9 / manifest 9 | missing [] | extra [] | not ready [] -> OK
```

The uploader prints timestamped progress lines, retries on 5xx, 429 and network errors with backoff, streams files from disk instead of loading them into memory, and keeps a journal so a re-run skips finished files. Defaults live inside the dataset folder (`.evren_dataset.json`, `.evren_upload_journal.jsonl`, `.evren_upload.log`). Exit codes: `0` ok, `1` operation failed, `2` usage or configuration error.

## Which API key do I need?

| Key | Prefix | Host | Header | Works for |
|---|---|---|---|---|
| Full platform key | `evren_plt_` | `https://api.ssyz.org.tr/api/v1` | `X-API-Key` | Datasets, models, billing, catalogue |
| Models-only key | `evren_mdl_` | same | `X-API-Key` | Models and inference only (dataset calls return 403) |
| LLM gateway key | `evren_llm_` | `https://evren-llmapi.ssyz.org.tr/v1` | `Authorization: Bearer` | Chat, embeddings, OCR, ... (not the Platform API) |

Dataset work needs `evren_plt_`. Details and the measured scope matrix: [docs/api/keys.md](docs/api/keys.md).

## API reference

| Page | Covers |
|---|---|
| [docs/api/keys.md](docs/api/keys.md) | Hosts, headers, key types and scopes, response envelope |
| [docs/api/datasets.md](docs/api/datasets.md) | Create, list, delete, items, catalogue search, versions, export |
| [docs/api/upload.md](docs/api/upload.md) | Presign / PUT / confirm with curl and Python, dedup, verification, sharding, `.npy` to Parquet |
| [docs/api/llm-gateway.md](docs/api/llm-gateway.md) | Short orientation to the LLM gateway and its terms flow |
| [docs/api/errors.md](docs/api/errors.md) | Error shape, the 401/403 cases, retry guidance, exit codes |
| [docs/opencode.md](docs/opencode.md) | OpenCode provider block and the repo's OpenCode command |

## Use it with OpenCode

[OpenCode](https://opencode.ai) is the first supported agent harness. The repository contains an [`AGENTS.md`](AGENTS.md) contract and a custom command, so an agent can publish a folder for you:

```bash
export EVREN_PLATFORM_KEY="evren_plt_..."
opencode
# inside OpenCode:
/evren-publish-dataset ./my-dataset
```

The command builds the manifest, creates a **private** NLP dataset, uploads, verifies, reports, and asks before anything public. To use EVREN-hosted models as your OpenCode model, add the provider block from [`opencode.example.json`](opencode.example.json) (key from `EVREN_LLM_API_KEY`); see [docs/opencode.md](docs/opencode.md). To give any assistant these instructions globally, paste [`GLOBAL_AGENT_RULE.md`](GLOBAL_AGENT_RULE.md) into its global instructions.

## Platform credits

From the platform's pricing page (2026-10-26; check it for current numbers):

| Item | Credits (CR) |
|---|---|
| Starting balance | 1000 |
| Daily login | +10 |
| Publishing a dataset | +5 (up to 3 per day) |
| Item milestones at 100 / 500 / 1K / 5K / 10K | +2 / +5 / +15 / +25 / +40 |
| Daily earning cap | 100 |
| GPU training, 1x H200 | 10 per hour |

Milestones count files, not rows; unpublished datasets do not count; the datasets need at least 80 % diversity. The LLM gateway is free and independent of credits (15M tokens per day, 2.5M per 5 minutes, 32 concurrent requests). `GET /billing/balance` returns your balance.

## FAQ

### Can I upload text or tabular data to EVREN?

Yes. Accepted formats include Parquet, Arrow, Feather, SQLite, CSV, TSV, JSON, JSONL, NDJSON, TXT, Markdown and PDF, plus images, audio and video. Create the dataset with `"modality": "NLP"` and upload the files with the three-step flow in [docs/api/upload.md](docs/api/upload.md).

### Why does the web form not offer NLP?

The web "new dataset" form enables only vision and medical datasets, but the API accepts `NLP` (verified on 2026-10-26). This project does not know the platform's intent, so treat NLP-through-the-API as working today but not as a promise.

### Which API key do I need?

An `evren_plt_` key, sent in the `X-API-Key` header, for anything involving datasets. `evren_mdl_` keys are limited to models and inference; `evren_llm_` keys only work on the LLM gateway. See the [table above](#which-api-key-do-i-need).

### Is `.npy` supported?

No. The platform's extension list does not include `.npy`. Convert arrays to Parquet; [docs/api/upload.md](docs/api/upload.md#converting-npy-to-parquet) has a chunked `pyarrow` snippet.

### How large can a file be?

Files of 0.7 KB, 105 MB and 316 MB all uploaded successfully, and no limit was hit up to 316 MB. The tool warns above 280 MB and the guide recommends sharding to stay within what was tested.

### What happens if my upload is interrupted?

Run the same command again. Finished files are skipped from the journal, the server also deduplicates by SHA-256, and `verify` tells you whether anything is missing.

### Does publishing earn credits?

Yes, within the limits in [Platform credits](#platform-credits): +5 CR per published dataset (up to three a day), plus item milestones, capped at 100 CR of earnings per day.

### Is this official?

No. It is an independent community project, not affiliated with or endorsed by SSB or the EVREN platform. See the notice at the top.

### Can an AI agent run this safely?

That is what [`AGENTS.md`](AGENTS.md) is for: keys stay in the environment, datasets are created private, terms are never accepted on your behalf, and nothing is made public without you asking.

## Published with this tool

- [cve-threat-intelligence-hub](https://evren.ssyz.org.tr/datasets/u4be40c9fa813/cve-threat-intelligence-hub): 400,776 CVE records with 384-dim embeddings, 9 Parquet files
- [open-agent-db](https://evren.ssyz.org.tr/datasets/u4be40c9fa813/open-agent-db): 3.65M AI-agent skill / rule / MCP metadata rows, 13 Parquet files

## Related projects and alternatives

These community projects are linked by name for convenience; no endorsement is implied and this repository does not duplicate them. They mostly cover the LLM gateway, which is a different surface from the dataset API documented here.

| Project | What it is |
|---|---|
| [bykemalh/evren-llm-opencode](https://github.com/bykemalh/evren-llm-opencode) | OpenCode LLM provider installer |
| [emuzinun/evren-mcp](https://github.com/emuzinun/evren-mcp) | MCP server for cost-approved training from Claude Code |
| [speker/evren-sdk](https://github.com/speker/evren-sdk) | Python SDK: vision inference and image upload |
| [necmettincimen/evren-cli](https://github.com/necmettincimen/evren-cli) | Terminal coding assistant on the LLM gateway |
| [zakcali/evren-chat](https://github.com/zakcali/evren-chat) | Gradio chat client |
| [erdalnacitunc-create/evren-desktop](https://github.com/erdalnacitunc-create/evren-desktop) | Windows desktop client |
| [drdoof2019/EvrenLLM-Kullanim](https://github.com/drdoof2019/EvrenLLM-Kullanim) | LLM gateway usage notes (Turkish) |

This repository fills the gap for text and tabular datasets, resumable transfers and AI-agent use.

## Other CLIs: planned

OpenCode is supported first; ready-made setups for Claude Code, Codex, Gemini CLI and Cursor are planned.

## License

[MIT](LICENSE). Contributions are welcome through issues and pull requests; please keep the tool standard-library only and the tests offline.
