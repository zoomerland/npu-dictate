import argparse
import sys
from math import gcd
from pathlib import Path

import nncf
import numpy as np
import onnx_asr
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


def vad_segment_ranges(vad, audio16, args):
    waveforms = audio16[None, :]
    waveforms_len = np.array([len(audio16)], dtype=np.int64)
    raw_segments = next(
        vad.segment_batch(
            waveforms,
            waveforms_len,
            16_000,
            max_speech_duration_s=float(args.vad_max_speech_s),
            min_silence_duration_ms=int(args.vad_min_silence_ms),
            speech_pad_ms=int(args.vad_speech_pad_ms),
        )
    )
    segments = []
    for start, end in raw_segments:
        start = max(0, min(len(audio16), int(start)))
        end = max(0, min(len(audio16), int(end)))
        if end > start:
            segments.append((start, end))
    if segments and args.vad_first_pad_ms:
        start, end = segments[0]
        segments[0] = (max(0, start - int(args.vad_first_pad_ms * 16)), end)
    min_samples = int(max(0, args.vad_min_segment_ms) * 16)
    if min_samples:
        segments = [(start, end) for start, end in segments if end - start >= min_samples]
    return segments


def calibration_samples(asr, wav_files, bucket, max_samples, args):
    samples = []
    max_audio_samples = asr._audio_samples_for_bucket(bucket)
    vad = onnx_asr.load_vad("silero") if args.vad_segments else None
    for path in wav_files:
        audio = load_audio(path)
        if vad is not None:
            ranges = vad_segment_ranges(vad, audio, args)
        else:
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
    parser.add_argument("--vad-segments", action="store_true")
    parser.add_argument("--vad-max-speech-s", type=float, default=3.5)
    parser.add_argument("--vad-min-silence-ms", type=int, default=80)
    parser.add_argument("--vad-speech-pad-ms", type=int, default=250)
    parser.add_argument("--vad-first-pad-ms", type=int, default=500)
    parser.add_argument("--vad-min-segment-ms", type=int, default=450)
    args = parser.parse_args()

    bucket = int(args.bucket)
    model_path = args.model_dir / "v3_ctc.onnx"
    wav_files = latest_wavs(args.recordings_dir, args.max_wavs)
    if not wav_files:
        raise SystemExit(f"No WAV files found in {args.recordings_dir}")

    helper = GigaamOpenVinoCtcAsr(args.model_dir, device="CPU", bucket_frames=(bucket,))
    samples = calibration_samples(helper, wav_files, bucket, args.subset_size, args)
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
    print(f"samples={len(samples)} wavs={len(wav_files)} bucket={bucket} vad_segments={args.vad_segments}")


if __name__ == "__main__":
    main()
