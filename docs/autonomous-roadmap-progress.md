# Autonomous Roadmap Work

## Authority And Scope

On 2026-10-04 the owner requested continued autonomous roadmap development until
further safe progress requires their participation. Use bounded feature branches
from `features/next`, independent review where risk warrants it, automated checks
and local integration checkpoints. Live microphone/desktop interaction remains
deferred. Do not treat deferred checks as passed.

The starting integration commit is
`36b236837d30d00bb02e5e2af0a2442c4db7a65c`; its combined headless suite passed
109 tests. `main` / `origin/main` remain
`fbd0a53ae1052a34bdc09528c907d7ed8c1948f6`, and `origin/features/next` remains
`8700d1d8d6288877287328ba9da0363633693113`. Publication and stable-branch promotion
are separate owner decisions. Tests must not restart the installed app, change
its config/startup entry, capture audio or type/paste into user applications.

## Ordered Work

1. [x] Show model-storage usage in Settings: model files, compiled cache and
   incomplete downloads. Read metadata in a background worker, avoid links and
   report incomplete/unavailable measurements honestly. Cover stale results,
   close/reopen, localization and errors using fake UI and temporary files.
2. [x] Resume interrupted model downloads when the remote representation can be
   validated. Retain final size/hash checks, restart safely for changed or
   non-resumable responses, preserve the installed target on failure, and keep
   speed/remaining-byte reporting meaningful. Test HTTP responses in memory.
3. [x] Verify and finish installed-build startup-toggle support using fake COM,
   temporary paths and frozen/source-mode tests. Never modify the real Startup
   folder merely to test this feature.
4. [x] Reassess model/cache maintenance after storage and download contracts are
   settled. Implement only scoped, explicit user-triggered operations whose
   idle/lifecycle and filesystem boundaries can be checked automatically.
5. [x] Reassess remaining roadmap tasks after each accepted block. Safe isolated
   source/runtime/build checks may proceed; broad model quality, real desktop
   rendering, signing and externally visible publication have separate limits.

Do not introduce unrelated ASR quality changes while implementing storage and
download management. Keep current Russian model profiles and CPU/NPU defaults.

## Git And Private Boundaries

The initial revision found a clean sole root worktree, no stash, untracked drift
or detached HEAD. All historical refs match the preceding integration readback
in `build/feature-integration-20261004/pre-merge-checkpoint.md`. Retained outreach
and research work remains unrelated. Preserve both completed preparation and
telemetry branches and their reports.

`.hf`, runtime config/logs, recordings, models/caches, local dependencies and
generated build/release artifacts stay private/local. Model-storage tests use
temporary trees; download tests use synthetic bytes and fake responses. New
managed worktrees contain source only and use the existing Python interpreter.
No dependency installation, large download or private-content inspection is
needed for the first two blocks.

## Runtime Profiles

Parent: `gpt-6-astra / high`, independently verified from the current turn context
at `2026-10-04T01:25:56.391Z`. Retained for a cross-family review of inherited
contracts and coordination of the autonomous batch. Workers are selected by the
bounded task, with fresh runtime evidence recorded before acceptance.

## Checkpoints

- Planning: storage usage is absent; download_url_to_file deletes partial files
  and always starts over; installed-startup code already distinguishes frozen
  mode, so test its actual contract before deciding whether code needs changes.
