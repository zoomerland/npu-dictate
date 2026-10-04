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

1. [ ] Show model-storage usage in Settings: model files, compiled cache and
   incomplete downloads. Read metadata in a background worker, avoid links and
   report incomplete/unavailable measurements honestly. Cover stale results,
   close/reopen, localization and errors using fake UI and temporary files.
2. [ ] Resume interrupted model downloads when the remote representation can be
   validated. Retain final size/hash checks, restart safely for changed or
   non-resumable responses, preserve the installed target on failure, and keep
   speed/remaining-byte reporting meaningful. Test HTTP responses in memory.
3. [ ] Verify and finish installed-build startup-toggle support using fake COM,
   temporary paths and frozen/source-mode tests. Never modify the real Startup
   folder merely to test this feature.
4. [ ] Reassess model/cache maintenance after storage and download contracts are
   settled. Implement only scoped, explicit user-triggered operations whose
   idle/lifecycle and filesystem boundaries can be checked automatically.
5. [ ] Reassess remaining roadmap tasks after each accepted block. Safe isolated
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

Next: implement storage and resumable downloads in disjoint worktrees while the
parent examines installed-startup behavior and owns roadmap/integration records.
