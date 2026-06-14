import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import onnx_asr
import sounddevice as sd
import soundfile as sf

from gigaam_openvino_asr import GigaamOpenVinoCtcAsr


def repo_root():
    return Path(__file__).resolve().parents[1]


def default_model_dir():
    return repo_root() / "models" / "asr" / "gigaam-v3-ctc"


def default_recordings_dir():
    return repo_root() / "recordings" / "voice_benchmarks"


def load_config():
    path = repo_root() / "voice_dictation_config.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def result_to_text(result):
    if isinstance(result, str):
        return result
    if hasattr(result, "text"):
        return result.text
    if isinstance(result, dict) and "text" in result:
        return str(result["text"])
    return str(result)


def resolve_sample_rate(sample_rate, device_index):
    if sample_rate:
        return sample_rate
    info = sd.query_devices(device_index, "input")
    return int(info["default_samplerate"])


def record_audio(seconds, sample_rate, channels, device_index, countdown):
    if countdown:
        print(f"Recording starts in {countdown} seconds...", flush=True)
        time.sleep(countdown)

    print(f"Recording {seconds:.1f} seconds at {sample_rate} Hz...", flush=True)
    audio = sd.rec(
        int(seconds * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
        device=device_index,
    )
    sd.wait()
    return normalize_audio(audio)


def normalize_audio(audio):
    if audio.ndim == 2 and audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = np.squeeze(audio)
    return np.ascontiguousarray(audio, dtype=np.float32)


def save_audio(audio, sample_rate, recordings_dir, label):
    recordings_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = "".join(char if char.isalnum() else "_" for char in label).strip("_")[:48]
    stem = f"voice_benchmark_{timestamp}"
    if safe_label:
        stem = f"{stem}_{safe_label}"
    path = recordings_dir / f"{stem}.wav"
    sf.write(path, audio, sample_rate)
    return path


def load_audio(path):
    audio, sample_rate = sf.read(path, dtype="float32")
    return normalize_audio(audio), sample_rate


def run_cpu(audio, sample_rate, model_dir, quantization):
    start = time.perf_counter()
    asr = onnx_asr.load_model("gigaam-v3-ctc", model_dir, quantization=None if quantization == "fp32" else quantization)
    load_sec = time.perf_counter() - start

    start = time.perf_counter()
    text = result_to_text(asr.recognize(audio, sample_rate=sample_rate)).strip()
    infer_sec = time.perf_counter() - start
    return {
        "name": f"onnx_cpu_{quantization}",
        "load_sec": load_sec,
        "infer_sec": infer_sec,
        "text": text,
    }


def run_openvino(audio, sample_rate, model_dir, device, bucket, pad_mode):
    start = time.perf_counter()
    asr = GigaamOpenVinoCtcAsr(
        model_dir,
        device=device,
        cache_dir=repo_root() / "models" / "openvino" / "cache" / "asr_gigaam_voice_benchmark",
        bucket_frames=(bucket,),
        pad_mode=pad_mode,
    )
    load_sec = time.perf_counter() - start

    start = time.perf_counter()
    text = asr.recognize(audio, sample_rate=sample_rate).strip()
    infer_sec = time.perf_counter() - start
    actual_bucket = asr.last_bucket
    return {
        "name": f"openvino_{device.lower()}_fp32_bucket_{bucket}_{pad_mode}",
        "actual_bucket": actual_bucket,
        "pad_mode": pad_mode,
        "load_sec": load_sec,
        "infer_sec": infer_sec,
        "text": text,
    }


def print_result(result, audio_sec):
    speed = audio_sec / result["infer_sec"] if result["infer_sec"] else 0.0
    print(
        f"{result['name']}: load={result['load_sec']:.3f}s "
        f"infer={result['infer_sec']:.3f}s speed={speed:.2f}x"
        + (f" actual_bucket={result['actual_bucket']}" if "actual_bucket" in result else ""),
        flush=True,
    )
    print(f"  {result['text']}", flush=True)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    cfg = load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path)
    parser.add_argument("--label", default="")
    parser.add_argument("--seconds", type=float, default=14.0)
    parser.add_argument("--countdown", type=int, default=4)
    parser.add_argument("--sample-rate", type=int, default=int(cfg.get("sample_rate", 0) or 0))
    parser.add_argument("--channels", type=int, default=int(cfg.get("channels", 1) or 1))
    parser.add_argument("--device-index", type=int, default=cfg.get("input_device_index"))
    parser.add_argument("--buckets", default="400,800,1200,1600,2000,2400,3200,6400")
    parser.add_argument("--openvino-devices", default="NPU")
    parser.add_argument("--pad-modes", default="silence,zero,edge,min")
    parser.add_argument("--cpu-quantizations", default="int8,fp32")
    parser.add_argument("--skip-cpu", action="store_true")
    parser.add_argument("--skip-openvino", action="store_true")
    parser.add_argument("--recordings-dir", type=Path, default=default_recordings_dir())
    parser.add_argument("--model-dir", type=Path, default=default_model_dir())
    args = parser.parse_args()

    if args.file:
        audio, sample_rate = load_audio(args.file)
        audio_path = args.file
    else:
        sample_rate = resolve_sample_rate(args.sample_rate, args.device_index)
        audio = record_audio(args.seconds, sample_rate, args.channels, args.device_index, args.countdown)
        audio_path = save_audio(audio, sample_rate, args.recordings_dir, args.label)

    audio_sec = len(audio) / sample_rate if sample_rate else 0.0
    print(f"audio_path={audio_path}", flush=True)
    print(f"audio_sec={audio_sec:.3f}", flush=True)

    results = []
    if not args.skip_cpu:
        for raw_quantization in args.cpu_quantizations.split(","):
            quantization = raw_quantization.strip().lower()
            if not quantization:
                continue
            results.append(run_cpu(audio, sample_rate, args.model_dir, quantization))
            print_result(results[-1], audio_sec)

    if not args.skip_openvino:
        for raw_device in args.openvino_devices.split(","):
            device = raw_device.strip().upper()
            if not device:
                continue
            for raw_bucket in args.buckets.split(","):
                raw_bucket = raw_bucket.strip()
                if not raw_bucket:
                    continue
                bucket = int(raw_bucket)
                for raw_pad_mode in args.pad_modes.split(","):
                    pad_mode = raw_pad_mode.strip().lower()
                    if not pad_mode:
                        continue
                    results.append(run_openvino(audio, sample_rate, args.model_dir, device, bucket, pad_mode))
                    print_result(results[-1], audio_sec)

    report_path = audio_path.with_suffix(".json")
    with report_path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "audio_path": str(audio_path),
                "audio_sec": audio_sec,
                "sample_rate": sample_rate,
                "results": results,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )
    print(f"report_path={report_path}", flush=True)


if __name__ == "__main__":
    main()
