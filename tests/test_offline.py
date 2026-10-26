"""Offline tests: manifest building, journal resume, dry-run, retry, verify. No network."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import evren_dataset_upload as T  # noqa: E402


class FakeClient:
    """Stands in for T.Client: records calls, simulates presign/PUT/confirm/items."""

    def __init__(self, fail_names=(), duplicates=()):
        self.calls, self.items = [], {}
        self.fail_names, self.duplicates = set(fail_names), set(duplicates)
        self._pending = {}

    def call(self, method, path, body=None, stream=None, size=None):
        self.calls.append((method, path.split("?")[0]))
        if path.endswith("/upload/presign"):
            f = body["files"][0]
            if f["filename"] in self.fail_names:
                raise T.ApiError(0, "simulated network exhaustion")
            if f["sha256_hash"] in self.duplicates:
                return {"presigned_urls": [], "duplicates": [f["sha256_hash"]]}
            key = "obj/" + f["filename"]
            self._pending[key] = f
            return {"presigned_urls": [{"filename": f["filename"], "upload_url": f"/datasets/D1/upload/put?key={key}",
                                        "object_key": key}], "duplicates": []}
        if method == "PUT":
            assert stream and os.path.getsize(stream) == size
            return {"ok": True, "size": size}
        if path.endswith("/upload/confirm"):
            for it in body["items"]:
                self.items[it["sha256_hash"]] = {"original_filename": it["filename"], "sha256_hash": it["sha256_hash"],
                                                 "status": "ready"}
            return {"created": len(body["items"])}
        if "/items" in path:
            return {"items": list(self.items.values()), "next_cursor": ""}
        raise AssertionError(f"unexpected call {method} {path}")


class NoNetwork:
    def call(self, *a, **k):
        raise AssertionError("network used during dry-run")


def make_dir(tmp):
    d = Path(tmp)
    (d / "a.parquet").write_bytes(b"A" * 100)
    (d / "b.csv").write_bytes(b"x,y\n1,2\n")
    (d / "c.jsonl").write_bytes(b'{"k":1}\n')
    for junk in ("README.md", "card.json", "vec.npy", ".hidden"):
        (d / junk).write_bytes(b"junk")
    return d


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = make_dir(self.tmp.name)
        self.logs = []
        self.log = self.logs.append
        self.journal = str(self.d / T.DEFAULT_JOURNAL)

    def tearDown(self):
        self.tmp.cleanup()

    def state(self):
        T.write_json_atomic(str(self.d / T.STATE_FILE), {"id": "D1", "slug": "demo", "owner_username": "me"})

    def manifest(self):
        m = T.build_manifest(str(self.d), log=self.log)
        T.write_json_atomic(str(self.d / "manifest.json"), m)
        return m

    def test_manifest_contents(self):
        m = self.manifest()
        names = [f["filename"] for f in m["files"]]
        self.assertEqual(names, ["a.parquet", "b.csv", "c.jsonl"])  # no README/card/.npy/hidden/manifest
        a = m["files"][0]
        self.assertEqual(a["bytes"], 100)
        self.assertEqual(a["sha256"], hashlib.sha256(b"A" * 100).hexdigest())
        self.assertTrue(any(".npy" in line for line in self.logs))

    def test_dry_run_touches_nothing(self):
        self.manifest()
        before = sorted(os.listdir(self.d))
        rc = T.upload_dir(NoNetwork(), str(self.d), self.journal, True, self.log)
        self.assertEqual(rc, T.EXIT_OK)
        self.assertEqual(sorted(os.listdir(self.d)), before)
        self.assertFalse(os.path.exists(self.journal))
        self.assertEqual(sum("dry-run: would upload" in line for line in self.logs), 3)
        card = self.d / "card.json"
        card.write_text(json.dumps({"name": "demo", "tags": ["t"], "license": "MIT"}))
        rc = T.create_dataset(NoNetwork(), str(card), None, str(self.d), "private", "NLP", True, self.log)
        self.assertEqual(rc, T.EXIT_OK)
        self.assertFalse((self.d / T.STATE_FILE).exists())

    def test_resume_after_failure(self):
        self.manifest()
        self.state()
        c1 = FakeClient(fail_names={"b.csv"})
        self.assertEqual(T.upload_dir(c1, str(self.d), self.journal, False, self.log), T.EXIT_FAIL)
        self.assertEqual(len(T.done_keys(self.journal)), 2)  # a and c done, b failed
        # simulate a crash that tore the last journal line
        with open(self.journal, "a") as f:
            f.write('{"dataset_id": "D1", "sha')
        self.assertEqual(len(T.done_keys(self.journal)), 2)
        c2 = FakeClient()
        self.assertEqual(T.upload_dir(c2, str(self.d), self.journal, False, self.log), T.EXIT_OK)
        presigned = [p for m, p in c2.calls if p.endswith("/presign")]
        self.assertEqual(len(presigned), 1)  # only b.csv retried
        self.assertTrue(any("resuming: 2 done, 1 left" in line for line in self.logs))
        c3 = FakeClient()
        self.assertEqual(T.upload_dir(c3, str(self.d), self.journal, False, self.log), T.EXIT_OK)
        self.assertEqual(c3.calls, [])  # everything journaled: no requests at all

    def test_dedup_skips_put(self):
        m = self.manifest()
        self.state()
        dup = m["files"][0]["sha256"]
        c = FakeClient(duplicates={dup})
        self.assertEqual(T.upload_dir(c, str(self.d), self.journal, False, self.log), T.EXIT_OK)
        self.assertEqual(sum(1 for m_, _ in c.calls if m_ == "PUT"), 2)

    def test_verify(self):
        self.manifest()
        self.state()
        c = FakeClient()
        T.upload_dir(c, str(self.d), self.journal, False, self.log)
        self.assertTrue(T.verify_dir(c, str(self.d), self.log))
        c.items.pop(next(iter(c.items)))
        self.assertFalse(T.verify_dir(c, str(self.d), self.log))
        self.assertIn("FAIL", self.logs[-1])

    def test_retry_on_503_then_ok(self):
        waits = []
        client = T.Client("evren_plt_test", self.log, retries=3, sleep=waits.append)
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = b'{"ok": true}'
        err = urllib.error.HTTPError("u", 503, "x", {}, io.BytesIO(b"busy"))
        with mock.patch.object(T.urllib.request, "urlopen", side_effect=[err, ok]):
            self.assertEqual(client.call("GET", "/auth/me"), {"ok": True})
        self.assertEqual(waits, [5])

    def test_4xx_not_retried_and_key_host_guard(self):
        client = T.Client("evren_plt_test", self.log, retries=3, sleep=lambda s: None)
        err = urllib.error.HTTPError("u", 403, "x", {}, io.BytesIO(b"nope"))
        with mock.patch.object(T.urllib.request, "urlopen", side_effect=[err]) as m:
            with self.assertRaises(T.ApiError) as cm:
                client.call("GET", "/datasets")
        self.assertEqual((cm.exception.status, m.call_count), (403, 1))
        with self.assertRaises(T.ApiError):
            client.call("GET", "https://example.invalid/steal")

    def test_key_validation(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(T.UsageError):
                T.get_key()
        with mock.patch.dict(os.environ, {T.ENV_KEY: "evren_llm_x"}):
            with self.assertRaises(T.UsageError):
                T.get_key()
        with mock.patch.dict(os.environ, {T.ENV_KEY: "evren_plt_x"}):
            self.assertEqual(T.get_key(), "evren_plt_x")


if __name__ == "__main__":
    unittest.main()
