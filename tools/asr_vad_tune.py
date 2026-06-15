import argparse
import ast
from difflib import SequenceMatcher
import json
import re
import sys
import time
from math import gcd
from pathlib import Path

import numpy as np
import onnx_asr
import soundfile as sf
from scipy.signal import resample_poly

from gigaam_openvino_asr import GigaamOpenVinoCtcAsr


CONFIGS = {
    "pad300_first0_b800": {
        "bucket": 800,
        "first_pad_ms": 0,
        "vad": {"max_speech_duration_s": 7.5, "min_silence_duration_ms": 100, "speech_pad_ms": 300},
    },
    "pad300_first500_b800": {
        "bucket": 800,
        "first_pad_ms": 500,
        "vad": {"max_speech_duration_s": 7.5, "min_silence_duration_ms": 100, "speech_pad_ms": 300},
    },
    "pad300_first800_b800": {
        "bucket": 800,
        "first_pad_ms": 800,
        "vad": {"max_speech_duration_s": 7.5, "min_silence_duration_ms": 100, "speech_pad_ms": 300},
    },
    "pad300_first500_b1000": {
        "bucket": 1000,
        "first_pad_ms": 500,
        "vad": {"max_speech_duration_s": 9.5, "min_silence_duration_ms": 100, "speech_pad_ms": 300},
    },
    "lowload_s2_b200": {
        "bucket": 200,
        "first_pad_ms": 300,
        "hard_split": True,
        "overlap_ms": 180,
        "vad": {"max_speech_duration_s": 1.6, "min_silence_duration_ms": 60, "speech_pad_ms": 120},
    },
    "lowload_s25_b300": {
        "bucket": 300,
        "first_pad_ms": 450,
        "vad": {"max_speech_duration_s": 2.7, "min_silence_duration_ms": 80, "speech_pad_ms": 220},
    },
    "lowload_s3_b400": {
        "bucket": 400,
        "first_pad_ms": 500,
        "vad": {"max_speech_duration_s": 3.5, "min_silence_duration_ms": 80, "speech_pad_ms": 250},
    },
    "int8_lowload_s3_b400": {
        "bucket": 400,
        "first_pad_ms": 500,
        "model_filename": "v3_ctc.int8.onnx",
        "vad": {"max_speech_duration_s": 3.5, "min_silence_duration_ms": 80, "speech_pad_ms": 250},
    },
    "nncf_int8_lowload_s3_b400": {
        "bucket": 400,
        "first_pad_ms": 500,
        "model_filename": "../gigaam-v3-ctc-openvino-int8/v3_ctc_bucket400_nncf_int8.xml",
        "vad": {"max_speech_duration_s": 3.5, "min_silence_duration_ms": 80, "speech_pad_ms": 250},
    },
    "nncf_int8_stitch_s3_b400": {
        "bucket": 400,
        "first_pad_ms": 500,
        "model_filename": "../gigaam-v3-ctc-openvino-int8/v3_ctc_bucket400_nncf_int8.xml",
        "stitch": True,
        "vad": {"max_speech_duration_s": 3.5, "min_silence_duration_ms": 80, "speech_pad_ms": 250},
    },
    "nncf_int8_fuzzy_s3_b400": {
        "bucket": 400,
        "first_pad_ms": 500,
        "model_filename": "../gigaam-v3-ctc-openvino-int8/v3_ctc_bucket400_nncf_int8.xml",
        "stitch": True,
        "fuzzy_stitch": True,
        "min_segment_ms": 450,
        "vad": {"max_speech_duration_s": 3.5, "min_silence_duration_ms": 80, "speech_pad_ms": 250},
    },
    "hybrid_repair_s3_b400": {
        "bucket": 400,
        "first_pad_ms": 500,
        "cpu_repair_min_chunks": 2,
        "vad": {"max_speech_duration_s": 3.5, "min_silence_duration_ms": 80, "speech_pad_ms": 250},
    },
    "int8_pad300_first500_b800": {
        "bucket": 800,
        "first_pad_ms": 500,
        "model_filename": "v3_ctc.int8.onnx",
        "vad": {"max_speech_duration_s": 7.5, "min_silence_duration_ms": 100, "speech_pad_ms": 300},
    },
    "lowload_s5_b600": {
        "bucket": 600,
        "first_pad_ms": 500,
        "vad": {"max_speech_duration_s": 5.5, "min_silence_duration_ms": 100, "speech_pad_ms": 250},
    },
    "lowload_s6_b800": {
        "bucket": 800,
        "first_pad_ms": 500,
        "vad": {"max_speech_duration_s": 6.5, "min_silence_duration_ms": 100, "speech_pad_ms": 250},
    },
    "tiles1_s3_b400": {
        "bucket": 400,
        "first_pad_ms": 500,
        "device_config": {"NPU_TILES": 1},
        "vad": {"max_speech_duration_s": 3.5, "min_silence_duration_ms": 80, "speech_pad_ms": 250},
    },
    "turbo_s3_b400": {
        "bucket": 400,
        "first_pad_ms": 500,
        "device_config": {"NPU_TURBO": True},
        "vad": {"max_speech_duration_s": 3.5, "min_silence_duration_ms": 80, "speech_pad_ms": 250},
    },
    "tiles1_turbo_s3_b400": {
        "bucket": 400,
        "first_pad_ms": 500,
        "device_config": {"NPU_TILES": 1, "NPU_TURBO": True},
        "vad": {"max_speech_duration_s": 3.5, "min_silence_duration_ms": 80, "speech_pad_ms": 250},
    },
}


