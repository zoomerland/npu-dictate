# NPU Preparation States

## Scope

Make model preparation explicit before recording. Do not change ASR segmentation,
decoding, quantization, model files or microphone/input behavior. Do not restart
the running app, build packages or publish this feature without a separate gate.

## Plan

- [x] Inspect the lazy ASR compilation path and existing startup hang guard.
- [x] Record the Git and privacy boundaries before implementation.
- [x] Run the unchanged hermetic UX baseline: 69 tests PASS.
- [x] Expose preparation, actual cache result, warm-up and readiness separately.
- [x] Keep preparation asynchronous and bind statuses/results to generations.
- [x] Block recording until required preparation succeeds; surface failures.
- [x] Cover enabled/disabled preparation and cold/cache/unknown results offline.
- [x] Complete independent review and the final offline regression gate.
- [x] Perform isolated native cold-cache/warm-cache and saved-audio checks.
- [ ] Complete live UI, microphone and recording-mode acceptance separately.

## Initial Evidence

`GigaamOpenVinoCtcAsr.__init__` does not compile a bucket. `_compile` first runs
from inference or `warmup`. The app's `_warmup_models` explicitly skips NPU ASR
to avoid historical startup hangs. `_load_models` can then publish `loaded=True`
and `Ready`, leaving the first recording to absorb preparation. Punctuation is
compiled during construction but its first inference also needs explicit handling.

