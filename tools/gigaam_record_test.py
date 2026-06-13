import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import onnx_asr
import sounddevice as sd
import soundfile as sf


def repo_root():
    return Path(__file__).resolve().parents[1]


def default_asr_model_dir():
    return repo_root() / "models" / "asr" / "gigaam-v3-ctc"


def default_recordings_dir():
    return repo_root() / "recordings"


def default_punct_model_dir():
    return repo_root() / "models" / "openvino" / "RUPunct_big_fp16_static128"


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
        print(f"Recording starts in {countdown} seconds...")
        time.sleep(countdown)

    print(f"Recording {seconds:.1f} seconds at {sample_rate} Hz...")
    audio = sd.rec(
        int(seconds * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
        device=device_index,
    )
    sd.wait()

    if audio.ndim == 2 and audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = np.squeeze(audio)

    return np.ascontiguousarray(audio, dtype=np.float32)


def save_audio(audio, sample_rate, recordings_dir):
    recordings_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = recordings_dir / f"gigaam_test_{timestamp}.wav"
    sf.write(path, audio, sample_rate)
    return path


def load_audio_file(path):
    audio, sample_rate = sf.read(path, dtype="float32")
    if audio.ndim == 2 and audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = np.squeeze(audio)
    return np.ascontiguousarray(audio, dtype=np.float32), sample_rate


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--file", type=Path, help="Transcribe an existing WAV file instead of recording.")
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Recording sample rate. Use 0 for the selected device default.",
    )
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--device-index", type=int)
    parser.add_argument("--countdown", type=int, default=3)
    parser.add_argument("--model", default="gigaam-v3-ctc")
    parser.add_argument("--model-dir", type=Path, default=default_asr_model_dir())
    parser.add_argument("--quantization", default="int8")
    parser.add_argument("--recordings-dir", type=Path, default=default_recordings_dir())
    parser.add_argument("--skip-punct", action="store_true")
    parser.add_argument("--punct-device", default="NPU", choices=["CPU", "GPU", "NPU"])
    parser.add_argument("--punct-model-dir", type=Path, default=default_punct_model_dir())
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    if args.file:
        audio, sample_rate = load_audio_file(args.file)
        audio_path = args.file
        seconds = len(audio) / sample_rate
    else:
        sample_rate = resolve_sample_rate(args.sample_rate, args.device_index)
        audio = record_audio(
            args.seconds,
            sample_rate,
            args.channels,
            args.device_index,
            args.countdown,
        )
        audio_path = save_audio(audio, sample_rate, args.recordings_dir)
        seconds = args.seconds

    load_start = time.perf_counter()
    asr = onnx_asr.load_model(args.model, args.model_dir, quantization=args.quantization)
    load_sec = time.perf_counter() - load_start

    infer_start = time.perf_counter()
    raw_result = asr.recognize(audio, sample_rate=sample_rate)
    infer_sec = time.perf_counter() - infer_start
    raw_text = result_to_text(raw_result).strip()

    punct_text = ""
    punct_sec = 0.0
    if raw_text and not args.skip_punct:
        from rupunct_restore import RUPunctRestorer

        punct_start = time.perf_counter()
        restorer = RUPunctRestorer(args.punct_model_dir, args.punct_device)
        punct_text = restorer.restore(raw_text)
        punct_sec = time.perf_counter() - punct_start

    rtf = seconds / infer_sec if infer_sec else 0.0

    print(f"audio_path={audio_path}")
    print(f"audio_sec={seconds:.3f}")
    print(f"asr_load_sec={load_sec:.4f}")
    print(f"asr_infer_sec={infer_sec:.4f}")
    print(f"asr_rtf={rtf:.2f}x")
    if punct_text:
        print(f"punct_total_sec={punct_sec:.4f}")
    print(f"raw={raw_text}")
    if punct_text:
        print(f"punct={punct_text}")


if __name__ == "__main__":
    main()
