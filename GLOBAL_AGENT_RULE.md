# Global Agent Rule: EVREN dataset publishing (`evren-platform-api`)

> **For developers:** copy the block below into your global agent instructions (for OpenCode: `~/.config/opencode/AGENTS.md`; for other harnesses use their global instruction file) so your assistant knows how to create and upload datasets through the EVREN platform REST API. Replace `<path-to>` with the folder where you cloned `evren-platform-api`.
>
> Unofficial: not affiliated with or endorsed by SSB or the EVREN platform.

```markdown
## EVREN dataset publishing (evren-platform-api)

When asked to create, upload, verify or publish a dataset on the EVREN AI platform:

1. Tool: `python3 <path-to>/evren-platform-api/tools/evren_dataset_upload.py` (Python 3.9+, stdlib only).
   Subcommands: `manifest DIR`, `create --card card.json --readme README.md [--visibility private] [--dry-run]`,
   `upload DIR [--dry-run]`, `verify DIR`. Docs: `<path-to>/evren-platform-api/docs/api/`.
2. Auth: environment variable `EVREN_PLATFORM_KEY` holding an `evren_plt_` key. Never print, log, echo or
   commit it. `evren_mdl_` (models only) and `evren_llm_` (LLM gateway) keys cannot call dataset endpoints.
   The Platform API uses the `X-API-Key` header; the LLM gateway uses `Authorization: Bearer`.
3. Order: `manifest` -> `create --dry-run` -> `create` (private) -> `upload` -> `verify`.
   The API accepts `modality: NLP` although the web form does not offer it.
   `.npy` is not accepted (convert to Parquet); shard files to 280 MB or less.
4. Resume: if `upload` is interrupted or exits 1, re-run the same command. It resumes from the journal and the
   server dedups by SHA-256. Exit codes: 0 ok, 1 operation failed, 2 usage/config error.
5. Safety: always create datasets as `private`; never make one public without the user explicitly asking;
   never accept the EVREN LLM gateway terms for the user; never delete a dataset unless asked about that
   specific dataset; ask before uploading personal or confidential data (the platform may use uploaded data
   for training under its user agreement).
```
