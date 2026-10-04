# Settings Opening Responsiveness

## Scope and Evidence

Owner reported approximately five seconds on every settings opening, including
repeated openings after both models were ready. Recording hold/toggle and paste
acceptance passed in the preceding live check.

Read-only profiling of the real settings constructor with fake widgets and
actual local model metadata on 2026-10-04 reproduced 6.096 seconds. Of this,
6.081 seconds was in 24 `model_is_installed` calls; nine punctuation readiness
checks accounted for 5.539 seconds. The constructor repeatedly parsed local
JSON files, including the tokenizer. The measured microphone enumeration was
0.0011 seconds; the Startup shortcut check was 0.0005 seconds.

No real window, microphone recording or model inference was used in this probe.
The fake-widget result isolates blocking Python work, not Windows rendering.

## Implementation Plan

- Render settings with a localized checking state for model availability.
- Check each distinct profile once per background pass and publish through the
  existing event queue; never run model file readiness checks in UI callbacks.
- Coalesce refresh requests, permit one worker, and reject results from closed
  or superseded settings windows.
- Preserve the selected models, devices, microphone, unsaved edits and existing
  runtime/download integrity checks.
- Verify blocked checks, language changes, close/reopen, late results, failure
  recovery and settings construction without opening windows.
- Commit the fix separately. Live restart/acceptance follows source validation;
  stable branch, published binaries and remote remain outside this fix.

## Git and Validation Checkpoint

Branch `codex/settings-open-responsiveness` starts from `features/next`
`9cb9e6a22e2f0c842cfa1225432644612ef723c5`. Delta revision against
`build/autonomous-roadmap-20261004/checkpoint.md`: all three worktrees clean,
HEAD/ref values unchanged, no stash, detached worktree or unresolved index.
Main/origin/main remain `fbd0a53ae1052a34bdc09528c907d7ed8c1948f6`;
origin/features/next remains `8700d1d8d6288877287328ba9da0363633693113`.
Remote and ignored/private classifications are unchanged. The new feature
branch is the only intended ref addition. Running application remains loaded
from the preceding integration source until a separately coordinated restart.

Current parent profile: gpt-6.1-sol / xhigh, runtime verified. Owner explicitly
selected the increased effort; keep it for this bounded debugging/fix phase.

Status: source implementation, automated tests, independent review and owner
live responsiveness acceptance PASS.

## Intermediate Validation

Nine focused lifecycle/UI tests PASS. First focused red was in test fixtures:
zero refresh interval allowed an intentional queued second pass, and a hardcoded
microphone label disagreed with the existing translation. Corrected the clock
fixture and used the authoritative translation; production guards unchanged.

The same fake-widget constructor with actual local model metadata after the fix
took 0.0052 and 0.0026 seconds on two openings. Availability checks completed in
the background in approximately 0.3652 and 0.2946 seconds. These are local Python
timings, not a guarantee about native rendering or every storage/device setup.

First aggregate run: 221 discovered, one failure and one skip, 85.896 seconds.
`RealImportTests.test_rupunct_wrapper_real_dependencies_fresh_home` exceeded its
unchanged 45-second timeout; the subsequent voice-app import probe was skipped
by the existing first-red rule. All other reported cases passed. This source fix
does not change rupunct_restore, model_setup or the import probe/timeout. Retain
this red separately and diagnose before claiming an aggregate PASS.

The unchanged isolated punctuation import probe then passed in 28.117 seconds.
A complete repeat of the aggregate passed all 221 cases without skips in
70.176 seconds (exit 0). No timeout or other guard was weakened. Final receipt:
`build/settings-open-responsiveness/headless-final.log`. The first timeout remains
historical evidence of variable import latency, not a demonstrated regression
in this settings fix or a guarantee about future cold-import times.

## Resulting Behavior

Settings construct using only in-memory availability state. A daemon worker
checks the four current profiles once each per pass and publishes an immutable
result through the app queue. Main-thread handling updates labels while retaining
the selected IDs, microphone and dirty flag. Requests coalesce with a five-second
minimum refresh interval; close/reopen cancels the old generation and does not
start overlapping workers. Checking and unavailable results have RU/EN labels;
unknown is never described as a model that needs downloading.

Runtime/download integrity checks still use their existing implementations.
The metadata tokenizer parsing was moved out of settings rendering, not removed.
Cache/model storage measurement remains the existing independent background task.

The synchronous hardware fallback for opening settings before the loader has
published hardware information is pre-existing and outside this measured
after-ready reproduction. Microphone, filesystem/Startup metadata and native
rendering can also have machine-specific latency; these timings do not establish
a universal bound on all settings-opening scenarios.

The owner-authorized source restart and subsequent responsiveness check are
complete; exact live evidence is recorded below. No installed build, publication,
cache cleanup or main promotion is included.

## Final Review and Gate

Independent reviewer `01a1071d-dc3f-71a1-8ce7-ef462985f7a5` used
gpt-6.1-sol/high with fresh runtime verification. Initial review found P3:
a repeat worker-start failure changed the snapshot but left old visible labels.
The failure now signals the UI to refresh; a regression covers unavailable
labels, unchanged dirty state and successful retry. Reviewer rechecked that
delta, ran all ten focused cases plus an additional dirty/Russian/selection
probe, and closed P3 with final PASS. Retained private review:
`build/settings-open-responsiveness/reviewer.md`.

Final aggregate after the review fix: 222 tests PASS, no skips, exit 0,
73.819 seconds. Receipt: `build/settings-open-responsiveness/headless-after-review.log`.
Product revision hashes match the reviewed candidate. No test/build process
remains required for this source gate. Subsequent live timing is recorded below.

Full pre-commit Git revision rechecked all three worktrees, heads/remotes,
stashes, detached/index state and ignored metadata. Only the announced nine
source/test/report/roadmap files are commit candidates; historical refs remain
preserved and classified as in the base checkpoint. Other managed worktrees
remain clean with no ignored residue. Primary credentials/dependencies, user
models/audio/config/log, generated artifacts and retained evidence stay local.

Owner's additional roadmap request records future Escape cancellation and an
Enter-finish design discussion as unchecked items. This commit changes no
recording key behavior. At the source-commit checkpoint, main, features/next and
remote refs were unchanged, with the source fix on its own feature branch pending
live acceptance.

## Live Acceptance and Integration

After explicit owner authorization, the app was restarted from source commit
`9c40c4e6f83ea907d14d4f1bd316355bca4bf2ad`. Existing settings, model weights and
compiled cache were retained; the configuration SHA256 remained unchanged.
Both speech and punctuation loaded on NPU before the owner check.

Owner feedback on 2026-10-04: settings now open practically instantly. Two
constructor timings in the updated process were 0.155 and 0.149 seconds.
These log values measure settings construction, not a Windows first-paint
instrumentation; perceived responsiveness is separately confirmed by the owner.
The repeated after-ready delay is accepted as fixed. Broader cold-start/device,
mixed-DPI and accessibility scenarios are not newly claimed as tested.

The documentation-only acceptance commit follows the tested source commit.
All reviewed product hashes and the 222-test receipt remain applicable; no code
changed after those gates. Integrate this accepted branch into features/next
with a no-fast-forward merge. Main/remote/publication remain separate owner
gates. The running app already contains the accepted fix and needs no restart
for the documentation update or identical-source local merge.