- HTTP contract reference: [RFC 9110, If-Range](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-range)
  and [206 Partial Content](https://www.rfc-editor.org/rfc/rfc9110.html#name-206-partial-content).
  Resume only a consistent representation and validate partial-response bounds.

### First Source Batch

- Startup commit: `3697a472b90d450a841e37d750c1f2245a124c7f`.
- Storage commit: `ad73cd353998fc252b1de883c57018d3dd984308`.
- Downloads commit: `6e443fb5cc05f2da28ca59d621c413cebab797a7`.
- Parent cross-family source review accepted all three frozen diffs. Review
  corrected the startup empty-placeholder issue and simplified an unnecessarily
  complex read-only storage scanner before acceptance.
- Separate no-fast-forward merges completed without conflicts. Shared runner
  now includes all three focused suites. Combined headless gate: 180 PASS,
  exit 0, 64.744 seconds on 2026-10-04; no skips. Receipt remains local at
  `build/autonomous-roadmap-20261004/combined-headless.log`.
- Worker tests: startup 21 focused plus 26 Settings tests; storage 12 focused;
  download 38 focused plus 13 readiness tests. Do not add overlapping counts.
- Real HTTP, Tk/DPI rendering and Windows sign-in remain unverified. No app
  restart, user-state mutation or model download took place.

### Isolated Package Check

- Four diagnostic regressions added; combined headless suite 184 PASS, and
  separate packaging safety suite 18 PASS.
- Independent source review PASS; isolated PyInstaller build and actual EXE
  fresh-home import smoke PASS. Archive lacks optional OpenVINO telemetry;
  genuine vendor fallback is active. No model or user config was created.
- Full evidence and scope: `docs/packaged-offline-verification.md`. This EXE
  precedes deferred cache maintenance and is not a release artifact.

### Deferred Cache Maintenance

- Source commit `accb2b4246c3b8c0807b571c55e8e7b595eb7bc7`, independently
  reviewed by parent and integrated without conflicts.
- Explicit request/cancel controls; cleanup runs after the instance lock and
  before model construction, never in smoke mode or a secondary instance.
- Preflight and deletion are bounded to the fixed app cache subtree. Failures
  consume a started request and remain visible; no silent repeated purge.
- Review added final empty-root/identity validation and prevented runtime
  deletion requests/temporary state from entering Git or distributable payloads.
- Worker final gates: 38 focused cache/UI/payload tests and inherited 109-test
  aggregate PASS. Their overlapping counts are not a total. Windows metadata
  and Git-stdin first-red evidence is retained in `docs/cache-maintenance.md`.
- Parent shared-runner registration includes all 28 cache regressions.

### Final Combined Acceptance

- `tools/headless_ux_checks.py`: 212 PASS, no skips, exit 0, 60.362 seconds.
- `tools/test_release_payload.py`: 21 PASS, no skips, exit 0, 13.806 seconds.
- The combined tests include the actual merged startup/smoke control flow:
  smoke and secondary instances bypass cache maintenance; normal acquired startup
  checks maintenance before any app/model construction.
- Source integration before this report: `526e89c78da50c7b2557c0a13e67b5db16551af5`.
  Separate frozen-verification merge: `2b9f3dee4416bc9fcef28138c7798a25378523f1`.
- Full Git revision covered all three worktrees, branch/remote refs, stashes,
  unresolved index state and private metadata. Historical outreach/research
  refs remain preserved, not silently integrated; no new unresolved ownership.
- All feature workers/reviewer are closed and required test/build sessions exited.
  The managed source worktrees are retained clean on their accepted commits.
- Existing `.hf`, models, recordings, user config/log, dependency environments,
  `dist` and earlier build evidence remain private/local. New isolated build and
  synthetic test receipts are retained evidence, not release payload candidates.
- No normal app launch, microphone capture, real input, production-cache cleanup,
  installed update, main promotion, remote push, tag or publication occurred.

The final local checkpoint is ready for owner-led live/installed acceptance.
No background work is left running. This closes the selected autonomous source
batch, not every optional/future item in the roadmap. Any new release must be
built from the final integrated source; the isolated telemetry EXE above predates
the cache feature and must not be mistaken for that release.

Keep the installed app and published binaries unchanged. The next owner gate
is live/installed acceptance and a decision about stable-branch promotion;
the remaining deferred research/features below are not silently taken into scope.

### Owner Daily-use Acceptance

After the owner-authorized source restart and settings responsiveness fix, the
owner reports continuous use and confirms all ordinary checks T1-T20 PASS.
This includes both recording modes, onset, hotkeys, paste/focus, Enter-send,
review-stop, clipboard behavior, longer dictation, interface localization,
settings, overlay/tray, single instance, model UI and source startup behavior.
The stable test IDs, evidence scope and limitations are recorded in
[manual acceptance](manual-acceptance-20261004.md).

The owner explicitly did not perform separate-stage checks T21-T25. No installed
update, production-cache cleanup, download interruption or broad cold/warm-cache
acceptance is implied. The accepted source is `features/next` at `8bc76a6`; the
settings fix has a 222-test headless receipt. This documentation update changes
no product code, running process, main/remote ref or published artifact.

### Remaining Acceptance Boundaries

Autonomy does not waive the owner's remaining acceptance gates. Following the
ordinary owner-confirmed checks above, these remain separate:

- Coordinated cache-maintenance and cold/repeated-cache checks T23-T24, including
  disabled warm-up. Current daily-use success does not close every preparation
  failure/shutdown or settings-during-preparation transition.
- Installed shortcut launch at Windows sign-in, MSI upgrade/uninstall, mixed-DPI
  rendering, native tray menus and screen-reader interaction.
- Live interrupted-download acceptance against the model host. The synthetic
  protocol tests cover errors, not that host's current Range/ETag behavior.
- Broader ASR/bucket/GPU/language changes require separate model selection,
  measured quality evidence and acceptance; current Russian quality is preserved.
- Full-field repunctuation requires a safe editor-specific replacement path;
  no selection fallback is authorized. Stable USB input identity requires real
  device reconnection evidence before changing microphone-selection guarantees.
- Signing, publication, `main` promotion and updating the installed app remain
  separate owner gates. Optional later language/cosmetic work does not supersede
  the outstanding Russian packaged-flow acceptance.

Cache recompilation is distinct from regenerating converted/quantized weights.
The former can be requested via the bounded cache action; the latter must not
be advertised as implemented without a separate reproducible conversion design.
