# Using EVREN with OpenCode

[OpenCode](https://opencode.ai) is the first supported agent harness for this repository. Other CLIs (Claude Code, Codex, Gemini CLI, Cursor) are planned; the `AGENTS.md` contract is plain markdown, so most of them can already read it.

There are two separate things you may want, and they use two different keys:

| Goal | Key | Where it goes |
|---|---|---|
| Use EVREN-hosted models as the coding model in OpenCode | `evren_llm_` | `EVREN_LLM_API_KEY`, read by the provider block below |
| Let the agent create and upload datasets | `evren_plt_` | `EVREN_PLATFORM_KEY`, read by `tools/evren_dataset_upload.py` |

## 1. EVREN as an OpenCode provider

The LLM gateway speaks the OpenAI-compatible protocol. Add a provider to your `opencode.json` (this repository ships the same block as [`opencode.example.json`](../opencode.example.json)):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "evren": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "EVREN",
      "options": {
        "baseURL": "https://evren-llmapi.ssyz.org.tr/v1",
        "apiKey": "{env:EVREN_LLM_API_KEY}"
      },
      "models": {
        "glm-5.3": { "name": "GLM 5.3" },
        "deepseek-v4.1-flash": { "name": "DeepSeek V4.1 Flash" },
        "mimo-v2.6-pro": { "name": "MiMo V2.6 Pro" }
      }
    }
  }
}
```

```bash
export EVREN_LLM_API_KEY="evren_llm_..."    # your own key; never commit it
opencode                                      # then pick evren/glm-5.3 with /models
```

The key never appears in the file: OpenCode substitutes `{env:EVREN_LLM_API_KEY}` at load time. The first use of a new LLM key requires accepting the gateway terms, which you do yourself; see [api/llm-gateway.md](api/llm-gateway.md).

For a ready-made installer that sets the provider up for you, see the community project [bykemalh/evren-llm-opencode](https://github.com/bykemalh/evren-llm-opencode).

## 2. Dataset publishing with the repo's OpenCode command

This repository contains a custom OpenCode command at [`.opencode/command/evren-publish-dataset.md`](../.opencode/command/evren-publish-dataset.md). It also provides `AGENTS.md`, which OpenCode reads automatically as project instructions.

```bash
git clone https://github.com/nsozturk/evren-platform-api
cd evren-platform-api
export EVREN_PLATFORM_KEY="evren_plt_..."
opencode
```

Then, inside OpenCode:

```
/evren-publish-dataset ./path/to/my-folder
```

The command walks the agent through: check the folder (data files plus `card.json` and `README.md`), warn about `.npy` and oversized files, preview the request with `--dry-run`, build the manifest, create a **private** NLP dataset, upload, verify by SHA-256, and report. It asks before anything public.

To use the command from another project, copy `.opencode/command/evren-publish-dataset.md` and `tools/evren_dataset_upload.py` into it (and adjust the script path in the command), or paste [`GLOBAL_AGENT_RULE.md`](../GLOBAL_AGENT_RULE.md) into your global OpenCode instructions.

## Safety notes for agents

- The agent must never print or write `EVREN_PLATFORM_KEY`.
- Datasets are created private. Making one public is your decision, made in the web app.
- Accepting the LLM gateway terms is yours to do, not the agent's.
- Uploaded datasets may be used by the platform for training under its user agreement; read the agreement before uploading anything you do not want used that way.
