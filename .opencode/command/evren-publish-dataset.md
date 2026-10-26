---
description: Publish a local folder to EVREN as a private NLP dataset (manifest, create, upload, verify)
---

Publish the folder `$ARGUMENTS` to the EVREN platform as a **private** NLP dataset using `tools/evren_dataset_upload.py`. Follow these steps in order and stop on the first failure.

Rules that always apply:
- Never print, log, echo or write the value of `EVREN_PLATFORM_KEY`. Only check that it is set (`test -n "$EVREN_PLATFORM_KEY"`). If it is unset, tell the user to export an `evren_plt_` key and stop.
- Create the dataset as `private`. Do not change visibility to public/unlisted, and do not pass `--visibility public`, unless the user explicitly asks in this conversation. Ask before doing so.
- Do not run `DELETE` calls and do not accept any LLM-gateway terms.

Steps:
1. Inspect the folder. It needs the data files plus a `card.json` (fields: `name`, `description`, `license`, `tags`, at most 10 tags) and a `README.md` dataset card. If either is missing, draft it from the folder contents (see `examples/card.example.json`), show it to the user and ask for approval before writing.
2. Check the files against the platform rules: `.npy` is not accepted (offer to convert to Parquet, see `docs/api/upload.md`), and files above about 280 MB should be sharded. Ask before converting or splitting anything.
3. Preview: `python3 tools/evren_dataset_upload.py create --card $ARGUMENTS/card.json --readme $ARGUMENTS/README.md --dry-run`, then show the user the name, license and tags.
4. Build the manifest: `python3 tools/evren_dataset_upload.py manifest $ARGUMENTS`.
5. Create the dataset: `python3 tools/evren_dataset_upload.py create --card $ARGUMENTS/card.json --readme $ARGUMENTS/README.md --visibility private`. This writes `.evren_dataset.json` in the folder; keep that file, it is what makes the upload resumable.
6. Upload: `python3 tools/evren_dataset_upload.py upload $ARGUMENTS`. If it is interrupted or some files fail (exit code 1), re-run the same command; it resumes from the journal.
7. Verify: `python3 tools/evren_dataset_upload.py verify $ARGUMENTS`. Expect `-> OK` and exit code 0.
8. Report: dataset slug and id from `.evren_dataset.json`, files uploaded, files skipped as duplicates, and the verify line. Then ask whether the user wants the dataset made public; if yes, tell them to change visibility in the dataset settings of the EVREN web app.

Exit codes: 0 ok, 1 operation failed, 2 usage or configuration error (for example a missing key or manifest).
