# Outreach for alpha.5

Prepared on 2026-10-03. No video is required for this round.

Public sources of truth:

- [Source and product limitations](https://github.com/zoomerland/npu-dictate).
- [Unsigned alpha.5 EXE/MSI](https://github.com/zoomerland/npu-dictate/releases/tag/v0.1.0-alpha.5).
- [Converted model artifacts](https://huggingface.co/Zoomerland/local-voice-dictation-openvino).
- [Tested hardware](../tested-hardware.md).

## Destinations

| Destination | Material | Reason / gate |
| --- | --- | --- |
| OpenVINO GitHub, Show and tell | [English post](openvino-community-post-en.md) | Official project-showcase category; request Intel NPU testing and implementation feedback. |
| GigaAM GitHub | [Russian technical question](gigaam-team-message-ru.md) | Follow up on existing long-form guidance with a static-shape deployment question, not a claimed upstream defect. |
| Our Hugging Face model community | [English testing thread](hf-community-post-en.md) | Explain how converted artifacts are used and where to report app problems. |
| ODS Projects | [Russian project description](ods-announcement-ru.md) | User login and an available project-submission route are required. |
| Habr | [Author briefing](habr-author-brief-ru.md) | Do not publish generated article text. Current rules require an original author article, with only limited AI additions; self-promotion rules also apply. |
| Own GitHub documentation | [Russian technical note](technical-note-ru.md) | Public, two-part explanation without a video or invented measurements. |

Publication receipts and blockers are recorded in [publication-log.md](publication-log.md). A prepared text or successful authentication is not a publication receipt.

## Claim Boundaries

- Russian ASR; English/Russian interface. English interface is not English dictation.
- Intel NPU path tested on Core Ultra 5 135U / Intel AI Boost, not a universal NPU implementation. No validated NVIDIA or GPU profile.
- CPU still handles capture, VAD, feature preparation, stitching and insertion. No zero-CPU, power-saving or battery-life claim.
- Cold OpenVINO compilation can be slow. Historical README timings are warm ASR development measurements, not alpha.5 end-to-end benchmarks or WER.
- Converted artifacts have upstream model licenses; MIT describes the app code, not every weight in the pipeline.
- Builds are unsigned alpha software. Do not recommend disabling Windows security protections.
- Request sanitized diagnostics and non-sensitive reproductions. Do not publish private audio, transcripts, full logs, tokens or local user configuration.

## Working State

This documentation branch starts from `features/next` at `8700d1d8d6288877287328ba9da0363633693113`. At the starting checkpoint, `main` / `origin/main` were `fbd0a53ae1052a34bdc09528c907d7ed8c1948f6`, with the same tree. One clean worktree, no stashes or detached HEADs were observed. The old `codex/outreach-launch-kit` at `b72dd9dda19618432cc824e0fa6e92c1f3587779` remains preserved; it is not the current publication source.

Ignored model/build/cache directories remain local operational data; ignored config, credentials, recordings and logs remain private evidence. None is part of this outreach change. No app restart, model conversion, main merge, tag or new release is included.
