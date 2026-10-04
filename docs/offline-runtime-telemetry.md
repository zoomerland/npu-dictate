# Optional OpenVINO Telemetry

## Scope And Plan

Disable the optional Python OpenVINO telemetry package for this application's
runtime without changing machine-wide consent, removing installed packages or
blocking the explicit model downloader. No GUI, microphone, paste or model-quality
changes belong to this feature. Live UI/microphone acceptance is deferred by the
owner, not recorded as passed.

- [x] Inspect the observed clean-home telemetry attempt and installed fallback.
- [x] Keep NPU preparation work preserved on its separate branch.
- [x] Apply a process-local policy before all three runtime entrypoint imports.
- [x] Configure a frozen runtime hook and exclude the optional telemetry package.
- [x] Validate fresh-process imports without a telemetry opt-out file.
- [x] Complete regression tests and independent review.
- [x] Prepare the reviewed local feature checkpoint; leave integration/publication
  to a later gate.

## Evidence And Decision

The preceding isolated NPU preparation check blocked a GA4 `urlopen` attempt
during dependency import, before audio or native inference. The installed
OpenVINO 2026.2.0 conversion/import utilities import `openvino_telemetry` as an
optional dependency and catch `ImportError` to use their own
`openvino.tools.ovc.telemetry_stub`. The test's isolated consent file disabled
the attempt, but did not fix product startup on a fresh user's machine.

The source runtime now makes that optional package unavailable in `sys.modules`
before third-party imports. Python's `None` module entry raises
`ModuleNotFoundError`, selecting OpenVINO's existing fallback. This does not
replace OpenVINO Core, compilation, inference, tokenizer or downloader code.
The policy is idempotent. If a telemetry root or child module is already loaded,
it raises a clear startup error rather than pretending to undo earlier activity.
Applications embedding these helpers must initialize the policy in a fresh
process before importing OpenVINO.

The three protected entrypoints are `voice_dictation_app.py`,
`gigaam_openvino_asr.py` and `rupunct_restore.py`. The PyInstaller spec includes
the helper, excludes `openvino_telemetry` and runs the same policy in a custom
runtime hook before application imports. No global environment or consent file
is written. Explicit first-time model downloads remain unchanged.

This is a targeted optional-Python-telemetry policy, not an OS network sandbox
or proof about every native component or every third-party dependency. Future
dependency upgrades must keep the real fallback/import regressions passing.

## Git And Ownership

Started from `features/next` at
`8700d1d8d6288877287328ba9da0363633693113` in
`codex/offline-runtime-telemetry`, after reviewing the sole worktree, refs,
remotes, stash and ignored boundaries. No stash or detached HEAD was present.
`main` / `origin/main` remain at
`fbd0a53ae1052a34bdc09528c907d7ed8c1948f6`.

`codex/npu-preparation-states` retains two unique commits, `8c6d9ff` and
`1fe6bae`, with its cold/warm native evidence. It was not merged, cherry-picked
or rewritten. Existing outreach/research branches remain preserved and outside
this feature. Their established classifications were not changed.

Ignored boundaries remain private/local: `.hf` credentials; user config/log/audio;
models and caches; dependencies and generated build/release artifacts. The
preceding native-check harness and receipts under `build/native-preparation-check`
remain retained local evidence, not new product source or disposable residue.
Only the narrow policy, packaging configuration, tests and documentation belong
in this feature's commit. No release, app restart or installed-binary change is
authorized by these headless checks.

## Validation

Main profile: `gpt-6.1-sol / xhigh`, verified from the fresh turn context.
Test worker: `01a103ca-0eea-7e21-8202-c7fc21aea9dc`, `gpt-6.1-sol / high`,
verified from its fresh runtime turn context. Its write scope is only the focused
test module, disjoint from parent-owned implementation/documentation.
Independent reviewer: `01a103cb-7e3b-7a10-805a-6af875ddda14`,
`gpt-6.1-sol / high`, verified from its fresh runtime turn context.

Verified on 2026-10-04 (Europe/Moscow):

- Existing headless compatibility suite on the modified source: 69 tests PASS.
- Focused telemetry regressions: 16 tests PASS (worker and independent reviewer).
- Final parent-run `tools/headless_ux_checks.py`: 85 tests PASS, including those
  same 16 tests, not 16 additional distinct tests.
- `git diff --check`: PASS.

The four real-import probes cover OpenVINO directly, the voice app module, the
ASR wrapper and punctuation wrapper in separate fresh processes. They remove
vendor CI opt-outs and use empty temporary home/data directories with no consent
file, not the earlier helper's injected opt-out. Actual OpenVINO and dependency
imports are retained; only audio/input/tray operations are replaced with forbidden
or inert boundaries. Tk creation, network access and model artifact reads are
guarded. Each probe confirms the genuine vendor fallback and callable Core API,
without constructing Core, loading a model or running app main.

The network violation latch remains observable even when a background exception
is swallowed. Probes wait for Python workers, inspect the final exit receipt and
use bounded subprocess timeouts with disk-backed capture; all final subprocesses
exited. Pure/AST tests also cover idempotence, rejected late imports, unchanged
environment, no consent/IO side effects, early entrypoint ordering, and spec/hook
configuration. These Python guards are mistake containment, not an OS sandbox.

Independent final review found no actionable product/test issues. The frozen
test file SHA-256 is
`d1ad049bb0700ab76ed6215fd912bd5f561e9eedc253ef7c54baec770b8036ce`;
the policy helper SHA-256 is
`5c94d7cc065586fc067ee4c5b60d89c559d3cce60d4f119c182b843e40daa9c9`.
The reviewer's pre/post-run hashes matched the frozen source. The parent then
completed aggregate integration and the 85-test gate.

### First-Red Checkpoint

The initial test's model-data guard treated any `models` path component as an
artifact root, incorrectly blocking imported dependency source such as
`transformers/models/auto`. This produced a first-red import result, not a
product model or telemetry failure. The worker diagnosed the source match,
restricted the guard to the actual workspace model-data root, and added a guard
regression. The review also caught inherited `TF_BUILD`, which could hide
telemetry behind the vendor's CI opt-out; it is now removed in probe environments.
Only after these corrections were the 16-test focused and 85-test aggregate
gates accepted. No earlier result is substituted for a failed run.

Source/spec review does not prove a rebuilt EXE/MSI's runtime behavior, native
telemetry or model inference compatibility. No new package was built or published,
no app was restarted, and no microphone or real input operation was requested.
Recognition algorithms, model data, caches, user config and global consent were
outside the implementation write scope. The next integration/build gate must
retain the early policy and test the resulting frozen imports without an opt-out
file. Owner-deferred UI/microphone checks remain deferred, not passed.
