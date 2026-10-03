# NPU Dictate: local Russian dictation on an Intel Core Ultra NPU

I'd like to share a small Windows dictation app built around Intel NPU inference. It records speech, transcribes it locally and pastes the text into the previously focused input field. It has a floating button, configurable hotkeys, hold-to-talk and start/stop modes, plus an optional Enter after insertion.

The current prerelease is [NPU Dictate alpha.5](https://github.com/zoomerland/npu-dictate/releases/tag/v0.1.0-alpha.5). The [source](https://github.com/zoomerland/npu-dictate) is MIT-licensed; model licenses are separate. The Windows builds are unsigned alpha software. Speech recognition is Russian only for now, even though the interface also has English localization.

The reference machine is a Core Ultra 5 135U with Intel AI Boost, running Windows 11 and OpenVINO 2026.2.0. The current NPU ASR profile is GigaAM v3 CTC converted to OpenVINO with NNCF INT8 and a static 400-frame feature bucket. Punctuation is a separate RUPunct_big FP16 model with a static 128-token input. [Converted artifacts and their manifest](https://huggingface.co/Zoomerland/local-voice-dictation-openvino) are downloaded separately, with size and SHA256 checks.

This is not an all-NPU pipeline. Capture, Silero VAD, feature preparation, segment stitching and Windows insertion still run on the CPU. The CPU fallback uses a separate ONNX INT8 GigaAM profile. GPU/NVIDIA support has not been validated.

The interesting engineering part has been variable-length speech on a static-shape ASR path. Segments are processed independently, with real feature lengths supplied alongside padded features. Their outputs are stitched in the application; the model does not keep a shared transcript state between requests. The current implementation uses VAD and overlap-aware stitching. Repeated words remain an imperfect case, so I'm not treating CPU/NPU text agreement as an accuracy metric.

Cold compilation is another practical issue: the first OpenVINO/NPU preparation can take noticeably longer than warm starts. There are historical warm ASR timings in the README, but no formal end-to-end, power or battery benchmark. Alpha.5 mainly improves long-text punctuation windows and UI safeguards, not the ASR model itself.

I'd appreciate two kinds of feedback:

- Tests on other Intel Core Ultra laptops, especially cold startup, warm dictation latency and device detection. Please report the CPU/NPU, driver and OpenVINO versions, selected profile and a non-sensitive reproduction in the [app issue tracker](https://github.com/zoomerland/npu-dictate/issues).
- Advice on static-shape CTC deployment on Intel NPU: bucket selection, validating the real-length/padding path, and segment overlap strategies that preserve genuinely repeated words.

Models need an initial download; normal dictation afterwards runs locally. There is no need to upload recordings to try it. Please don't post private audio or full unredacted diagnostic logs.
