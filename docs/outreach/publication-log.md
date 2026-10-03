# Publication Log

## 2026-10-03 Round

| Destination | State | Receipt / blocker |
| --- | --- | --- |
| Own GitHub technical note | Published, verified | [Russian two-part note](https://github.com/zoomerland/npu-dictate/blob/a117afb5a02043d0fbf1fefef0594fc9588832c7/docs/outreach/technical-note-ru.md); documentation branch only, no main merge. Remote content matches the reviewed file. |
| OpenVINO Show and tell | Posted, verified | [Discussion #38580](https://github.com/openvinotoolkit/openvino/discussions/38580), author `zoomerland`, category `Show and tell`. Title and body read back; body matches reviewed file. |
| GigaAM technical question | Posted, verified | [Issue #93](https://github.com/salute-developers/GigaAM/issues/93), author `zoomerland`, open. Title and body read back; body matches reviewed file. Existing #70 guidance acknowledged, no upstream bug claimed. |
| Hugging Face artifact community | Posted, verified | [Discussion #1](https://huggingface.co/Zoomerland/local-voice-dictation-openvino/discussions/1), author `Zoomerland`, open. Title and initial comment read back; body matches reviewed file. |
| ODS Projects | Waiting for email confirmation | User signed in; site requests primary email confirmation before full access. Project-add link is present. No submission or account modification performed. User action requested; no password/inbox read. |
| Habr | Blocked for generated article | Original author text and compliance with self-promotion rules required; factual briefing prepared. No article submitted. |

No email has been sent. No video upload or private recording publication is part of this round. Do not treat preparation, a CLI exit code or a login as proof of publication; read back the public title, body, author and URL after a write. On an unknown write outcome, inspect for the original post before any retry.

## Evidence And Checkpoint

- Publication source commit: `a117afb5a02043d0fbf1fefef0594fc9588832c7`, branch `codex/outreach-alpha5`, pushed to the existing public repository.
- Independent reviewer `01a1027c-2d56-7ef1-9d0f-bc110526d63d`: `gpt-6.1-sol / high`, RUNTIME_VERIFIED from its turn context. One SHA256-scope wording finding fixed; closing review PASS. The ignored report is retained locally in `build/outreach-alpha5-review.md`, not uploaded.
- Duplicate checks: OpenVINO discussion search for the project returned zero; GigaAM project-title search and existing issues by this author returned zero; the HF artifact repository had no discussions. One post per destination was created. GitHub/HF existing authenticated identities matched the intended owner.
- Readback comparisons normalize CRLF/LF and trailing whitespace only. All three discussion/issue bodies and the remote article matched the frozen reviewed text.
- `main` / `origin/main` remain `fbd0a53ae1052a34bdc09528c907d7ed8c1948f6`; `features/next` / its remote remain `8700d1d8d6288877287328ba9da0363633693113`. Only outreach Markdown is changed on the new branch. One worktree; no stash or detached HEAD was introduced.
- Ignored boundaries are unchanged: `.hf` credentials remain private; `.venv`, `.wix`, `build`, `dist`, `hf_export`, `models` and bytecode are local tooling/generated artifacts; recordings, log and user config remain private runtime data. The reviewer added only the classified ignored report. No secret, recording, model or config was staged.
- Validation: independent source/rules review, `git diff --check`, staged filename review, public repository visibility, exact remote publication readbacks. App/model tests were not rerun for this documentation-only change; running app and model memory were not touched.
- Next action: after the user confirms the ODS email, inspect the legitimate project-add form, its rules and required fields, then submit only the reviewed project description if no further agreement or missing input is required. Do not bypass the verification gate.
