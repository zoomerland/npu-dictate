from pathlib import Path


ASR_MODEL_NAME = "gigaam-v3-ctc"
ASR_MODEL_REPO = "istupakov/gigaam-v3-onnx"
PUNCT_MODEL_NAME = "RUPunct/RUPunct_big"
PUNCT_MAX_LEN = 128


def repo_root():
    return Path(__file__).resolve().parents[1]


def hf_cache_dir():
    return repo_root() / ".hf"


def asr_model_dir():
    return repo_root() / "models" / "asr" / ASR_MODEL_NAME


def punct_model_dir():
    return repo_root() / "models" / "openvino" / "RUPunct_big_fp16_static128"


def emit(status_callback, message):
    if status_callback:
        status_callback(message)


def asr_model_ready():
    model_dir = asr_model_dir()
    required = ("config.json", "v3_ctc.int8.onnx", "v3_vocab.txt")
    return all((model_dir / name).exists() for name in required)


def asr_openvino_model_ready():
    model_dir = asr_model_dir()
    required = ("config.json", "v3_ctc.onnx", "v3_vocab.txt")
    return all((model_dir / name).exists() for name in required)


def punct_model_ready():
    model_dir = punct_model_dir()
    required = ("config.json", "openvino_model.xml", "openvino_model.bin", "tokenizer.json")
    return all((model_dir / name).exists() for name in required)


def ensure_asr_model(status_callback=None):
    if asr_model_ready():
        return asr_model_dir()

    emit(status_callback, "Downloading ASR")
    import onnx_asr

    asr_model_dir().parent.mkdir(parents=True, exist_ok=True)
    onnx_asr.load_model(ASR_MODEL_NAME, asr_model_dir(), quantization="int8")
    return asr_model_dir()


def ensure_asr_openvino_model(status_callback=None):
    if asr_openvino_model_ready():
        return asr_model_dir()

    emit(status_callback, "Downloading ASR NPU")
    from huggingface_hub import hf_hub_download

    model_dir = asr_model_dir()
    model_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("config.json", "v3_vocab.txt", "v3_ctc.onnx"):
        hf_hub_download(ASR_MODEL_REPO, filename, local_dir=model_dir)
    return model_dir


def ensure_punct_model(status_callback=None, max_len=PUNCT_MAX_LEN):
    if punct_model_ready():
        return punct_model_dir()

    emit(status_callback, "Downloading punct")
    import openvino as ov
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    model_dir = punct_model_dir()
    model_dir.mkdir(parents=True, exist_ok=True)
    hf_cache_dir().mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        PUNCT_MODEL_NAME,
        cache_dir=str(hf_cache_dir()),
        strip_accents=False,
        add_prefix_space=True,
    )
    model = AutoModelForTokenClassification.from_pretrained(
        PUNCT_MODEL_NAME,
        cache_dir=str(hf_cache_dir()),
    )
    model.eval()

    tokenizer.save_pretrained(model_dir)
    model.config.save_pretrained(model_dir)

    emit(status_callback, "Converting punct")
    encoded = tokenizer(
        "это короткий тест для подготовки модели",
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=max_len,
    )
    inputs = {
        key: value
        for key, value in encoded.items()
        if key in {"input_ids", "attention_mask", "token_type_ids"}
    }

    with torch.no_grad():
        ov_model = ov.convert_model(model, example_input=inputs)

    ov_model.reshape({key: [1, max_len] for key in inputs})
    ov.save_model(ov_model, model_dir / "openvino_model.xml", compress_to_fp16=True)
    return model_dir


def main():
    ensure_asr_model(print)
    ensure_punct_model(print)
    print("Models are ready.")


if __name__ == "__main__":
    main()
