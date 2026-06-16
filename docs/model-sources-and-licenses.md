# Model Sources and License Notes

Checked on: 2026-06-16.

This document records the upstream sources used by the current prototype and the license labels observed on official project pages. It is not legal advice. Re-check upstream model cards and repositories before publishing any converted model artifacts.

## Current Sources

| Component | Upstream source | Role in this project | Observed license | Local artifact path |
| --- | --- | --- | --- | --- |
| GigaAM family | https://github.com/salute-developers/GigaAM | Original GigaAM model family and reference code. | MIT | Not downloaded directly by the app. |
| GigaAM-v3 | https://huggingface.co/ai-sage/GigaAM-v3 | Base GigaAM-v3 model family. The ONNX package references this as the base model. | MIT | Not downloaded directly by the app. |
| GigaAM-v3 ONNX | https://huggingface.co/istupakov/gigaam-v3-onnx | Current ASR model source used by `onnx-asr` and direct local downloads. | MIT | `models/asr/gigaam-v3-ctc/` |
| ONNX ASR | https://github.com/istupakov/onnx-asr | Runtime library and model loader used for the CPU ASR profile. | MIT | Python dependency from `requirements.txt`. |
| RUPunct big | https://huggingface.co/RUPunct/RUPunct_big | Current punctuation/capitalization model source. | MIT | `models/openvino/RUPunct_big_fp16_static128/` after local conversion. |

## Generated Local Artifacts

Generated artifacts are ignored by Git:

- `models/asr/gigaam-v3-ctc/`
- `models/openvino/RUPunct_big_fp16_static128/`
- `models/openvino/cache/`
- OpenVINO/NNCF ASR conversion outputs under `models/asr/`

Current policy:

- Do not commit model weights, converted OpenVINO XML/BIN files, caches, local recordings, or Hugging Face caches.
- Prefer first-run download/conversion from official upstream sources.
- If converted model artifacts are ever published separately, include upstream attribution, exact source revision or commit where practical, original license text or links, conversion script/version, and a clear note that the artifact is a derivative conversion.

## Redistribution Notes

The current public repository should publish:

- Application code.
- Setup scripts.
- Download and conversion code.
- Documentation describing model sources and local artifact locations.

The current public repository should not publish:

- Downloaded model weights.
- Locally converted OpenVINO artifacts.
- OpenVINO cache files.
- Debug audio recordings.

## Recheck Before Release

Before a public release or a Hugging Face repository with converted artifacts:

- Re-open every upstream model card/repository listed above.
- Confirm the license label has not changed.
- Check whether each upstream project includes additional attribution, citation, acceptable-use, or redistribution requirements.
- Include a third-party notices file if bundled artifacts are shipped.
- Keep a dated copy of the source/revision metadata used for the release.