def repo_root():
    return Path(__file__).resolve().parents[1]


def default_recordings_dir():
    return repo_root() / "recordings" / "debug_dictation"


def default_model_dir():
    return repo_root() / "models" / "asr" / "gigaam-v3-ctc"


def default_log_file():
    return repo_root() / "voice_dictation.log"


def normalize_audio(audio):
    if audio.ndim == 2 and audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = np.squeeze(audio)
    return np.ascontiguousarray(audio, dtype=np.float32)


def resample_to_16k(audio, sample_rate):
    sample_rate = int(sample_rate)
    if sample_rate == 16_000:
        return audio
    divisor = gcd(sample_rate, 16_000)
    return resample_poly(audio, 16_000 // divisor, sample_rate // divisor).astype(np.float32)


def load_audio(path):
    audio, sample_rate = sf.read(path, dtype="float32")
    audio = normalize_audio(audio)
    return np.ascontiguousarray(resample_to_16k(audio, sample_rate), dtype=np.float32)


def vad_segments(vad, audio16, vad_options, first_pad_ms):
    waveforms = audio16[None, :]
    waveforms_len = np.array([len(audio16)], dtype=np.int64)
    raw_segments = next(vad.segment_batch(waveforms, waveforms_len, 16_000, **vad_options))
    segments = []
    for start, end in raw_segments:
        start = max(0, min(len(audio16), int(start)))
        end = max(0, min(len(audio16), int(end)))
        if end > start:
            segments.append((start, end))
    if segments and first_pad_ms:
        start, end = segments[0]
        segments[0] = (max(0, start - int(first_pad_ms * 16)), end)
    return segments


def hard_split_segments(segments, bucket, overlap_ms):
    max_samples = GigaamOpenVinoCtcAsr._audio_samples_for_bucket(bucket)
    overlap_samples = int(max(0, overlap_ms) * 16)
    overlap_samples = min(overlap_samples, max_samples // 4)
    split = []
    for start, end in segments:
        start = int(start)
        end = int(end)
        if end - start <= max_samples:
            split.append((start, end))
            continue
        cursor = start
        while cursor < end:
            chunk_end = min(end, cursor + max_samples)
            split.append((cursor, chunk_end))
            if chunk_end >= end:
                break
            cursor = max(cursor + 1, chunk_end - overlap_samples)
    return split


def filter_short_segments(segments, min_segment_ms):
    min_samples = int(max(0, min_segment_ms) * 16)
    if min_samples <= 0:
        return segments
    return [(start, end) for start, end in segments if end - start >= min_samples]


def result_to_text(result):
    if isinstance(result, str):
        return result
    if hasattr(result, "text"):
        return result.text
    if isinstance(result, dict) and "text" in result:
        return str(result["text"])
    return str(result)


def latest_files(directory, count):
    files = sorted(directory.glob("*.wav"), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[:count]


def text_diff_score(left, right):
    left = (left or "").strip()
    right = (right or "").strip()
    if not left and not right:
        return 0.0
    return 1.0 - SequenceMatcher(None, left, right).ratio()


def parse_literal(value):
    try:
        return str(ast.literal_eval(value))
    except (SyntaxError, ValueError):
        return value.strip("'\"")


def compare_log_error_files(log_file, limit, min_diff):
    dictation_re = re.compile(r"audio_path=(?P<path>.*?) raw=")
    compare_re = re.compile(r"active_raw=(?P<active>'.*?'|\".*?\") compare_raw=(?P<compare>'.*?'|\".*?\")")
    current_path = None
    cases = []
    if not log_file.exists():
        return cases

    for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if "dictation result" in line and "audio_path=" in line:
            match = dictation_re.search(line)
            if match:
                current_path = Path(match.group("path")).resolve()
            continue

        if "asr compare audio=" not in line or current_path is None:
            continue
        match = compare_re.search(line)
        if not match:
            continue
        active_text = parse_literal(match.group("active"))
        compare_text = parse_literal(match.group("compare"))
        if active_text == compare_text:
            continue
        score = text_diff_score(active_text, compare_text)
        if score < min_diff or not current_path.exists():
            continue
        cases.append({"path": current_path, "score": score, "active": active_text, "compare": compare_text})

    cases.sort(key=lambda case: case["score"], reverse=True)
    return cases[:limit]


def resolve_files(args):
    files = [Path(value) for value in args.files]
    if args.latest:
        files.extend(latest_files(args.recordings_dir, args.latest))
    if args.from_compare_log:
        cases = compare_log_error_files(args.log_file, args.from_compare_log, args.min_compare_diff)
        if cases:
            print("compare_log_cases:", flush=True)
            for case in cases:
                print(
                    f"  score={case['score']:.3f} file={case['path'].name} "
                    f"npu={case['active']} | cpu={case['compare']}",
                    flush=True,
                )
        files.extend(case["path"] for case in cases)
    seen = set()
    resolved = []
    for path in files:
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        resolved.append(path)
    return resolved


def device_config_key(device_config):
    return tuple(sorted((str(key), value) for key, value in (device_config or {}).items()))


def model_filename_key(config):
    return str(config.get("model_filename") or "v3_ctc.onnx")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", help="WAV files to test.")
    parser.add_argument("--latest", type=int, default=0, help="Test N latest debug recordings.")
    parser.add_argument("--recordings-dir", type=Path, default=default_recordings_dir())
    parser.add_argument("--model-dir", type=Path, default=default_model_dir())
    parser.add_argument("--log-file", type=Path, default=default_log_file())
    parser.add_argument("--from-compare-log", type=int, default=0, help="Test N recordings with largest CPU/NPU log diffs.")
    parser.add_argument("--min-compare-diff", type=float, default=0.04)
    parser.add_argument("--configs", default="pad300_first0_b800,pad300_first500_b800,pad300_first500_b1000")
    parser.add_argument("--device", default="NPU", choices=["CPU", "GPU", "NPU"])
    parser.add_argument("--pad-mode", default="zero")
    parser.add_argument("--cpu-baseline", action="store_true")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    files = resolve_files(args)
    if not files:
        raise SystemExit("No WAV files provided. Use file paths or --latest N.")

    config_names = [name.strip() for name in args.configs.split(",") if name.strip()]
    unknown = [name for name in config_names if name not in CONFIGS]
    if unknown:
        raise SystemExit(f"Unknown config(s): {', '.join(unknown)}")

    vad = onnx_asr.load_vad("silero")
    asr_keys = sorted(
        {
            (
                CONFIGS[name]["bucket"],
                device_config_key(CONFIGS[name].get("device_config")),
                model_filename_key(CONFIGS[name]),
            )
            for name in config_names
        }
    )
    asrs = {}
    for bucket, config_key, model_filename in asr_keys:
        device_config = dict(config_key)
        asr = GigaamOpenVinoCtcAsr(
            args.model_dir,
            device=args.device,
            model_filename=model_filename,
            cache_dir=repo_root() / "models" / "openvino" / "cache" / "asr_gigaam_vad_tune",
            bucket_frames=(bucket,),
            pad_mode=args.pad_mode,
            device_config=device_config,
        )
        asr.warmup([bucket])
        asrs[(bucket, config_key, model_filename)] = asr

    cpu = None
    if args.cpu_baseline:
        cpu = onnx_asr.load_model("gigaam-v3-ctc", args.model_dir, quantization="int8")

    report = []
    for path in files:
        audio16 = load_audio(path)
        audio_sec = len(audio16) / 16_000
        print("\n" + "=" * 96, flush=True)
        print(f"{path.name} audio={audio_sec:.2f}s", flush=True)

        item = {"file": str(path), "audio_sec": audio_sec, "results": []}
        cpu_text = None
        if cpu is not None:
            start = time.perf_counter()
            cpu_text = result_to_text(cpu.recognize(audio16, sample_rate=16_000)).strip()
            cpu_sec = time.perf_counter() - start
            item["cpu"] = {"seconds": cpu_sec, "text": cpu_text}
            print(f"cpu_int8: {cpu_sec:.3f}s {cpu_text}", flush=True)

        for name in config_names:
            config = CONFIGS[name]
            bucket = config["bucket"]
            config_key = device_config_key(config.get("device_config"))
            model_filename = model_filename_key(config)
            asr = asrs[(bucket, config_key, model_filename)]
            segments = vad_segments(vad, audio16, config["vad"], config["first_pad_ms"])
            segments = filter_short_segments(segments, config.get("min_segment_ms", 0))
            if config.get("hard_split"):
                segments = hard_split_segments(segments, bucket, config.get("overlap_ms", 0))
            start = time.perf_counter()
            text = asr.recognize_segments_16k(
                audio16,
                segments,
                bucket=bucket,
                stitch=bool(config.get("stitch")),
                fuzzy_stitch=bool(config.get("fuzzy_stitch")),
            ).strip()
            seconds = time.perf_counter() - start
            chunks = list(getattr(asr, "last_chunks", []))
            repair = None
            repair_min_chunks = int(config.get("cpu_repair_min_chunks") or 0)
            if repair_min_chunks and len(chunks) >= repair_min_chunks:
                if cpu is None:
                    raise SystemExit(f"{name} requires --cpu-baseline for CPU repair.")
                repair_start = time.perf_counter()
                repair_text = result_to_text(cpu.recognize(audio16, sample_rate=16_000)).strip()
                repair_sec = time.perf_counter() - repair_start
                repair = {"seconds": repair_sec, "reason": f"chunks>={repair_min_chunks}", "npu_text": text}
                text = repair_text
                seconds += repair_sec
            segment_rows = [
                {"start_sec": start / 16_000, "end_sec": end / 16_000, "duration_sec": (end - start) / 16_000}
                for start, end in segments
            ]
            item["results"].append(
                {
                    "config": name,
                    "bucket": bucket,
                    "device_config": dict(config_key),
                    "model_filename": model_filename,
                    "seconds": seconds,
                    "segments": segment_rows,
                    "chunks": chunks,
                    "repair": repair,
                    "text": text,
                }
            )
            segment_text = ", ".join(f"{row['start_sec']:.2f}-{row['end_sec']:.2f}" for row in segment_rows)
            chunk_text = ", ".join(f"{chunk['frames']}->{chunk['bucket']}" for chunk in chunks)
            config_text = " ".join(f"{key}={value}" for key, value in config_key)
            config_suffix = f" {config_text}" if config_text else ""
            print(f"{name}: {seconds:.3f}s n={len(segments)}{config_suffix} [{segment_text}]", flush=True)
            if repair:
                print(f"  repair: {repair['reason']} +{repair['seconds']:.3f}s", flush=True)
            if chunk_text:
                print(f"  chunks: {chunk_text}", flush=True)
            print(f"  {text}", flush=True)

        report.append(item)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\njson_out={args.json_out}", flush=True)


if __name__ == "__main__":
    main()
