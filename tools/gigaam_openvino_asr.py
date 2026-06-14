import re
import threading
from math import gcd
from pathlib import Path

import numpy as np
import openvino as ov
from onnx_asr.preprocessors.numpy_preprocessor import GigaamPreprocessorNumpy
from scipy.signal import resample_poly


DECODE_SPACE_PATTERN = re.compile(r"\A\s|\s\B|(\s)\b")


class GigaamOpenVinoCtcAsr:
    def __init__(
        self,
        model_dir,
        device="NPU",
        model_filename="v3_ctc.onnx",
        cache_dir=None,
        bucket_frames=(200, 400, 800, 1600, 3200, 6400),
    ):
        self.model_dir = Path(model_dir)
        self.device = device
        self.model_path = self.model_dir / model_filename
        self.bucket_frames = tuple(sorted(int(value) for value in bucket_frames))
        self.core = ov.Core()
        if cache_dir is not None:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            self.core.set_property({"CACHE_DIR": str(cache_dir)})

        self.preprocessor = GigaamPreprocessorNumpy("gigaam_v3")
        self.vocab, self.blank_idx = self._load_vocab(self.model_dir / "v3_vocab.txt")
        self.compiled = {}
        self.lock = threading.RLock()

    @staticmethod
    def _load_vocab(path):
        vocab = {}
        blank_idx = None
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                token, index = line.rstrip("\n").split(" ")
                index = int(index)
                token = token.replace("\u2581", " ")
                vocab[index] = token
                if token == "<blk>":
                    blank_idx = index
        if blank_idx is None:
            blank_idx = len(vocab) - 1
        return vocab, blank_idx

    @staticmethod
    def _normalize_waveform(waveform, channel=None):
        audio = np.asarray(waveform, dtype=np.float32).squeeze()
        if audio.ndim == 2:
            if channel == "mean" or channel is None:
                audio = audio.mean(axis=1)
            else:
                audio = audio[:, int(channel)]
        if audio.ndim != 1:
            raise ValueError("GigaAM OpenVINO ASR expects mono audio.")
        return np.ascontiguousarray(audio, dtype=np.float32)

    @staticmethod
    def _resample_to_16k(audio, sample_rate):
        sample_rate = int(sample_rate)
        if sample_rate == 16_000:
            return audio
        divisor = gcd(sample_rate, 16_000)
        return resample_poly(audio, 16_000 // divisor, sample_rate // divisor).astype(np.float32)

    def _features(self, waveform, sample_rate, channel=None):
        audio = self._normalize_waveform(waveform, channel)
        audio = self._resample_to_16k(audio, sample_rate)
        waveforms = audio[None, :]
        waveforms_lens = np.array([audio.shape[0]], dtype=np.int64)
        features, features_lens = self.preprocessor(waveforms, waveforms_lens)
        return np.ascontiguousarray(features, dtype=np.float32), features_lens.astype(np.int64)

    def _bucket_for(self, frames):
        for bucket in self.bucket_frames:
            if frames <= bucket:
                return bucket
        step = self.bucket_frames[-1]
        return ((int(frames) + step - 1) // step) * step

    def _compile(self, bucket):
        with self.lock:
            compiled = self.compiled.get(bucket)
            if compiled is not None:
                return compiled

            model = self.core.read_model(str(self.model_path))
            model.reshape({"features": [1, 64, bucket], "feature_lengths": [1]})
            compiled = self.core.compile_model(model, self.device)
            self.compiled[bucket] = compiled
            return compiled

    @staticmethod
    def _pad_features(features, bucket):
        frames = features.shape[2]
        if frames == bucket:
            return features
        padded = np.zeros((features.shape[0], features.shape[1], bucket), dtype=np.float32)
        padded[:, :, :frames] = features
        return padded

    def _decode(self, log_probs, encoder_lens):
        batch_tokens = log_probs.argmax(axis=-1)
        results = []
        for batch_index in range(log_probs.shape[0]):
            ids = []
            previous = self.blank_idx
            for frame_index in range(int(encoder_lens[batch_index])):
                token = int(batch_tokens[batch_index, frame_index])
                if token != self.blank_idx and token != previous:
                    ids.append(token)
                previous = token

            text = "".join(self.vocab[token] for token in ids)
            text = re.sub(DECODE_SPACE_PATTERN, lambda match: " " if match.group(1) else "", text)
            results.append(text)
        return results

    def recognize(self, waveform, *, sample_rate=16_000, channel=None, **_kwargs):
        features, features_lens = self._features(waveform, sample_rate, channel)
        frames = features.shape[2]
        bucket = self._bucket_for(frames)
        compiled = self._compile(bucket)
        features = self._pad_features(features, bucket)
        outputs = compiled({"features": features, "feature_lengths": features_lens})
        log_probs = outputs[compiled.output("log_probs")]
        encoder_lens = (features_lens - 1) // 4 + 1
        return self._decode(log_probs, encoder_lens)[0]
