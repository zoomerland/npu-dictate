"""Hermetic range/partial/install checks: synthetic bytes and fake HTTP only."""
import hashlib
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import model_setup as setup


URL = "https://example.invalid/model"
DATA = b"abcdefghij"
ETAG = '"revision-one"'


class Response:
    def __init__(self, chunks, status=200, **headers):
        self.chunks = iter(chunks)
        self.status = status
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size):
        value = next(self.chunks, b"")
        if isinstance(value, Exception):
            raise value
        return value


def full(data=DATA, etag=ETAG):
    headers = {"Content-Length": str(len(data))}
    if etag is not None:
        headers["ETag"] = etag
    return Response([data], **headers)


def tail(data=DATA[4:], **changes):
    headers = {"Content-Length": "6", "Content-Range": "bytes 4-9/10", "ETag": ETAG}
    headers.update(changes)
    return Response([data], status=206, **headers)


class ResumableDownloadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="resume-test-")
        self.addCleanup(temp.cleanup)
        self.raw_root = Path(temp.name)
        self.root = self.raw_root.resolve()
        self.target = self.root / "model.bin"
        self.partial, self.metadata = setup._download_paths(self.target)
        guard = patch.object(setup, "urlopen", side_effect=AssertionError("Real network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)
        sleep = patch.object(setup.time, "sleep", lambda _seconds: None)
        sleep.start()
        self.addCleanup(sleep.stop)

    def download(self, responses, **kwargs):
        with patch.object(setup, "urlopen", side_effect=responses) as network:
            result = setup.download_url_to_file(kwargs.pop("url", URL), self.target, **kwargs)
        return result, network

    def seed(self, **kwargs):
        response = Response([DATA[:4], URLError("interrupted")],
                            **{"Content-Length": "10", "ETag": ETAG})
        with self.assertRaises(URLError):
            self.download([response], **kwargs)
        self.assertEqual(self.partial.read_bytes(), DATA[:4])
        self.assertTrue(self.metadata.exists())

    def assert_no_state(self):
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.metadata.exists())
        self.assertFalse(self.metadata.with_name(self.metadata.name + ".tmp").exists())

    def test_interruption_and_later_invocation_resume(self):
        self.seed(expected_size=10)
        temporary, network = self.download([tail()], expected_size=10)
        request = network.call_args.args[0]
        self.assertEqual(request.get_header("Range"), "bytes=4-")
        self.assertEqual(request.get_header("If-range"), ETAG)
        self.assertEqual(request.get_header("Accept-encoding"), "identity")
        self.assertEqual(temporary.read_bytes(), DATA)
        self.assertFalse(self.metadata.exists())
        self.assertFalse(self.target.exists())

    def test_install_retry_resumes_and_installs_atomically(self):
        artifact = self.artifact()
        first = Response([DATA[:4], TimeoutError("lost connection")],
                         **{"Content-Length": "10", "ETag": ETAG})
        with patch.object(setup, "urlopen", side_effect=[first, tail()]) as network:
            result = setup.install_artifact(artifact, root=self.root)
        self.assertEqual(result.read_bytes(), DATA)
        self.assertEqual(network.call_count, 2)
        self.assertEqual(network.call_args.args[0].get_header("Range"), "bytes=4-")
        self.assert_no_state()

    def test_ignored_range_or_changed_representation_200_restarts(self):
        for etag in (ETAG, '"revision-two"', None, 'W/"revision-one"'):
            with self.subTest(etag=etag):
                self.seed()
                temporary, _ = self.download([full(b"0123456789", etag)])
                self.assertEqual(temporary.read_bytes(), b"0123456789")

    def test_changed_validator_on_206_is_rejected(self):
        self.seed()
        with self.assertRaises(RuntimeError):
            self.download([tail(ETag='"revision-two"')])
        self.assert_no_state()

    def test_invalid_ranges_headers_and_encoding_are_rejected(self):
        cases = [{"Content-Range": value} for value in
                 ("", "bytes 3-9/10", "bytes 5-9/10", "bytes 4-8/10", "bytes 4-10/11",
                  "bytes 4-9/*", "bytes */10", "bytes 9-4/10", "bytes 4-9/9", "garbage")]
        cases += [{"Content-Length": "5"}, {"Content-Length": "7"},
                  {"Content-Length": "-1"}, {"Content-Length": "invalid"},
                  {"ETag": None}, {"ETag": 'W/"revision-one"'},
                  {"Content-Encoding": "gzip"}, {"Content-Type": "multipart/byteranges"}]
        for headers in cases:
            with self.subTest(headers=headers):
                self.seed()
                with self.assertRaises(RuntimeError):
                    self.download([tail(**headers)])
                self.assert_no_state()

    def test_range_without_content_length_still_counts_exact_body(self):
        self.seed()
        response = tail()
        del response.headers["Content-Length"]
        temporary, _ = self.download([response])
        self.assertEqual(temporary.read_bytes(), DATA)

    def test_truncated_range_retains_only_valid_prefix(self):
        self.seed()
        with self.assertRaisesRegex(RuntimeError, "size mismatch"):
            self.download([tail(DATA[4:7])])
        state = json.loads(self.metadata.read_text())
        self.assertEqual(state["bytes"], 7)
        self.assertEqual(state["prefix_sha256"], hashlib.sha256(DATA[:7]).hexdigest())
        response = Response([DATA[7:]], status=206,
                            **{"Content-Range": "bytes 7-9/10", "ETag": ETAG, "Content-Length": "3"})
        temporary, network = self.download([response])
        self.assertEqual(network.call_args.args[0].get_header("Range"), "bytes=7-")
        self.assertEqual(temporary.read_bytes(), DATA)

    def test_overlong_body_is_not_written_and_state_is_cleared(self):
        for response in (full(DATA + b"x"), tail(DATA[4:] + b"x")):
            response.headers["Content-Length"] = "10" if response.status == 200 else "6"
            with self.subTest(status=response.status):
                self.seed()
                with self.assertRaisesRegex(RuntimeError, "exceeds declared size"):
                    self.download([response])
                self.assert_no_state()

    def test_no_or_weak_or_malformed_validator_never_resumes(self):
        for etag in (None, 'W/"weak"', "unquoted", '"bad\nvalue"'):
            headers = {"Content-Length": "10"}
            if etag is not None:
                headers["ETag"] = etag
            with self.subTest(etag=etag):
                with self.assertRaises(URLError):
                    self.download([Response([DATA[:4], URLError("lost")], **headers)])
                self.assert_no_state()
                temporary, network = self.download([full()])
                self.assertIsNone(network.call_args.args[0].get_header("Range"))
                self.assertEqual(temporary.read_bytes(), DATA)

    def test_unknown_total_does_not_persist_resume_state(self):
        with self.assertRaises(URLError):
            self.download([Response([DATA[:4], URLError("lost")], ETag=ETAG)])
        self.assert_no_state()

    def test_arbitrary_old_partial_direct_download_is_not_trusted(self):
        self.partial.write_bytes(b"unrelated")
        temporary, network = self.download([full()])
        self.assertIsNone(network.call_args.args[0].get_header("Range"))
        self.assertEqual(temporary.read_bytes(), DATA)

    def test_stale_source_size_or_expected_hash_restarts(self):
        for changes in ({"url": URL + "?new-source"}, {"expected_size": 11},
                        {"expected_sha256": "a" * 64}):
            with self.subTest(changes=changes):
                self.seed()
                data = DATA + b"x" if changes.get("expected_size") == 11 else DATA
                temporary, network = self.download([full(data)], **changes)
                self.assertIsNone(network.call_args.args[0].get_header("Range"))
                self.assertEqual(temporary.read_bytes(), data)

    def test_corrupt_or_changed_metadata_never_appends(self):
        for payload in ("{bad json", "[]", "null", "x" * 9000):
            with self.subTest(payload=payload[:20]):
                self.seed()
                self.metadata.write_text(payload, encoding="utf-8")
                temporary, network = self.download([full()])
                self.assertIsNone(network.call_args.args[0].get_header("Range"))
                self.assertEqual(temporary.read_bytes(), DATA)
        for key, value in (("bytes", 5), ("total", 3), ("version", 2),
                           ("version", True), ("expected_size", False),
                           ("etag", 'W/"revision-one"'), ("prefix_sha256", "bad")):
            with self.subTest(key=key):
                self.seed()
                state = json.loads(self.metadata.read_text())
                state[key] = value
                self.metadata.write_text(json.dumps(state), encoding="utf-8")
                _, network = self.download([full()])
                self.assertIsNone(network.call_args.args[0].get_header("Range"))

    def test_same_size_modified_prefix_restarts(self):
        self.seed()
        self.partial.write_bytes(b"XXXX")
        temporary, network = self.download([full()])
        self.assertIsNone(network.call_args.args[0].get_header("Range"))
        self.assertEqual(temporary.read_bytes(), DATA)

    def test_metadata_does_not_store_source_credentials(self):
        url = "https://user:password@example.invalid/model?token=private"
        self.seed(url=url)
        saved = self.metadata.read_text()
        for secret in (url, "password", "private", "example.invalid"):
            self.assertNotIn(secret, saved)

    def test_416_has_one_full_fallback_not_local_completion(self):
        self.seed()
        error = HTTPError(URL, 416, "range", {}, None)
        temporary, network = self.download([error, full(b"replacement")])
        self.assertEqual(network.call_count, 2)
        self.assertIsNone(network.call_args.args[0].get_header("Range"))
        self.assertEqual(temporary.read_bytes(), b"replacement")

    def test_repeated_416_is_bounded(self):
        self.seed()
        with patch.object(setup, "urlopen", side_effect=[HTTPError(URL, 416, "range", {}, None),
                                                        HTTPError(URL, 416, "again", {}, None)]) as network:
            with self.assertRaises(HTTPError):
                setup.download_url_to_file(URL, self.target)
        self.assertEqual(network.call_count, 2)
        self.assert_no_state()

    def test_failed_request_preserves_previously_valid_state(self):
        self.seed()
        before = self.metadata.read_bytes()
        with self.assertRaises(URLError):
            self.download([URLError("offline")])
        self.assertEqual(self.metadata.read_bytes(), before)
        self.assertEqual(self.partial.read_bytes(), DATA[:4])

    def test_complete_old_partial_is_not_installed_without_fresh_response(self):
        self.seed()
        self.partial.write_bytes(DATA)
        temporary, network = self.download([full(b"0123456789")])
        self.assertIsNone(network.call_args.args[0].get_header("Range"))
        self.assertEqual(temporary.read_bytes(), b"0123456789")

    def artifact(self):
        return {"repo_path": "model.bin", "install_path": "model.bin", "size_bytes": 10,
                "sha256": hashlib.sha256(DATA).hexdigest()}

    def test_hash_mismatch_clears_resume_and_preserves_existing_target(self):
        self.target.write_bytes(b"installed")
        with patch.object(setup, "urlopen", side_effect=[full(b"XXXXXXXXXX") for _ in range(3)]) as network:
            with self.assertRaisesRegex(RuntimeError, "SHA256 mismatch"):
                setup.install_artifact(self.artifact(), root=self.root)
        self.assertEqual(network.call_count, setup.DOWNLOAD_RETRIES)
        self.assert_no_state()
        self.assertEqual(self.target.read_bytes(), b"installed")

    def test_failed_install_keeps_target_and_resumable_partial(self):
        self.target.write_bytes(b"installed")
        response = Response([DATA[:4], URLError("lost")],
                            **{"Content-Length": "10", "ETag": ETAG})
        with patch.object(setup, "urlopen", side_effect=[response, URLError("lost"), URLError("lost")]):
            with self.assertRaises(RuntimeError):
                setup.install_artifact(self.artifact(), root=self.root)
        self.assertEqual(self.target.read_bytes(), b"installed")
        self.assertEqual(self.partial.read_bytes(), DATA[:4])
        self.assertTrue(self.metadata.exists())

    def test_atomic_replace_failure_preserves_good_target(self):
        self.target.write_bytes(b"installed")
        with patch.object(setup, "urlopen", side_effect=[full() for _ in range(3)]), \
             patch.object(setup.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(RuntimeError):
                setup.install_artifact(self.artifact(), root=self.root)
        self.assertEqual(self.target.read_bytes(), b"installed")
        self.assertEqual(self.partial.read_bytes(), DATA)

    def test_callback_failure_is_not_retried_or_installed(self):
        for etag in (ETAG, None):
            with self.subTest(etag=etag):
                self.target.write_bytes(b"installed")
                headers = {"Content-Length": "10"}
                if etag is not None:
                    headers["ETag"] = etag
                error = RuntimeError("PreparationSuperseded synthetic")
                raised = False
                def callback(message):
                    nonlocal raised
                    if "%" in message and not raised:
                        raised = True
                        raise error
                with patch.object(setup, "urlopen", return_value=Response([DATA[:4], DATA[4:]], **headers)) as network:
                    with self.assertRaises(RuntimeError) as caught:
                        setup.install_artifact(self.artifact(), root=self.root, status_callback=callback)
                self.assertIs(caught.exception, error)
                self.assertEqual(network.call_count, 1)
                self.assertEqual(self.target.read_bytes(), b"installed")
                if etag:
                    self.assertEqual(self.partial.read_bytes(), DATA[:4])
                    self.assertTrue(self.metadata.exists())
                else:
                    self.assert_no_state()

    def test_callback_failure_after_complete_download_never_installs(self):
        self.target.write_bytes(b"installed")
        error = RuntimeError("superseded before verification")
        def callback(message):
            if message.startswith("Verifying models"):
                raise error
        with patch.object(setup, "urlopen", return_value=full()) as network:
            with self.assertRaises(RuntimeError) as caught:
                setup.install_artifact(self.artifact(), root=self.root, status_callback=callback)
        self.assertIs(caught.exception, error)
        self.assertEqual(network.call_count, 1)
        self.assertEqual(self.target.read_bytes(), b"installed")
        self.assertFalse(self.metadata.exists())
        self.assertFalse(self.partial.exists())

    def test_callback_failure_on_last_chunk_clears_nonresumable_candidate(self):
        self.target.write_bytes(b"installed")
        def callback(message):
            if "100%" in message:
                raise RuntimeError("superseded after last chunk")
        with patch.object(setup, "urlopen", return_value=full()) as network:
            with self.assertRaisesRegex(RuntimeError, "superseded"):
                setup.install_artifact(self.artifact(), root=self.root, status_callback=callback)
        self.assertEqual(network.call_count, 1)
        self.assertEqual(self.target.read_bytes(), b"installed")
        self.assert_no_state()

    def test_direct_asr_entrypoints_resume_and_preserve_invalid_target_until_done(self):
        for function in (setup.ensure_asr_model, setup.ensure_asr_openvino_model):
            with self.subTest(function=function.__name__), patch.object(setup, "repo_root", return_value=self.root):
                directory = setup.asr_model_dir()
                directory.mkdir(parents=True, exist_ok=True)
                config = directory / "config.json"
                config.write_bytes(b"broken")
                for name in ("v3_vocab.txt", "v3_ctc.onnx", "v3_ctc.int8.onnx"):
                    (directory / name).write_bytes(b"synthetic")
                first = Response([b"{", URLError("lost")],
                                 **{"Content-Length": "2", "ETag": ETAG})
                resumed = Response([b"}"], status=206,
                                   **{"Content-Range": "bytes 1-1/2", "Content-Length": "1", "ETag": ETAG})
                with patch.object(setup, "urlopen", side_effect=[first, resumed]) as network:
                    with self.assertRaises(URLError):
                        function()
                    self.assertEqual(config.read_bytes(), b"broken")
                    function()
                self.assertEqual(network.call_count, 2)
                self.assertEqual(network.call_args.args[0].get_header("Range"), "bytes=1-")
                self.assertEqual(config.read_bytes(), b"{}")
                partial, metadata = setup._download_paths(config)
                self.assertFalse(partial.exists())
                self.assertFalse(metadata.exists())

    def test_same_target_installs_cannot_replace_candidate_during_hash(self):
        first_hash = threading.Event()
        release_hash = threading.Event()
        second_lock_attempt = threading.Event()
        original_hash = setup.sha256_file
        original_lock = setup._download_lock
        second_data = b"0123456789"
        second_artifact = dict(self.artifact(), sha256=hashlib.sha256(second_data).hexdigest())
        first_thread_id = None
        second_thread_id = None
        def hash_file(path):
            if Path(path) == self.partial and threading.get_ident() == first_thread_id:
                first_hash.set()
                if not release_hash.wait(5):
                    raise AssertionError("Concurrent test did not release hash")
                self.assertEqual(self.partial.read_bytes(), DATA)
            return original_hash(path)
        def lock(target):
            if threading.get_ident() == second_thread_id:
                second_lock_attempt.set()
            return original_lock(target)
        def first():
            nonlocal first_thread_id
            first_thread_id = threading.get_ident()
            return setup.install_artifact(self.artifact(), root=self.root)
        def second():
            nonlocal second_thread_id
            second_thread_id = threading.get_ident()
            return setup.install_artifact(second_artifact, root=self.root)
        with patch.object(setup, "urlopen", side_effect=[full(), full(second_data)]) as network, \
             patch.object(setup, "sha256_file", side_effect=hash_file), \
             patch.object(setup, "_download_lock", side_effect=lock), \
             ThreadPoolExecutor(max_workers=2) as pool:
            job1 = pool.submit(first)
            try:
                if not first_hash.wait(5):
                    job1.result(timeout=1)
                    self.fail("First installer did not reach candidate hash")
                job2 = pool.submit(second)
                self.assertTrue(second_lock_attempt.wait(5))
                self.assertEqual(network.call_count, 1)
                self.assertEqual(self.partial.read_bytes(), DATA)
            finally:
                release_hash.set()
            self.assertEqual(job1.result(timeout=5), self.target)
            self.assertEqual(job2.result(timeout=5), self.target)
        self.assertEqual(network.call_count, 2)
        self.assertEqual(self.target.read_bytes(), second_data)
        self.assert_no_state()

    def test_equivalent_target_paths_share_ownership(self):
        self.assertIs(setup._download_lock(self.raw_root / "model.bin"),
                      setup._download_lock(self.target))
        self.assertIs(setup._download_lock(self.root / "nested" / ".." / "model.bin"),
                      setup._download_lock(self.target))

    def test_direct_asr_install_holds_ownership_through_publication(self):
        published = threading.Event()
        release = threading.Event()
        attempted = threading.Event()
        original_install = setup._install_download
        original_lock = setup._download_lock
        second_id = None
        def install(tmp, target):
            published.set()
            if not release.wait(5):
                raise AssertionError("Direct install test did not release publication")
            original_install(tmp, target)
        def lock(target):
            if threading.get_ident() == second_id:
                attempted.set()
            return original_lock(target)
        def second():
            nonlocal second_id
            second_id = threading.get_ident()
            setup._download_asr_file(URL, self.target)
        with patch.object(setup, "urlopen", return_value=full()) as network, \
             patch.object(setup, "_install_download", side_effect=install), \
             patch.object(setup, "_download_lock", side_effect=lock), \
             ThreadPoolExecutor(max_workers=2) as pool:
            job1 = pool.submit(setup._download_asr_file, URL, self.target)
            try:
                self.assertTrue(published.wait(5))
                job2 = pool.submit(second)
                self.assertTrue(attempted.wait(5))
                self.assertEqual(network.call_count, 1)
            finally:
                release.set()
            job1.result(timeout=5)
            job2.result(timeout=5)
        self.assertEqual(network.call_count, 1)
        self.assertEqual(self.target.read_bytes(), DATA)

    def test_full_headers_must_agree_with_manifest_size(self):
        self.target.write_bytes(b"installed")
        with self.assertRaisesRegex(RuntimeError, "size mismatch"):
            self.download([full()], expected_size=9)
        self.assertEqual(self.target.read_bytes(), b"installed")
        self.assert_no_state()

    def test_unsolicited_range_full_content_range_and_unexpected_status_fail(self):
        responses = (tail(), Response([DATA], **{"Content-Range": "bytes 0-9/10"}),
                     Response([], status=204), Response([DATA], **{"Content-Length": "bad"}),
                     Response([DATA], **{"Content-Encoding": "gzip"}))
        for response in responses:
            with self.subTest(status=response.status, headers=response.headers):
                with self.assertRaises(RuntimeError):
                    self.download([response])
                self.assert_no_state()

    def test_progress_counts_retained_bytes_but_speed_only_new_bytes(self):
        message = setup.format_download_status(8, 10, started_at=0, now=2, transferred=2)
        self.assertIn("80%", message)
        self.assertIn("1 B/s", message)
        message = setup.format_download_status(8, 10, started_at=0, now=2, transferred=2,
                                               overall_done=10, overall_total=20)
        self.assertIn("90%", message)
        self.assertIn("1 B/s", message)
        self.seed()
        with patch.object(setup, "format_download_status", wraps=setup.format_download_status) as status:
            self.download([tail()], status_callback=lambda _message: None)
        self.assertEqual(status.call_args.args[0], 10)
        self.assertEqual(status.call_args.kwargs["transferred"], 6)

    def test_directory_partial_or_sidecar_fails_without_cleanup(self):
        for path in (self.partial, self.metadata, self.metadata.with_name(self.metadata.name + ".tmp")):
            with self.subTest(path=path.name):
                path.mkdir()
                with self.assertRaises(OSError):
                    setup.download_url_to_file(URL, self.target)
                self.assertTrue(path.is_dir())
                path.rmdir()

    def test_sidecar_read_error_is_not_treated_as_permission_to_delete(self):
        self.seed()
        original = Path.open
        def fail(path, *args, **kwargs):
            if path == self.metadata:
                raise PermissionError("locked metadata")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", fail), self.assertRaises(PermissionError):
            setup.download_url_to_file(URL, self.target)
        self.assertEqual(self.partial.read_bytes(), DATA[:4])
        self.assertTrue(self.metadata.exists())

    def test_reparse_attribute_is_rejected_before_network_or_write(self):
        self.partial.write_bytes(b"external")
        original = Path.lstat
        def reparse(path):
            result = original(path)
            if path == self.partial:
                return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=0x400)
            return result
        with patch.object(Path, "lstat", reparse), self.assertRaises(OSError):
            setup.download_url_to_file(URL, self.target)
        self.assertEqual(self.partial.read_bytes(), b"external")

    def test_symlink_partial_or_sidecar_is_not_followed_or_deleted(self):
        external = self.root / "external.bin"
        external.write_bytes(b"external")
        for path in (self.partial, self.metadata):
            try:
                os.symlink(external, path)
            except OSError as exc:
                self.skipTest(f"Symlink creation unavailable: {exc}")
            with self.assertRaises(OSError):
                setup.download_url_to_file(URL, self.target)
            self.assertTrue(path.is_symlink())
            self.assertEqual(external.read_bytes(), b"external")
            path.unlink()

    def test_parent_directory_symlink_is_rejected(self):
        real = self.root / "real"
        real.mkdir()
        link = self.root / "linked"
        try:
            os.symlink(real, link, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Symlink creation unavailable: {exc}")
        with self.assertRaises(OSError):
            setup.download_url_to_file(URL, link / "model.bin")
        with self.assertRaises(OSError):
            setup.download_url_to_file(URL, link / ".." / "model.bin")
        self.assertEqual(list(real.iterdir()), [])

    def test_metadata_replace_failure_cannot_authorize_unchecked_append(self):
        response = Response([DATA[:4], URLError("lost")],
                            **{"Content-Length": "10", "ETag": ETAG})
        with patch.object(setup.os, "replace", side_effect=OSError("sidecar replace failed")):
            with self.assertRaises(OSError):
                self.download([response])
        self.assertFalse(self.metadata.exists())
        temporary, network = self.download([full()])
        self.assertIsNone(network.call_args.args[0].get_header("Range"))
        self.assertEqual(temporary.read_bytes(), DATA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
