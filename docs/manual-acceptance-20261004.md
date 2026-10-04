# Owner Live Acceptance: 2026-10-04

## Scope and Evidence

The owner reports using the running source application continuously and confirms
that all ordinary checks T1-T20 passed. The separate stage T21-T25 was explicitly
excluded. This records owner-reported acceptance, not new agent-operated tests or
independently measured timings for each scenario.

The accepted integration source is `features/next` at
`8bc76a6faae201c1ea299082c1bee05833bb2710`. The running app was restarted with
owner authorization from `9c40c4e6f83ea907d14d4f1bd316355bca4bf2ad`; subsequent
acceptance documentation and integration did not change its product code.
The existing 222-test headless receipt remains applicable; it was not rerun for
this documentation-only update. Settings responsiveness has separate measurements
in [the fix report](settings-open-responsiveness.md).

## Ordinary Checks: Owner Reports PASS

- [x] T1: Settings display correctly, open promptly and do not hang.
- [x] T2: The first dictated word is retained on immediate speech onset.
- [x] T3: Automatic insertion succeeds with fast perceived processing.
- [x] T4: Hold-to-talk stops on release and inserts once.
- [x] T5: Toggle mode starts and stops on successive presses.
- [x] T6: Recording hotkeys work in both modes and persist after restart.
- [x] T7: Enter-after-successful-paste sends once when enabled.
- [x] T8: Review-stop inserts without sending despite enabled Enter-send.
- [x] T9: Insertion works in the owner's ordinary browser and desktop apps.
- [x] T10: Switching applications/tabs does not reuse the old insertion target.
- [x] T11: Clipboard restore/retain behavior follows the selected setting.
- [x] T12: Longer speech, pauses and fast phrases have no major lost-text,
  hanging or artificial mid-sentence paragraph regression.
- [x] T13: Russian/English interface changes apply immediately; ASR remains Russian.
- [x] T14: Apply/Save and unsaved-close warning preserve the intended edits.
- [x] T15: Overlay drag, size, shape, opacity and position persistence work.
- [x] T16: Tray recovery and overlay hide/show hotkey work.
- [x] T17: A second launch does not create a second working instance.
- [x] T18: Model/device/status information and background refresh are usable
  without freezing settings or resetting unsaved edits.
- [x] T19: Recording waits for readiness while settings remain accessible;
  loading status clears when preparation completes.
- [x] T20: Startup setting/behavior accepted for the current source application.
  This does not establish installed-build sign-in behavior.

This is practical acceptance on the owner's current setup, not a claim of
error-free ASR, every possible input field, mixed-DPI/accessibility coverage,
every preparation failure/shutdown transition, or additional speech languages.
Known recognition limitations remain documented in the roadmap.

## Separate Stage: Not Performed

- [ ] T21: Real model download percent, speed, remaining data, file and errors.
- [ ] T22: Interrupted host download, validated resume and corrupted-file rejection.
- [ ] T23: Cache request/confirmation/cancellation and next-launch cleanup outcome.
- [ ] T24: Coordinated cold/repeated-cache startup and disabled-warmup comparison.
- [ ] T25: Current installed build, MSI upgrade/uninstall and installed sign-in launch.

Do not clear production models/cache, change startup entries, reinstall or restart
solely to close these checks without coordinating the corresponding owner gate.
Escape cancellation and Enter-to-finish-recording remain future roadmap work;
they are not the implemented Enter-after-paste feature accepted by T7.

## Documentation Checkpoint

Before this update, all three worktrees were clean with no stash, detached HEAD
or unresolved index. Delta revision against the accepted/integrated section of
`build/settings-open-responsiveness/checkpoint.md` confirmed the integration ref
above, cache worktree `accb2b4246c3b8c0807b571c55e8e7b595eb7bc7`, and download
worktree `6e443fb5cc05f2da28ca59d621c413cebab797a7`. Historical refs and remote
configuration remain unchanged; no new unique branch work requires classification.
`main`/`origin/main` remain `fbd0a53ae1052a34bdc09528c907d7ed8c1948f6`;
`origin/features/next` remains `8700d1d8d6288877287328ba9da0363633693113`.
Ignored dependencies, credentials, models, audio/config/logs and generated
artifacts remain private/local; retained build evidence is not a release payload.
Ignored `tools/` content is Python bytecode only; managed worktrees have no ignored
residue. No model/config mutation, app restart, merge, push or publication is part
of this acceptance update. Next action: coordinate the deferred T21-T25 stage.
