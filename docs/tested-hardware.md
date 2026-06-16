# Tested Hardware

This project is still young, so the tested hardware list is intentionally small and conservative. A device is listed here only when it has been used for local development or direct smoke testing.

## Reference Laptop

| Item | Value |
| --- | --- |
| OS | Windows 11 |
| CPU | Intel Core Ultra 5 135U |
| NPU | Intel AI Boost |
| Approximate NPU capability | About 11 NPU TOPS |
| Approximate total platform AI capability | About 22 TOPS |
| OpenVINO version observed | 2026.2.0 |
| OpenVINO devices observed | `CPU`, `GPU`, `NPU` |
| Microphone | Built-in microphone array |

## Tested Paths

| Pipeline part | Tested path | Status |
| --- | --- | --- |
| ASR CPU | GigaAM v3 CTC ONNX INT8 on CPU | Works. Used as the baseline comparison path. |
| ASR NPU | GigaAM v3 CTC OpenVINO NNCF INT8 bucket-400 on NPU | Works with VAD segmentation and fuzzy stitching. Current preferred ASR path on the reference laptop. |
| Punctuation CPU | RUPunct big OpenVINO FP16 static-128 on CPU | Works. Direct smoke test produced `Привет, мир! Как дела?` from unpunctuated Russian text. |
| Punctuation NPU | RUPunct big OpenVINO FP16 static-128 on NPU | Works. Current preferred punctuation path on the reference laptop. |
| Paste/focus | Windows UI Automation, clipboard, and keyboard input events | Works in the current daily workflow, still needs a broader application matrix. |

## Notes

- Treat this laptop as a weak/mainstream NPU baseline rather than a high-end accelerator.
- First OpenVINO/NPU compilation can be slow. Warm cache starts are much faster.
- The app logs a startup OpenVINO hardware probe with available devices and selected OpenVINO devices.
- If a machine does not report `NPU`, use the CPU ASR profile and CPU punctuation device while investigating drivers.
- GPU profiles are not considered tested yet.
