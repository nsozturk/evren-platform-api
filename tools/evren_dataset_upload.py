#!/usr/bin/env python3
"""Resumable dataset uploader for the EVREN platform REST API (unofficial). Python 3.9+, stdlib only.

  export EVREN_PLATFORM_KEY=evren_plt_...        # never commit this

  evren_dataset_upload.py manifest DIR                      # build DIR/manifest.json (filename, bytes, sha256)
  evren_dataset_upload.py create --card card.json --readme README.md [--visibility private] [--dry-run]
  evren_dataset_upload.py upload DIR [--dry-run]            # presign -> PUT -> confirm, resumable
  evren_dataset_upload.py verify DIR                        # compare server items with the manifest by SHA-256

Exit codes: 0 ok, 1 operation failed (some file failed, verify mismatch, API error), 2 usage/config error.
Re-running `upload` resumes: finished files are read from a journal and skipped; the server also dedups by SHA-256.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_BASE = "https://api.ssyz.org.tr/api/v1"
ENV_KEY = "EVREN_PLATFORM_KEY"
STATE_FILE = ".evren_dataset.json"
DEFAULT_JOURNAL = ".evren_upload_journal.jsonl"
DEFAULT_LOG = ".evren_upload.log"
# Files the tool owns or that describe the dataset rather than being dataset items.
DEFAULT_EXCLUDE = ("manifest.json", "card.json", "README.md")
SHARD_WARN_BYTES = 280 * 1_000_000  # largest sizes exercised were ~316 MB; stay below that
MODALITIES = ("NLP", "VISION", "AUDIO", "MULTIMODAL")
VISIBILITIES = ("private", "unlisted", "public")
EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


class UsageError(Exception):
    """Bad input or missing configuration (exit 2)."""


class ApiError(RuntimeError):
    """HTTP/API failure. status is 0 for network exhaustion."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


