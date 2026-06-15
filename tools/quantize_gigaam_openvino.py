import argparse
import sys
from math import gcd
from pathlib import Path

import nncf
import numpy as np
import openvino as ov
import soundfile as sf
from scipy.signal import resample_poly

from gigaam_openvino_asr import GigaamOpenVinoCtcAsr


def repo_root():
    return Path(__file__).resolve().parents[1]


def load_audio(path):
    audio, sample_rate = sf.read(path, dtype="float32")
    if audio.ndim == 2 and audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = np.squeeze(audio)
    if int(sample_rate) != 16_000:
        divisor = gcd(int(sample_rate), 16_000)
        audio = resample_poly(audio, 16_000 // divisor, int(sample_rate) // divisor).astype(np.float32)
    return np.ascontiguousarray(audio, dtype=np.float32)


def latest_wavs(recordings_dir, limit):
    files = sorted(recordings_dir.glob("*.wav"), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[:limit]


def calibration_samples(asr, wav_files, bucket, max_samples):
    samples = []
    max_audio_samples = asr._audio_samples_for_bucket(bucket)
    for path in wav_files:
        audio = load_audio(path)
        ranges = asr._chunk_ranges(audio, bucket, overlap_ms=0, prefer_silence=True)
        for start, end in ranges:
            chunk = np.ascontiguousarray(audio[start:end], dtype=np.float32)
            if chunk.shape[0] < 320:
                continue
            features, feature_lengths = asr._features_from_16k(chunk[:max_audio_samples])
            if features.shape[2] > bucket:
                features = features[:, :, :bucket]
                feature_lengths = np.array([bucket], dtype=np.int64)
            features = asr._pad_features(features, bucket)
            samples.append({"features": features, "feature_lengths": feature_lengths.astype(np.int64)})
            if len(samples) >= max_samples:
                return samples
    return samples


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, default=repo_root() / "models" / "asr" / "gigaam-v3-ctc")
    parser.add_argument("--recordings-dir", type=Path, default=repo_root() / "recordings" / "debug_dictation")
    parser.add_argument("--output-dir", type=Path, default=repo_root() / "models" / "asr" / "gigaam-v3-ctc-openvino-int8")
    parser.add_argument("--bucket", type=int, default=400)
    parser.add_argument("--max-wavs", type=int, default=32)
    parser.add_argument("--subset-size", type=int, default=64)
    args = parser.parse_args()

    bucket = int(args.bucket)
    model_path = args.model_dir / "v3_ctc.onnx"
    wav_files = latest_wavs(args.recordings_dir, args.max_wavs)
    if not wav_files:
        raise SystemExit(f"No WAV files found in {args.recordings_dir}")

    helper = GigaamOpenVinoCtcAsr(args.model_dir, device="CPU", bucket_frames=(bucket,))
    samples = calibration_samples(helper, wav_files, bucket, args.subset_size)
    if not samples:
        raise SystemExit("No calibration samples were produced.")

    core = ov.Core()
    model = core.read_model(str(model_path))
    model.reshape({"features": [1, 64, bucket], "feature_lengths": [1]})

    dataset = nncf.Dataset(samples)
    quantized = nncf.quantize(
        model,
        dataset,
        preset=nncf.QuantizationPreset.MIXED,
        target_device=nncf.TargetDevice.NPU,
        subset_size=min(len(samples), args.subset_size),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"v3_ctc_bucket{bucket}_nncf_int8.xml"
    ov.save_model(quantized, output_path)
    print(f"saved={output_path}")
    print(f"samples={len(samples)} wavs={len(wav_files)} bucket={bucket}")


if __name__ == "__main__":
    main()
