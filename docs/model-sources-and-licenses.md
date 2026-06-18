# Model Sources and License Notes

Checked on: 2026-06-18.

This document records the upstream sources used by the current prototype and the license labels observed on official project pages. It is not legal advice. Re-check upstream model cards and repositories before publishing any converted model artifacts.

## Current Audit Verdict

The current v0.1 source-only release plan is acceptable from a model-license hygiene perspective:

- The app repository does not bundle model weights, converted OpenVINO artifacts, OpenVINO cache files, or debug recordings.
- Current ASR, punctuation, and VAD model sources are observed as MIT-licensed on their official upstream pages.
- Current runtime/export helper projects checked for model loading are also observed as MIT-licensed.
- If converted model artifacts are later published separately, include upstream attribution, license text/links, exact source revisions where practical, conversion script/version, and a clear derivative-conversion note.

## Current Sources

| Component | Upstream source | Role in this project | Observed license | Checked revision / metadata | Local artifact path |
| --- | --- | --- | --- | --- | --- |
| GigaAM family | https://github.com/salute-developers/GigaAM | Original GigaAM model family and reference code. | MIT | GitHub license API reports `mit`; default branch `main`; pushed 2026-04-15. | Not downloaded directly by the app. |
| GigaAM-v3 | https://huggingface.co/ai-sage/GigaAM-v3 | Base GigaAM-v3 model family. The ONNX package references this as the base model. | MIT | Hugging Face API: `license=mit`, SHA `ec1dc1f01d0d627ab2c0d3acc1e235702300d95e`, last modified 2025-11-19. | Not downloaded directly by the app. |
| GigaAM-v3 ONNX | https://huggingface.co/istupakov/gigaam-v3-onnx | Current ASR model source used by `onnx-asr` and direct local downloads. | MIT | Hugging Face API: `license=mit`, SHA `322c3b29492673eb7d0b434bfa9dfb8653e34d02`, last modified 2026-02-18. | `models/asr/gigaam-v3-ctc/` |
| ONNX ASR | https://github.com/istupakov/onnx-asr | Runtime library and model loader used for the CPU ASR profile. | MIT | GitHub license API reports `mit`; default branch `main`; pushed 2026-05-16. | Python dependency from `requirements.txt`. |
| RUPunct big | https://huggingface.co/RUPunct/RUPunct_big | Current punctuation/capitalization model source. | MIT | Hugging Face API: `license=mit`, SHA `d05f73afd84b57a45b83238c35b866bc625fe247`, last modified 2024-05-01. | `models/openvino/RUPunct_big_fp16_static128/` after local conversion. |
| Silero VAD | https://github.com/snakers4/silero-vad | Voice activity detector used through `onnx_asr.load_vad("silero")` for NPU ASR segmentation. | MIT | GitHub license file reports MIT, copyright `2020-present Silero Team`. | Loaded through `onnx-asr`; no local project artifact path is committed. |

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
- Preserve MIT copyright/license notices for any bundled substantial portions of model/runtime artifacts.

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

Before a public release with bundled model artifacts or a Hugging Face repository with converted artifacts:

- Re-open every upstream model card/repository listed above.
- Confirm the license label has not changed.
- Check whether each upstream project includes additional attribution, citation, acceptable-use, or redistribution requirements.
- Include a third-party notices file if bundled artifacts are shipped.
- Keep a dated copy of the source/revision metadata used for the release.

For the current source-only v0.1 release plan, this check was completed on 2026-06-18 and no blocking model-license issue was found.