# ----------------------------------------------------------------------------- helpers
def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Log:
    """Timestamped lines to stdout and, if a path is given, appended (flushed) to a file."""

    def __init__(self, path=None):
        self.path = path
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def __call__(self, msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")


def write_json_atomic(path, obj):
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise UsageError(f"file not found: {path}")
    except ValueError as e:
        raise UsageError(f"{path} is not valid JSON: {e}")


def append_jsonl(path, rec):
    prefix = ""
    if os.path.exists(path) and os.path.getsize(path):
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":  # a crash tore the last line: start a fresh one so this record survives
                prefix = "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(prefix + json.dumps(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def unwrap(resp):
    """Some endpoints answer {success, data, message}, others return the object directly."""
    if isinstance(resp, dict) and "success" in resp and isinstance(resp.get("data"), (dict, list)):
        return resp["data"]
    return resp


def _parse(raw):
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def get_key():
    key = os.environ.get(ENV_KEY, "").strip()
    if not key:
        raise UsageError(
            f"{ENV_KEY} is not set. Create an evren_plt_ key in the EVREN web app (Settings -> API Keys), "
            f"then run: export {ENV_KEY}=<your key>   (never commit it)"
        )
    if key.startswith(("evren_mdl_", "evren_llm_")):
        raise UsageError(
            f"{ENV_KEY} holds a models-only or LLM-gateway key; dataset endpoints need a full-access evren_plt_ key"
        )
    return key


# ----------------------------------------------------------------------------- HTTP layer
class _ProgressFile:
    """File wrapper that streams in blocks and logs a heartbeat every few seconds."""

    def __init__(self, path, size, log, every=10.0):
        self.fh = open(path, "rb")
        self.size, self.log, self.every = size, log, every
        self.name, self.sent = os.path.basename(path), 0
        self.t0 = self.last = time.time()

    def read(self, n=-1):
        block = self.fh.read(n)
        self.sent += len(block)
        now = time.time()
        if now - self.last >= self.every:
            self.last = now
            rate = self.sent / 1e6 / max(now - self.t0, 1e-6)
            self.log(f"    {self.name}: {self.sent / 1e6:.0f}/{self.size / 1e6:.0f} MB "
                     f"({100 * self.sent / max(self.size, 1):.0f}%) | {rate:.1f} MB/s")
        return block

    def close(self):
        self.fh.close()


class Client:
    """Minimal EVREN Platform API client with retry/backoff on 5xx, 429 and network errors."""

    def __init__(self, key, log=print, base=API_BASE, retries=4, sleep=time.sleep, timeout=1800):
        self.key, self.log, self.base = key, log, base.rstrip("/")
        self.retries, self.sleep, self.timeout = max(1, retries), sleep, timeout

    def call(self, method, path, body=None, stream=None, size=None):
        url = path if path.startswith("http") else self.base + path
        if not url.startswith(self.base + "/"):
            raise ApiError(0, "refusing to send the API key to a host other than the API base")
        reason = "unknown"
        for attempt in range(1, self.retries + 1):
            headers = {"X-API-Key": self.key}
            fh = None
            if stream is not None:
                fh = data = _ProgressFile(stream, size, self.log)
                headers.update({"Content-Type": "application/octet-stream", "Content-Length": str(size)})
            else:
                data = json.dumps(body).encode() if body is not None else None
                if data is not None:
                    headers["Content-Type"] = "application/json"
            try:
                req = urllib.request.Request(url, data=data, method=method, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return _parse(r.read())
            except urllib.error.HTTPError as e:
                detail = e.read()[:400].decode("utf-8", "replace")
                if e.code < 500 and e.code != 429:
                    raise ApiError(e.code, f"{method} {path.split('?')[0]} -> {e.code} {detail}")
                reason = f"HTTP {e.code}"
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                reason = str(e)
            finally:
                if fh is not None:
                    fh.close()
            if attempt < self.retries:
                wait = min(5 * 2 ** (attempt - 1), 120)
                self.log(f"  retry {attempt}/{self.retries - 1}: {method} {path.split('?')[0]} -> {reason}; waiting {wait}s")
                self.sleep(wait)
        raise ApiError(0, f"{method} {path.split('?')[0]} failed after {self.retries} tries ({reason})")


# ----------------------------------------------------------------------------- manifest
def build_manifest(d, globs=("*",), exclude=(), log=print):
    skip = tuple(DEFAULT_EXCLUDE) + tuple(exclude)
    files = []
    for name in sorted(os.listdir(d)):
        path = os.path.join(d, name)
        if name.startswith(".") or not os.path.isfile(path):
            continue
        if not any(fnmatch.fnmatch(name, g) for g in globs) or any(fnmatch.fnmatch(name, x) for x in skip):
            continue
        if name.lower().endswith(".npy"):
            log(f"  skip {name}: .npy is not accepted by the platform; convert to parquet first")
            continue
        size = os.path.getsize(path)
        if size > SHARD_WARN_BYTES:
            log(f"  warning: {name} is {size / 1e6:.0f} MB; shard files to <= {SHARD_WARN_BYTES // 1_000_000} MB")
        log(f"  hashing {name} ({size / 1e6:.1f} MB)")
        files.append({"filename": name, "bytes": size, "sha256": sha256_file(path)})
    if not files:
        raise UsageError(f"no uploadable files found in {d}")
    return {"generated_utc": utc_now(), "files": files}


def load_manifest(d):
    m = read_json(os.path.join(d, "manifest.json"))
    if not isinstance(m.get("files"), list) or not m["files"]:
        raise UsageError(f"{d}/manifest.json has no 'files' list")
    return m


# ----------------------------------------------------------------------------- journal
def done_keys(journal):
    """(dataset_id, sha256) pairs recorded as done. A torn last line is ignored."""
    keys = set()
    if os.path.exists(journal):
        with open(journal, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("status") == "done":
                        keys.add((r["dataset_id"], r["sha256"]))
                except (ValueError, KeyError, AttributeError):
                    pass
    return keys


# ----------------------------------------------------------------------------- commands
def load_state(d):
    info = read_json(os.path.join(d, STATE_FILE))
    if not info.get("id"):
        raise UsageError(f"{d}/{STATE_FILE} has no dataset id; run `create` first")
    return info


def create_dataset(client, card_path, readme_path, d, visibility, modality, dry_run, log):
    card = read_json(card_path)
    name = card.get("name")
    if not name:
        raise UsageError(f"{card_path} needs a 'name'")
    tags = card.get("tags") or []
    if len(tags) > 10:
        raise UsageError("a dataset accepts at most 10 tags")
    state = os.path.join(d, STATE_FILE)
    if os.path.exists(state):
        info = read_json(state)
        log(f"already created: {info.get('owner_username')}/{info.get('slug')} (state file {state}); nothing to do")
        return EXIT_OK
    payload = {"name": name, "modality": modality, "visibility": visibility}
    for k in ("description", "license"):
        if card.get(k):
            payload[k] = card[k]
    if tags:
        payload["tags"] = tags
    if readme_path:
        try:
            with open(readme_path, encoding="utf-8") as f:
                payload["readme"] = f.read()
        except OSError as e:
            raise UsageError(f"cannot read readme: {e}")
    if dry_run:
        shown = {k: (f"<{len(v)} chars>" if k == "readme" else v) for k, v in payload.items()}
        log(f"dry-run: would POST /datasets {json.dumps(shown, ensure_ascii=False)}")
        return EXIT_OK
    if visibility != "private":
        log(f"note: creating a {visibility} dataset")
    ds = unwrap(client.call("POST", "/datasets", payload))
    if not isinstance(ds, dict) or not ds.get("id"):
        raise ApiError(0, "POST /datasets returned no dataset id")
    info = {"id": ds["id"], "slug": ds.get("slug"), "owner_username": ds.get("owner_username")}
    write_json_atomic(state, info)
    log(f"created {visibility} dataset {info['owner_username']}/{info['slug']} ({info['id']}); state saved to {state}")
    return EXIT_OK


def upload_dir(client, d, journal, dry_run, log):
    if dry_run:
        try:
            ds = load_state(d)
        except UsageError:
            ds = {"id": "DRY-RUN", "slug": "(not created yet)"}
    else:
        ds = load_state(d)
    if os.path.exists(os.path.join(d, "manifest.json")):
        files = load_manifest(d)["files"]
    elif dry_run:
        files = build_manifest(d, log=log)["files"]
    else:
        log("manifest.json missing; building it")
        m = build_manifest(d, log=log)
        write_json_atomic(os.path.join(d, "manifest.json"), m)
        files = m["files"]
    done = done_keys(journal)
    left = [f for f in files if (ds["id"], f["sha256"]) not in done]
    total_bytes = sum(f["bytes"] for f in files)
    left_bytes = sum(f["bytes"] for f in left)
    state = f"resuming: {len(files) - len(left)} done, {len(left)} left" if len(left) < len(files) else f"fresh start, {len(left)} left"
    log(f"== {ds.get('slug')}: {len(files)} files, {total_bytes / 1e6:.0f} MB | {state}")
    if not dry_run:
        log(f"journal {journal} | re-run the same command to resume")
    counts = {"uploaded": 0, "dedup": 0, "failed": 0}
    failed, t_start, sent = [], time.time(), 0
    for i, f in enumerate(left, 1):
        name, size, sha = f["filename"], f["bytes"], f["sha256"]
        if dry_run:
            log(f"  [{i}/{len(left)}] dry-run: would upload {name} ({size / 1e6:.1f} MB, sha256 {sha[:12]}...)")
            continue
        t0 = time.time()
        try:
            path = os.path.join(d, name)
            if not os.path.isfile(path) or os.path.getsize(path) != size:
                raise ApiError(0, f"{name}: missing or size differs from manifest; rebuild manifest.json")
            pre = unwrap(client.call("POST", f"/datasets/{ds['id']}/upload/presign",
                                     {"files": [{"filename": name, "sha256_hash": sha, "file_size": size}]}))
            urls = pre.get("presigned_urls") or []
            if sha in (pre.get("duplicates") or []):
                status = "dedup"
            elif not urls:
                raise ApiError(0, f"{name}: presign returned no upload URL")
            else:
                u = urls[0]
                client.call("PUT", u["upload_url"], stream=path, size=size)
                client.call("POST", f"/datasets/{ds['id']}/upload/confirm",
                            {"items": [{"object_key": u["object_key"], "sha256_hash": sha, "filename": name, "file_size": size}]})
                status = "uploaded"
        except ApiError as e:
            if e.status in (401, 403):
                raise  # wrong or under-scoped key: every file would fail the same way
            counts["failed"] += 1
            failed.append(name)
            log(f"  [{i}/{len(left)}] FAILED {name}: {e}")
            append_jsonl(journal, {"dataset_id": ds["id"], "file": name, "sha256": sha, "status": "failed",
                                   "error": str(e)[:300], "ts": utc_now()})
            continue
        counts[status] += 1
        sent += size
        dt = max(time.time() - t0, 1e-6)
        elapsed = max(time.time() - t_start, 1e-6)
        eta = (left_bytes - sent) / (sent / elapsed) if sent else 0
        log(f"  [{i}/{len(left)}] {name} {status} {size / 1e6:.0f} MB in {dt:.0f}s ({size / 1e6 / dt:.1f} MB/s) "
            f"| {100 * sent / max(left_bytes, 1):.0f}% | ETA {int(eta)}s | failed {counts['failed']}")
        append_jsonl(journal, {"dataset_id": ds["id"], "file": name, "sha256": sha, "status": "done", "ts": utc_now()})
    log(f"upload end | uploaded {counts['uploaded']}, dedup {counts['dedup']}, failed {counts['failed']}, "
        f"skipped (journal) {len(files) - len(left)} | {int(time.time() - t_start)}s")
    if failed:
        log(f"failed files: {failed}; re-run to retry them")
    return EXIT_FAIL if failed else EXIT_OK


def verify_dir(client, d, log):
    ds = load_state(d)
    want = {f["sha256"]: f["filename"] for f in load_manifest(d)["files"]}
    got, cursor, seen = {}, None, set()
    while True:
        q = f"/datasets/{ds['id']}/items?limit=200" + (f"&cursor={cursor}" if cursor else "")
        page = client.call("GET", q)
        page = unwrap(page) if isinstance(page, dict) else {}
        for it in page.get("items", []):
            got[it["sha256_hash"]] = (it["original_filename"], it["status"])
        cursor = page.get("next_cursor")
        if not cursor or cursor in seen:
            break
        seen.add(cursor)
    missing = [want[h] for h in want if h not in got]
    extra = [got[h][0] for h in got if h not in want]
    not_ready = [v[0] for v in got.values() if v[1] != "ready"]
    ok = not (missing or extra or not_ready)
    log(f"verify {ds.get('slug')}: server {len(got)} / manifest {len(want)} | missing {missing} | extra {extra} "
        f"| not ready {not_ready} -> {'OK' if ok else 'FAIL'}")
    return ok


# ----------------------------------------------------------------------------- CLI
def make_parser():
    p = argparse.ArgumentParser(prog="evren_dataset_upload.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--log", help=f"progress log file (default DIR/{DEFAULT_LOG})")
    common.add_argument("--retries", type=int, default=4, help="attempts per request on 5xx/429/network errors")

    m = sub.add_parser("manifest", parents=[common], help="build DIR/manifest.json (filename, bytes, sha256)")
    m.add_argument("dir")
    m.add_argument("--glob", action="append", help="only files matching this pattern (repeatable; default all)")
    m.add_argument("--exclude", action="append", default=[], help=f"extra exclude pattern (default excludes: {', '.join(DEFAULT_EXCLUDE)})")

    c = sub.add_parser("create", parents=[common], help="create the dataset and write DIR/" + STATE_FILE)
    c.add_argument("--card", required=True, help="card.json: name, description, license, tags")
    c.add_argument("--readme", help="dataset README (markdown)")
    c.add_argument("--dir", help="dataset directory for the state file (default: the card's directory)")
    c.add_argument("--visibility", default="private", choices=VISIBILITIES)
    c.add_argument("--modality", default="NLP", choices=MODALITIES)
    c.add_argument("--dry-run", action="store_true", help="print the request, change nothing")

    u = sub.add_parser("upload", parents=[common], help="upload files listed in DIR/manifest.json (resumable)")
    u.add_argument("dir")
    u.add_argument("--journal", help=f"journal file (default DIR/{DEFAULT_JOURNAL})")
    u.add_argument("--dry-run", action="store_true", help="print the plan, no network, no writes")

    v = sub.add_parser("verify", parents=[common], help="compare server items with the manifest by SHA-256")
    v.add_argument("dir")
    return p


def run(args):
    d = args.dir if getattr(args, "dir", None) else os.path.dirname(os.path.abspath(args.card))
    dry = getattr(args, "dry_run", False)
    log = Log(None if dry else (args.log or os.path.join(d, DEFAULT_LOG)))
    if args.cmd == "manifest":
        m = build_manifest(args.dir, args.glob or ("*",), args.exclude, log)
        write_json_atomic(os.path.join(args.dir, "manifest.json"), m)
        log(f"wrote {os.path.join(args.dir, 'manifest.json')} ({len(m['files'])} files)")
        return EXIT_OK
    client = None if dry else Client(get_key(), log, retries=args.retries)
    if args.cmd == "create":
        return create_dataset(client, args.card, args.readme, d, args.visibility, args.modality, dry, log)
    if args.cmd == "upload":
        journal = args.journal or os.path.join(d, DEFAULT_JOURNAL)
        return upload_dir(client, d, journal, dry, log)
    return EXIT_OK if verify_dir(client, d, log) else EXIT_FAIL


def main(argv=None):
    args = make_parser().parse_args(argv)
    try:
        return run(args)
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_USAGE
    except ApiError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_FAIL
    except KeyboardInterrupt:
        print("interrupted; re-run the same command to resume", file=sys.stderr)
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