The implementation must not assert a cache hit merely because a cache directory
contains files. OpenVINO's read-only `LOADED_FROM_CACHE` compiled-model property
reports the actual result after `compile_model` returns; unsupported property
queries must remain unknown. Compiler progress has no trustworthy percentage or
ETA. See [OpenVINO properties](https://docs.openvino.ai/2025/api/c_cpp_api/classov.html).

Native compilation cannot safely be killed by cancelling a Python thread. Offline
tests establish state/ownership rules, not native driver liveness or Tk rendering.

## Git Checkpoint

Before this feature:

- One clean worktree; no stash or detached HEAD.
- `main` / `origin/main`: `fbd0a53ae1052a34bdc09528c907d7ed8c1948f6`.
- `features/next` / its remote: `8700d1d8d6288877287328ba9da0363633693113`.
- The two integration trees have no content differences.
- Start `codex/npu-preparation-states` from `features/next` at the above hash.
- `codex/outreach-alpha5` retains its three unique documentation commits,
  including local-only `7904c3d`; do not transfer them into this feature.
- `codex/outreach-launch-kit` retains its unique documentation commit.
- `codex/research-dictation-cleanup` retains its unique roadmap research note.
- `codex/press-enter-after-paste` is patch-equivalent to integrated work.
- Other existing local branches are integrated by ancestry. No refs were deleted
  or rewritten, and no unrelated pending work was adopted.

Ignored boundaries are retained: `.hf` credentials; private runtime config/logs
and `recordings`; local dependencies in `.venv`/`.wix`; generated `build`, `dist`,
`hf_export`, `models`, and bytecode. None belongs in the feature commit.

## Validation Boundaries

Main runtime: `gpt-6.1-sol / xhigh`, verified from this task's current turn context.
Implementation worker: `01a10319-4b8e-7642-8ca2-f58a1cb8d767`, requested
`gpt-6.1-sol / high`; its fresh turn context confirms that profile. Code changes
and headless tests have a disjoint write scope from this parent-owned report.

Independent reviewer: `01a10321-0dd0-7261-b9eb-3a1aedd8de5f`, requested
`gpt-6.1-sol / high`, confirmed by its fresh turn context at
`2026-10-03T18:57:43.586Z`. Review begins provisionally while code is in flight;
a final verdict requires the frozen implementation handoff.

Final parent-run corrected-code checks:

- `.venv/Scripts/python.exe -B tools/headless_ux_checks.py`: 93 tests PASS,
  including the original 69 tests and 24 new preparation tests.
- `.venv/Scripts/python.exe -B tools/smoke_checks.py --suite preparation`:
  the same 24 preparation tests PASS, through the hermetic guards. This is a
  subset check, not another 24 distinct tests or native model smoke.
- `git diff --check`: PASS.

Review closed an in-flight callback lifetime defect and a provisional P2 UI
defect: current-generation background preparation could replace the active
transcription display/timer. Startup callbacks now detach from runtime inference;
background progress updates the model section without replacing active dictation
UI. Both have deterministic regression coverage. The independent frozen-code
review passed with 90 tests. Its CPU no-`warmup` coverage gap is now closed with
a fake-model regression. Pending hotkey start/toggle also preserves the precise
current native preparation phase instead of replacing it with generic loading.
Actual failures, disabled-warmup recording and stop commands remain unaffected.
Focused final re-review passed. The reviewer independently ran the corrected
93-test aggregate and checked the frozen hashes before/after verification; no
remaining actionable source findings were reported. This is an offline PASS,
not deployment, release or native-driver acceptance.

The preceding results establish offline acceptance only. The subsequent isolated
native checks are recorded below; real UI/microphone acceptance remains open.
No running app, user model/cache or packaged binary was changed.

The old NPU startup hang guard is replaced, not merely relabelled: native
compile/inference now occurs before readiness in background preparation. Keep
this feature out of a release until the cold/warm driver acceptance is performed.

### Final-Gate Red Checkpoint

After the CPU-default and pending-hotkey regressions, the aggregate suite passed
93 tests. The parent-run preparation subset then failed one of 24 tests:
`test_asr_compile_runs_in_background_without_engine_lock` observed a trailing
`Warming ASR: 400 frames` instead of `Ready`. Do not substitute the earlier green
run for this result or retry blindly. The fixture started `_load_models` directly
without normal loader ownership; its record attempt could create a second loader.
The worker is correcting ownership/cleanup in that fixture before rerunning the
gate. No commit, restart or native acceptance was performed after this red result.

The correction uses normal `load_async` ownership, counts loader/compile/inference
calls, joins every fixture thread and shuts the fake engine down. An intermediate
fixture-only assertion also failed because its configuration requested five
default buckets while expecting one compile; the fixture now explicitly selects
bucket 400. Neither red result is erased. No production-code change was needed
for these fixture corrections. Worker post-fix checks: preparation 24 PASS in
three successive runs and aggregate 93 PASS. The final parent run passed both
93-test aggregate and 24-test preparation subset; independent re-review also
passed the 93-test aggregate. Both original red outcomes remain documented above.

## Source Handoff

The final delta review confirms one owned feature worktree with only the nine
scoped source/test/documentation files changed. The integration/remote refs and
the retained outreach/research branches remain unchanged; no stash or detached
state exists. No secret/private runtime artifact belongs to the source checkpoint.

Implementation was saved as local commit `8c6d9ff` on
`codex/npu-preparation-states`. Do not merge to `features/next` or `main`, push,
rebuild EXE/MSI, or restart the existing app in this gate. The overall roadmap
checkbox stays open until the remaining live UI/microphone checks are completed.

## Isolated Native Acceptance

Verified on 2026-10-04 (Europe/Moscow), against source commit `8c6d9ff`, using
OpenVINO `2026.2.0-21903-52ddc073857-releases/2026/2`, Intel Core Ultra 5 135U
and Intel AI Boost. Three serialized fresh helper processes used a new isolated
OpenVINO cache, not the user's cache. NNCF INT8 ASR bucket 400 and static-128
punctuation both reported `EXECUTION_DEVICES = [NPU]`. Silero VAD used CPU,
as in the production segmentation route; no claim of an entirely NPU-only
pipeline is made.

| Case | Readiness, s | Actual ASR/punctuation cache result | First ASR, s | Punctuation, s |
| --- | ---: | --- | ---: | ---: |
| Empty isolated cache, warm-up on | 73.625 | Both miss | 0.407 | 0.015 |
| Same cache, fresh process, warm-up on | 8.922 | Both hit | 0.407 | 0.031 |
| Same cache, fresh process, warm-up off | 7.156 | Punctuation hit; ASR loaded from cache at first use | 1.641 | 0.109 |

Readiness timings start at receipt initialization and include dependency imports;
they are observations from one run per case, not a guaranteed startup duration.
The empty cache is application-cache cold, not a factory-reset machine/driver.
Actual cache properties, not blob presence, support the hit/miss results.

In both prepared cases, each real native warm-up returned successfully before
the first `Ready` event. First saved-audio inference retained the same compiled
model identities and bucket keys, with no startup preparation statuses. The
disabled case reported `Ready - warmup deferred`, had no compiled ASR at readiness,
then loaded exactly bucket 400 at inference. It is a deferred control result,
not fully prepared acceptance.

The existing private reference WAV is 12.48 seconds long: five VAD segments,
24 output words. Raw and punctuated output hashes match across all three cases.
This checks startup consistency, not transcription accuracy against a human
reference. No raw audio or transcript was printed or added to Git. Recognition
used the production VAD/segmentation and punctuation methods, not microphone
capture, the full paste pipeline or a GUI instance.

Python main-thread readiness sampling continued during native preparation:
maximum observed polling gaps were 0.157 s cold, 0.344 s cached and 0.125 s
deferred. The normal polling interval was 0.1 s. These observations do not prove
Tk rendering, settings/exit responsiveness or safe cancellation of a native call.

### Isolation And Review

The ignored helper and receipts are retained under
`build/native-preparation-check/`; they are local test evidence, not product code.
The final helper SHA-256 is
`9f424a5b2a08f6fd4642ac986024dd1f32091989a1783410f95e5f63bfb2524f`;
wrapper SHA-256 is
`f5e54bd00b78f963d317ee37d803cd080d3d5411ef0aaac00e21459055aace5c`.

The helper redirects data/cache/temp directories, returns validated read-only
model paths instead of downloading, disables app logging, and replaces only
microphone readiness with an explicitly inert marker. GUI, microphone, keyboard,
clipboard and network operations are guarded. Hardware discovery, model load,
compilation and inference are real; device fallback is rejected. Python guards
are not an OS/native-code sandbox. The wrapper enforces a 420-second process
deadline, bounded pipe capture, exclusive evidence files and PID-only cleanup.
All final helper processes exited normally, with zero boundary violations and
no timeout; no helper process remains running.

Worker `01a10378-e421-7f33-ae67-aa7d9e01fe87` and independent reviewer
`01a1037f-8f17-7890-ab6d-c892a3e38ebf` each used `gpt-6.1-sol / high`, confirmed
by fresh runtime turn contexts. Independent source review cleared the frozen
helper before native execution. Final native receipts are named `cold-on-v2.json`,
`warm-on-v2.json` and `warm-off-v2.json` in `run-20261003-isolated-v2/`.
The reviewer subsequently checked the native receipts and roadmap/report claims;
timings, properties, deferred-control interpretation and acceptance limits passed.

All 13 converted artifacts matched the local manifest's sizes and SHA-256 before
and after testing. User config hash stayed unchanged. The user log's size/mtime
and all 92 existing user-cache files' paths/sizes/mtimes stayed unchanged; cache
contents were not independently re-hashed. The saved WAV hash also stayed
unchanged. A fresh aggregate run passed all 93 hermetic tests. Integration and
remote refs were not moved; no app restart, model deletion, package or publication
was performed.

### Preserved Import-Guard Failures

The first helper stopped before model loading: a broad socket audit guard blocked
ONNX Runtime's local `socket.gethostname` query. The next import-only diagnostic
confirmed that exact operation; allowing only the local query left real network
guards intact. A second import-only diagnostic then blocked an OpenVINO GA4
telemetry request and encountered a fake sounddevice metadata/introspection
error. Neither diagnostic created an engine or ran native compilation/inference.

The final helper gives missing module metadata normal `AttributeError` behavior
while keeping actual audio APIs forbidden. It creates an opt-out containing `0`
only under its redirected `LOCALAPPDATA` before importing OpenVINO; the installed
consent checker confirmed `DECLINED`. Background boundary violations are latched
so they cannot be ignored by a successful foreground result. Import-only checks
then passed with zero violations, followed by the three native cases above.
All earlier red receipts remain retained; they are test-harness/dependency import
findings, not evidence that NPU inference failed.

The clean-home telemetry attempt is a separate unresolved product follow-up in
the roadmap. The request was blocked before sending in this test; no claim is
made that the product or global dependency preferences have already been fixed.

## Remaining Live UI Acceptance

Use a separate app instance only after explicitly stopping the existing instance.
Do not delete the user's model or cache files to manufacture a cold start. A fresh
temporary data root with existing models supplied non-destructively is preferable.

1. Start with the supported NNCF INT8 NPU ASR profile and preparation enabled.
   While preparation is pending, neither hotkey mode nor overlay mode may start
   recording. Settings and exit must remain responsive.
2. Observe model read/preparation, actual cache-result and warm-up stages. The
   compiler must not show invented percentages or a promised completion time.
   Unsupported cache properties must not be displayed as a definite cache hit.
3. After readiness, dictate the first short phrase and confirm that no deferred
   ASR or punctuation preparation happens inside the recognition operation.
4. Restart using the same cache and repeat. Compare stage timing with the cold
   run; a directory of old blobs alone is not evidence of a cache hit.
5. Disable preparation explicitly, restart and verify that the UI warns about
   deferred first-use work rather than claiming a fully warmed NPU.
6. Change model/device or preparation settings while loading. Old completion and
   progress must not replace the current profile's state or enable recording.
7. In both RU and EN, inspect the overlay, tray and Models section for readable
   stage text, activity indicators and recoverable errors. Re-test hold-to-talk
   and toggle mode after readiness without changing recognition quality settings.

Do not mark native-driver liveness, cold/warm performance or visual acceptance as
passed solely from the offline suite. A native compile that never returns cannot
be safely stopped inside its Python worker; do not promise in-place cancellation.
