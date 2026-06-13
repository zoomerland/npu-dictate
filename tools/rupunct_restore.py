import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import openvino as ov
from transformers import AutoTokenizer


PUNCT = {
    "O": "",
    "PERIOD": ".",
    "COMMA": ",",
    "QUESTION": "?",
    "TIRE": " \u2014",
    "DVOETOCHIE": ":",
    "VOSKL": "!",
    "PERIODCOMMA": ";",
    "DEFIS": "-",
    "MNOGOTOCHIE": "...",
    "QUESTIONVOSKL": "?!",
}

SENTENCE_END = {"PERIOD", "QUESTION", "VOSKL", "MNOGOTOCHIE", "QUESTIONVOSKL"}


def split_label(label):
    if label.startswith("UPPER_TOTAL_"):
        return "UPPER_TOTAL", label.removeprefix("UPPER_TOTAL_")
    if label.startswith("UPPER_"):
        return "UPPER", label.removeprefix("UPPER_")
    if label.startswith("LOWER_"):
        return "LOWER", label.removeprefix("LOWER_")
    return "LOWER", "O"


def apply_case(word, mode, index, prev_suffix, score):
    if mode == "UPPER_TOTAL":
        return word.upper()

    should_cap = index == 0 or prev_suffix in SENTENCE_END or (
        mode == "UPPER" and score >= 0.70
    )
    if should_cap:
        return word[:1].upper() + word[1:]
    return word


def cleanup(text):
    text = re.sub(r"(?<=\w)\s+-\s+(?=\w)", "-", text, flags=re.UNICODE)
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)
    text = re.sub(r"\s*\u2014\s*", " \u2014 ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


class RUPunctRestorer:
    def __init__(self, model_dir, device="NPU", max_len=128, cache_dir=None):
        self.model_dir = Path(model_dir)
        self.max_len = max_len

        with (self.model_dir / "config.json").open("r", encoding="utf-8") as file:
            config = json.load(file)
        self.id2label = {int(k): v for k, v in config["id2label"].items()}

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_dir),
            strip_accents=False,
            add_prefix_space=True,
        )

        self.core = ov.Core()
        if cache_dir:
            self.core.set_property({"CACHE_DIR": str(cache_dir)})

        model = self.core.read_model(str(self.model_dir / "openvino_model.xml"))
        self.compiled = self.core.compile_model(model, device)

    def restore(self, text):
        encoded = self.tokenizer(
            text,
            return_offsets_mapping=True,
            padding="max_length",
            truncation=True,
            max_length=self.max_len,
            return_tensors="np",
        )
        offsets = encoded.pop("offset_mapping")[0]
        inputs = {
            key: value.astype(np.int64)
            for key, value in encoded.items()
            if key in {"input_ids", "attention_mask", "token_type_ids"}
        }

        logits = self.compiled(inputs)[self.compiled.output("logits")][0]
        pred_ids = logits.argmax(axis=-1)
        probs = np.exp(logits - logits.max(axis=-1, keepdims=True))
        probs = probs / probs.sum(axis=-1, keepdims=True)

        groups = []
        current = None
        for index, (start, end) in enumerate(offsets):
            if inputs["attention_mask"][0, index] == 0 or int(start) == int(end):
                continue

            label_id = int(pred_ids[index])
            label = self.id2label[label_id]
            score = float(probs[index, label_id])
            start = int(start)
            end = int(end)

            if current and current["label"] == label:
                current["end"] = end
                current["scores"].append(score)
            else:
                if current:
                    groups.append(current)
                current = {"label": label, "start": start, "end": end, "scores": [score]}

        if current:
            groups.append(current)

        pieces = []
        prev_suffix = None
        for index, group in enumerate(groups):
            word = text[group["start"] : group["end"]].strip()
            mode, suffix = split_label(group["label"])
            score = sum(group["scores"]) / len(group["scores"])
            pieces.append(apply_case(word, mode, index, prev_suffix, score) + PUNCT.get(suffix, ""))
            prev_suffix = suffix

        return cleanup(" ".join(pieces))


def default_model_dir():
    return Path(__file__).resolve().parents[1] / "models" / "openvino" / "RUPunct_big_fp16_static128"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="*", help="Text to restore. Reads stdin when omitted.")
    parser.add_argument("--device", default="NPU", choices=["CPU", "GPU", "NPU"])
    parser.add_argument("--max-len", type=int, default=128)
    parser.add_argument("--model-dir", type=Path, default=default_model_dir())
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "openvino" / "cache",
    )
    parser.add_argument("--show-time", action="store_true")
    args = parser.parse_args()

    text = " ".join(args.text).strip()
    if not text:
        text = sys.stdin.read().strip()

    start = time.perf_counter()
    restorer = RUPunctRestorer(args.model_dir, args.device, args.max_len, args.cache_dir)
    load_sec = time.perf_counter() - start

    start = time.perf_counter()
    result = restorer.restore(text)
    infer_sec = time.perf_counter() - start

    print(result)
    if args.show_time:
        print(f"load_sec={load_sec:.4f} infer_sec={infer_sec:.4f}", file=sys.stderr)


if __name__ == "__main__":
    main()
