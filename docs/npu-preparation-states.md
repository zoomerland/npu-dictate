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
- [ ] Perform live cold-cache and warm-cache acceptance in a separate gate.

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

No current runtime/driver/UI acceptance is claimed. No app, model/cache or packaged
binary was changed on the running system.

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

Save this feature as a local commit on `codex/npu-preparation-states`. Do not merge
to `features/next` or `main`, push, rebuild EXE/MSI, or restart the existing app in
this gate. The precise next action is owner-authorized live NPU startup acceptance
using the plan above; until then the overall roadmap checkbox stays open.

## Live Acceptance (Not Run)

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
