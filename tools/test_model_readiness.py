"""Offline integrity regressions; files are synthetic and never model-loaded."""
import hashlib
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import model_setup as setup


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        root_patch = patch.object(setup, "repo_root", lambda: self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        network = patch.object(setup, "urlopen", side_effect=AssertionError("No network in integrity tests"))
        network.start()
        self.addCleanup(network.stop)
        setup.cached_sha256.cache_clear()

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def model_files(self, data=b"weights"):
        for directory, names in (
            (setup.asr_model_dir(), ("config.json", "v3_vocab.txt", "v3_ctc.onnx", "v3_ctc.int8.onnx")),
            (setup.punct_model_dir(), ("config.json", "tokenizer.json", "openvino_model.xml", "openvino_model.bin")),
            (self.root / "models/asr/gigaam-v3-ctc-openvino-int8-calib96",
             ("v3_ctc_bucket400_nncf_int8.xml", "v3_ctc_bucket400_nncf_int8.bin")),
        ):
            directory.mkdir(parents=True, exist_ok=True)
            for name in names:
                payload = b"{}" if data and name.endswith(".json") else data
                (directory / name).write_bytes(payload)

    def manifest(self, relative, expected, profile, component):
        artifact = {"install_path": relative, "repo_path": relative, "size_bytes": len(expected),
                    "sha256": hashlib.sha256(expected).hexdigest(), "profile_id": profile, "component": component}
        return {"repo_id": setup.ARTIFACT_MODEL_REPO, "artifacts": [artifact]}

    def test_empty_files_are_never_ready(self):
        self.model_files(b"")
        self.assertFalse(setup.asr_model_ready())
        self.assertFalse(setup.asr_openvino_model_ready())
        self.assertFalse(setup.asr_openvino_artifact_model_ready())
        self.assertFalse(setup.punct_model_ready())

    def test_invalid_config_json_is_not_ready(self):
        self.model_files()
        (setup.asr_model_dir() / "config.json").write_bytes(b"broken")
        self.assertFalse(setup.asr_model_ready())

    def test_manifest_size_failure_has_no_exists_fallback(self):
        self.model_files()
        path = "models/asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.bin"
        manifest = self.manifest(path, b"much longer weights", setup.ASR_OPENVINO_NNCF_INT8_PROFILE, "asr")
        with patch.object(setup, "load_cached_artifact_manifest", return_value=manifest):
            self.assertFalse(setup.asr_openvino_artifact_model_ready())

    def test_manifest_cannot_hide_missing_required_companion_file(self):
        self.model_files()
        path = "models/asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.bin"
        manifest = self.manifest(path, b"weights", setup.ASR_OPENVINO_NNCF_INT8_PROFILE, "asr")
        (setup.asr_model_dir() / "v3_vocab.txt").unlink()
        with patch.object(setup, "load_cached_artifact_manifest", return_value=manifest):
            self.assertFalse(setup.asr_openvino_artifact_model_ready())

    def test_same_size_corruption_is_checked_by_background_ensure(self):
        self.model_files()
        path = "models/asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.bin"
        manifest = self.manifest(path, b"WEIGHTS", setup.ASR_OPENVINO_NNCF_INT8_PROFILE, "asr")
        with patch.object(setup, "load_cached_artifact_manifest", return_value=manifest):
            self.assertTrue(setup.asr_openvino_artifact_model_ready())
            self.assertFalse(setup.asr_openvino_artifact_model_ready(verify_hash=True))
            with patch.object(setup, "ensure_profile_artifacts") as repair:
                setup.ensure_asr_openvino_model(profile_id=setup.ASR_OPENVINO_NNCF_INT8_PROFILE)
                repair.assert_called_once()

    def test_punctuation_corruption_uses_artifact_repair(self):
        self.model_files()
        relative = "models/openvino/RUPunct_big_fp16_static128/openvino_model.bin"
        expected = b"WEIGHTS"
        manifest = self.manifest(relative, expected, setup.PUNCT_OPENVINO_FP16_PROFILE, "punctuation")
        with patch.object(setup, "load_cached_artifact_manifest", return_value=manifest):
            self.assertTrue(setup.punct_model_ready())
            def repair(*_args):
                self.write(relative, expected)
            with patch.object(setup, "ensure_profile_artifacts", side_effect=repair) as download:
                self.assertEqual(setup.ensure_punct_model(), setup.punct_model_dir())
                download.assert_called_once()

    def test_hash_cache_is_invalidated_by_file_changes(self):
        expected = b"weights"
        path = self.write("weights.bin", expected)
        artifact = self.manifest("weights.bin", expected, "test", "asr")["artifacts"][0]
        real_hash = setup.sha256_file
        with patch.object(setup, "sha256_file", wraps=real_hash) as hasher:
            self.assertTrue(setup.artifact_ready(artifact))
            self.assertTrue(setup.artifact_ready(artifact))
            self.assertEqual(hasher.call_count, 1)
            path.write_bytes(b"WEIGHTS")
            self.assertFalse(setup.artifact_ready(artifact))
            self.assertEqual(hasher.call_count, 2)

    def test_broken_cached_manifest_is_recoverable(self):
        path = setup.artifact_manifest_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        for value in (b"broken", b"[]", b"\xff"):
            path.write_bytes(value)
            self.assertIsNone(setup.load_cached_artifact_manifest())

    def test_direct_asr_redownloads_invalid_config_only(self):
        self.model_files()
        (setup.asr_model_dir() / "config.json").write_bytes(b"broken")
        def fake_download(_url, target, **_kwargs):
            temp = target.with_suffix(".download")
            temp.write_bytes(b"{}")
            return temp
        with patch.object(setup, "download_url_to_file", side_effect=fake_download) as download:
            setup.ensure_asr_model()
            self.assertEqual(download.call_count, 1)
        self.assertTrue(setup.asr_model_ready())

    def test_malformed_manifest_metadata_is_unavailable_not_an_exception(self):
        self.model_files()
        base = dict(profile_id=setup.PUNCT_OPENVINO_FP16_PROFILE, component="punctuation", repo_path="model.bin")
        values = [{}, {"artifacts": "text"}, {"artifacts": [None]}, {"artifacts": [base]},
                  {"artifacts": [dict(base, install_path="../escape.bin")]},
                  {"artifacts": [dict(base, install_path="model.bin", size_bytes="bad")]},
                  {"artifacts": [dict(base, install_path="model.bin", sha256="bad")]}]
        for manifest in values:
            manifest["repo_id"] = setup.ARTIFACT_MODEL_REPO
            with self.subTest(manifest=manifest), patch.object(setup, "load_cached_artifact_manifest", return_value=manifest):
                self.assertFalse(setup.valid_artifact_manifest(manifest))
                self.assertFalse(setup.punct_model_ready())
                self.assertFalse(setup.asr_openvino_artifact_model_ready())
        for artifact in (None, {}, {"install_path": "../escape.bin"}):
            self.assertFalse(setup.artifact_ready(artifact))

    def test_invalid_cached_schema_is_replaced_by_valid_remote_manifest(self):
        manifest = self.manifest("model.bin", b"weights", "test", "asr")
        with patch.object(setup, "load_cached_artifact_manifest", return_value={"repo_id": setup.ARTIFACT_MODEL_REPO, "artifacts": [None]}), \
             patch.object(setup, "read_json_url", return_value=manifest) as download:
            self.assertEqual(setup.load_remote_artifact_manifest(), manifest)
            download.assert_called_once()

    def invalid_manifests(self, valid):
        for key, values in (("repo_path", (None, "", " ", 12, [], "../escape.bin", "/model.bin", ".", "C:/model.bin", "bad\x00.bin", "model.bin/", "./model.bin", "folder/./model.bin")),
                            ("repo_id", (None, "", "Other/models", 12, []))):
            for value in values:
                invalid = copy.deepcopy(valid)
                owner = invalid["artifacts"][0] if key == "repo_path" else invalid
                if value is None:
                    owner.pop(key)
                else:
                    owner[key] = value
                yield key, value, invalid

    def test_missing_source_metadata_is_unavailable_and_rejected_remotely(self):
        self.model_files()
        for profile, component, relative in (
            (setup.PUNCT_OPENVINO_FP16_PROFILE, "punctuation", "models/openvino/RUPunct_big_fp16_static128/openvino_model.bin"),
            (setup.ASR_OPENVINO_NNCF_INT8_PROFILE, "asr", "models/asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.bin"),
        ):
            valid = self.manifest(relative, b"weights", profile, component)
            for key, value, invalid in self.invalid_manifests(valid):
                with self.subTest(component=component, key=key, value=value):
                    self.assertFalse(setup.valid_artifact_manifest(invalid))
                    with patch.object(setup, "load_cached_artifact_manifest", return_value=invalid):
                        self.assertFalse(setup.punct_model_ready(verify_hash=True))
                        self.assertFalse(setup.asr_openvino_artifact_model_ready(verify_hash=True))
                    with patch.object(setup, "read_json_url", return_value=invalid):
                        with self.assertRaisesRegex(RuntimeError, "Invalid model artifact manifest"):
                            setup.load_remote_artifact_manifest(force=True)

    def test_invalid_source_cache_refreshes_and_installs_with_hash_checks(self):
        self.model_files()
        for profile, component, relative in (
            (setup.PUNCT_OPENVINO_FP16_PROFILE, "punctuation", "models/openvino/RUPunct_big_fp16_static128/openvino_model.bin"),
            (setup.ASR_OPENVINO_NNCF_INT8_PROFILE, "asr", "models/asr/gigaam-v3-ctc-openvino-int8-calib96/v3_ctc_bucket400_nncf_int8.bin"),
        ):
            valid = self.manifest(relative, b"weights", profile, component)
            target = self.root / relative
            for key, value, invalid in self.invalid_manifests(valid):
                for payload in (b"weights", b"WEIGHTS"):
                    with self.subTest(component=component, key=key, value=value, payload=payload):
                        target.unlink(missing_ok=True)
                        cache = setup.artifact_manifest_cache_path()
                        cache.parent.mkdir(parents=True, exist_ok=True)
                        cache.write_text(json.dumps(invalid), encoding="utf-8")
                        def fake_download(url, path, **kwargs):
                            self.assertEqual(url, setup.artifact_url(relative))
                            self.assertEqual(kwargs["expected_size"], len(payload))
                            temporary = path.with_name(path.name + ".download")
                            temporary.write_bytes(payload)
                            return temporary
                        with patch.object(setup, "read_json_url", return_value=valid) as remote, \
                             patch.object(setup, "download_url_to_file", side_effect=fake_download) as download, \
                             patch.object(setup.time, "sleep", lambda _seconds: None):
                            if payload == b"weights":
                                self.assertEqual(setup.ensure_profile_artifacts(profile, component), valid)
                                self.assertEqual(target.read_bytes(), payload)
                                download.assert_called_once()
                            else:
                                with self.assertRaisesRegex(RuntimeError, "SHA256 mismatch"):
                                    setup.ensure_profile_artifacts(profile, component)
                                self.assertFalse(target.exists())
                                self.assertFalse(target.with_name(target.name + ".download").exists())
                            remote.assert_called_once()
                        self.assertEqual(setup.load_cached_artifact_manifest(), valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
