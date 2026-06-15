import re
import threading
from math import gcd
from pathlib import Path

import numpy as np
import openvino as ov
from onnx_asr.preprocessors.numpy_preprocessor import GigaamPreprocessorNumpy
from scipy.signal import resample_poly


DECODE_SPACE_PATTERN = re.compile(r"\A\s|\s\B|(\s)\b")
SILENCE_FEATURE_VALUE = float(np.log(1e-9))
PAD_MODES = {"zero", "silence", "edge", "min"}
DEFAULT_BUCKET_FRAMES = (400, 800, 1000, 1600, 3200)
GIGAAM_SAMPLE_RATE = 16_000
GIGAAM_HOP_LENGTH = GIGAAM_SAMPLE_RATE // 100
GIGAAM_WIN_LENGTH = GIGAAM_SAMPLE_RATE // 50
DEFAULT_CHUNK_OVERLAP_MS = 350
DEFAULT_SILENCE_SEARCH_MS = 700


class GigaamOpenVinoCtcAsr:
    def __init__(
        self,
        model_dir,
        device="NPU",
        model_filename="v3_ctc.onnx",
        cache_dir=None,
        bucket_frames=DEFAULT_BUCKET_FRAMES,
        pad_mode="zero",
        device_config=None,
    ):
        self.model_dir = Path(model_dir)
        self.device = device
        self.model_path = self.model_dir / model_filename
        self.bucket_frames = tuple(sorted(int(value) for value in bucket_frames))
        self.pad_mode = pad_mode if pad_mode in PAD_MODES else "zero"
        self.device_config = dict(device_config or {})
        self.core = ov.Core()
        if cache_dir is not None:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            self.core.set_property({"CACHE_DIR": str(cache_dir)})

        self.preprocessor = GigaamPreprocessorNumpy("gigaam_v3")
        self.vocab, self.blank_idx = self._load_vocab(self.model_dir / "v3_vocab.txt")
        self.compiled = {}
        self.last_bucket = None
        self.last_frames = None
        self.last_chunks = []
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
        audio = self.audio_16k(waveform, sample_rate, channel)
        return self._features_from_16k(audio)

    def audio_16k(self, waveform, sample_rate=16_000, channel=None):
        audio = self._normalize_waveform(waveform, channel)
        return self._resample_to_16k(audio, sample_rate)

    def _features_from_16k(self, audio):
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
            if self.device_config:
                compiled = self.core.compile_model(model, self.device, self.device_config)
            else:
                compiled = self.core.compile_model(model, self.device)
            self.compiled[bucket] = compiled
            return compiled

    def _pad_features(self, features, bucket):
        frames = features.shape[2]
        if frames == bucket:
            return features
        if self.pad_mode == "zero":
            pad_value = 0.0
        elif self.pad_mode == "edge" and frames > 0:
            padded = np.repeat(features[:, :, -1:], bucket, axis=2)
            padded[:, :, :frames] = features
            return padded
        elif self.pad_mode == "min":
            pad_value = float(features.min()) if frames > 0 else SILENCE_FEATURE_VALUE
        else:
            pad_value = SILENCE_FEATURE_VALUE
        padded = np.full((features.shape[0], features.shape[1], bucket), pad_value, dtype=np.float32)
        padded[:, :, :frames] = features
        return padded

    def warmup(self, buckets=None):
        warmed = []
        for bucket in tuple(buckets or self.bucket_frames):
            bucket = int(bucket)
            compiled = self._compile(bucket)
            features = np.zeros((1, 64, bucket), dtype=np.float32)
            feature_lengths = np.array([bucket], dtype=np.int64)
            compiled({"features": features, "feature_lengths": feature_lengths})
            warmed.append(bucket)
        return warmed

    @staticmethod
    def _audio_samples_for_bucket(bucket):
        return max(GIGAAM_WIN_LENGTH, (int(bucket) - 1) * GIGAAM_HOP_LENGTH + GIGAAM_WIN_LENGTH)

    @staticmethod
    def _quiet_cut(audio, start, hard_end, search_ms=DEFAULT_SILENCE_SEARCH_MS):
        frame = max(1, int(0.025 * GIGAAM_SAMPLE_RATE))
        hop = max(1, int(0.010 * GIGAAM_SAMPLE_RATE))
        min_chunk = int(0.9 * GIGAAM_SAMPLE_RATE)
        search_start = max(start + min_chunk, hard_end - int(search_ms * GIGAAM_SAMPLE_RATE / 1000))
        if search_start + frame >= hard_end:
            return hard_end

        best_pos = None
        best_rms = None
        for pos in range(search_start, hard_end - frame + 1, hop):
            window = audio[pos : pos + frame]
            rms = float(np.sqrt(np.mean(window * window))) if window.size else 0.0
            if best_rms is None or rms < best_rms:
                best_rms = rms
                best_pos = pos

        if best_pos is None:
            return hard_end
        return min(hard_end, best_pos + frame // 2)

    def _chunk_ranges(self, audio, bucket, overlap_ms=DEFAULT_CHUNK_OVERLAP_MS, prefer_silence=True):
        max_samples = self._audio_samples_for_bucket(bucket)
        total = int(audio.shape[0])
        if total <= max_samples:
            return [(0, total)]

        overlap_samples = int(max(0, overlap_ms) * GIGAAM_SAMPLE_RATE / 1000)
        overlap_samples = min(overlap_samples, max_samples // 3)
        ranges = []
        start = 0
        while start < total:
            hard_end = min(total, start + max_samples)
            if hard_end >= total:
                end = total
            elif prefer_silence:
                end = self._quiet_cut(audio, start, hard_end)
            else:
                end = hard_end

            if end <= start + GIGAAM_WIN_LENGTH:
                end = hard_end

            ranges.append((start, end))
            if end >= total:
                break

            next_start = max(0, end - overlap_samples)
            if next_start <= start:
                next_start = min(total, start + max_samples - overlap_samples)
            start = next_start

        return ranges

    @staticmethod
    def _token_key(token):
        return re.sub(r"\W+", "", token.lower())

    @classmethod
    def _stitch_texts(cls, texts):
        output = []
        for text in texts:
            tokens = [token for token in text.strip().split() if token]
            if not tokens:
                continue
            if not output:
                output.extend(tokens)
                continue

            overlap = 0
            max_overlap = min(8, len(output), len(tokens))
            output_keys = [cls._token_key(token) for token in output]
            token_keys = [cls._token_key(token) for token in tokens]
            for size in range(max_overlap, 0, -1):
                if output_keys[-size:] == token_keys[:size]:
                    overlap = size
                    break
            output.extend(tokens[overlap:])

        return " ".join(output)

    @staticmethod
    def _join_texts(texts):
        return " ".join(text.strip() for text in texts if text.strip())

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

    def _recognize_features(self, features, features_lens, bucket):
        bucket = int(bucket)
        frames = features.shape[2]
        if frames > bucket:
            step = bucket
            bucket = ((int(frames) + step - 1) // step) * step
        self.last_bucket = bucket
        self.last_frames = frames
        frames = features.shape[2]
        compiled = self._compile(bucket)
        features = self._pad_features(features, bucket)
        outputs = compiled({"features": features, "feature_lengths": features_lens})
        log_probs = outputs[compiled.output("log_probs")]
        encoder_lens = (features_lens - 1) // 4 + 1
        return self._decode(log_probs, encoder_lens)[0]

    def recognize(self, waveform, *, sample_rate=16_000, channel=None, **_kwargs):
        self.last_chunks = []
        features, features_lens = self._features(waveform, sample_rate, channel)
        return self._recognize_features(features, features_lens, self._bucket_for(features.shape[2]))

    def recognize_with_bucket(self, waveform, *, bucket, sample_rate=16_000, channel=None, **_kwargs):
        self.last_chunks = []
        features, features_lens = self._features(waveform, sample_rate, channel)
        return self._recognize_features(features, features_lens, int(bucket))

    def recognize_chunked(
        self,
        waveform,
        *,
        bucket=400,
        overlap_ms=DEFAULT_CHUNK_OVERLAP_MS,
        sample_rate=16_000,
        channel=None,
        prefer_silence=True,
        **_kwargs,
    ):
        audio = self._normalize_waveform(waveform, channel)
        audio = self._resample_to_16k(audio, sample_rate)
        bucket = int(bucket)
        ranges = self._chunk_ranges(audio, bucket, overlap_ms, prefer_silence)
        texts = []
        chunks = []

        for index, (start, end) in enumerate(ranges):
            chunk = np.ascontiguousarray(audio[start:end], dtype=np.float32)
            if chunk.shape[0] < GIGAAM_WIN_LENGTH:
                continue
            features, features_lens = self._features_from_16k(chunk)
            frames = int(features.shape[2])
            text = self._recognize_features(features, features_lens, bucket).strip()
            chunks.append(
                {
                    "index": index,
                    "start_sec": start / GIGAAM_SAMPLE_RATE,
                    "end_sec": end / GIGAAM_SAMPLE_RATE,
                    "frames": frames,
                    "bucket": self.last_bucket,
                    "text": text,
                }
            )
            if text:
                texts.append(text)

        self.last_chunks = chunks
        self.last_bucket = f"chunked:{bucket}x{len(chunks)}"
        self.last_frames = sum(chunk["frames"] for chunk in chunks)
        return self._stitch_texts(texts)

    def recognize_segments_16k(self, audio, segments, *, bucket=800):
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        bucket = int(bucket)
        texts = []
        chunks = []

        for index, (start, end) in enumerate(segments):
            start = max(0, int(start))
            end = min(int(end), int(audio.shape[0]))
            if end <= start:
                continue
            segment = np.ascontiguousarray(audio[start:end], dtype=np.float32)
            if segment.shape[0] < GIGAAM_WIN_LENGTH:
                continue
            features, features_lens = self._features_from_16k(segment)
            frames = int(features.shape[2])
            text = self._recognize_features(features, features_lens, bucket).strip()
            chunks.append(
                {
                    "index": index,
                    "start_sec": start / GIGAAM_SAMPLE_RATE,
                    "end_sec": end / GIGAAM_SAMPLE_RATE,
                    "frames": frames,
                    "bucket": self.last_bucket,
                    "text": text,
                }
            )
            if text:
                texts.append(text)

        self.last_chunks = chunks
        self.last_bucket = f"vad:{bucket}x{len(chunks)}"
        self.last_frames = sum(chunk["frames"] for chunk in chunks)
        return self._join_texts(texts)
