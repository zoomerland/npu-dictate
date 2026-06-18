# Code Signing Policy

Status: pending SignPath Foundation approval.

NPU Dictate signs and distributes Windows release artifacts. The signing plan is designed so users can trace signed binaries back to the public source repository and GitHub Actions build that produced them.

## Windows

Planned statement if the project is approved:

> Free code signing provided by SignPath.io, certificate by SignPath Foundation.

### What Will Be Signed

- Windows installer packages (`.msi`) published on GitHub Releases.
- Windows packaged application archives (`.zip`) published on GitHub Releases, when practical.

Model weights and converted model artifacts are not bundled in signed installers. They are downloaded separately from the documented Hugging Face model repository and verified by file size and SHA256 where the NPU artifact downloader is used.

### Build And Signing Process

- Release artifacts are built from the public GitHub repository using GitHub Actions.
- Unsigned artifacts are uploaded as GitHub Actions artifacts before any signing request.
- After approval, only CI-built release artifacts will be submitted to SignPath.
- The private key is held by SignPath; this project does not store a code signing private key.
- Signing requests are intended for tagged release or pre-release builds such as `v0.1.0-alpha.1`.

### Product Metadata

Windows artifacts use these product metadata values:

- Product name: `NPU Dictate`.
- Product version: `0.1.0-alpha.1` for the first public pre-release.
- MSI `ProductVersion`: `0.1.0`, because Windows Installer requires a numeric three-part version.

## Team Roles

This is currently a single-maintainer project.

- Authors and committers: [`zoomerland`](https://github.com/zoomerland).
- Reviewers: [`zoomerland`](https://github.com/zoomerland).
- Approvers for signing requests: [`zoomerland`](https://github.com/zoomerland).

Policy: external pull requests must be reviewed by the maintainer before merge. Each signing request requires explicit maintainer approval unless a future SignPath policy restricts signing to protected release tags built by GitHub Actions.

## Distribution Locations

- Source repository: https://github.com/zoomerland/npu-dictate
- Releases: https://github.com/zoomerland/npu-dictate/releases
- Converted OpenVINO model artifacts: https://huggingface.co/Zoomerland/local-voice-dictation-openvino

## Privacy Policy

Normal dictation is local-first. Microphone audio, ASR, punctuation, and text insertion run on the user's machine.

NPU Dictate will not transfer microphone audio, recognized text, or user documents to networked systems unless the user explicitly requests an operation that requires network access.

Network access is used for first-time model download/preparation unless the required models are already present locally. Converted artifacts are downloaded from the documented Hugging Face model repository.

Local files that may contain private data, such as `voice_dictation_config.json`, `voice_dictation.log`, and optional debug recordings, are ignored by Git and are not uploaded by the application.
