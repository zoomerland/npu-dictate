# UI/UX Audit Remediation

Date: 2026-10-03. Branch: `codex/ux-audit-fixes`.
Base: `features/next` at `3af69614c045cbe187f1881bab33d2ba16f76862`.

## Boundaries

- Fix the source-confirmed defects from the local UI/UX audit, in separate commits.
- No visible UI, Computer Use, microphone capture, real clipboard/input delivery,
  user-config edits, model downloads, cache deletion, installer changes or releases.
- No merges, pushes, tags or movement of `features/next`/`main` in this task.
- Preserve the long-punctuation fix and existing ASR/model/bucket behavior.
- Use deterministic headless regressions; require independent review of delivery
  and recording-lifecycle changes. Real visual/hardware acceptance remains separate.

## Work Queue

- [x] UX-01: stop paste on failed target restoration/identity drift; retain manual text.
- [x] UX-02: retain raw ASR on punctuation failure, avoid automatic sending, retry safely.
- [x] UX-03: reject settings while dictation is active; preserve live recording indicators.
- [ ] Independent review and critical-path regression gate.
- [x] UX-04: consistent cached-model readiness and integrity checks.
- [x] UX-05: validate hotkey tokens and overlapping shortcuts.
- [x] UX-06: recoverable settings-save failures and exit behavior.
- [x] UX-07: preserve the system-default/missing microphone choice.
- [x] UX-08: full live model progress, refresh installed labels, honest warmup states.
- [x] UX-09: responsive settings widths and per-monitor workarea placement.
- [ ] UX-10: redact dictated text/logs from default copied diagnostics.
- [ ] UX-11: localize dynamic status details and correct opacity terminology.
- [ ] UX-12: accumulate wheel delta, expose review-stop command, safe hide fallback.
- [ ] Final headless suite, review findings, roadmap and handoff.

## Initial Git Revision

One worktree, attached HEAD, no tracked/untracked changes, no stashes.
`main`, `origin/main`, `origin/features/next` remain at
`f5a424cc8452759320bca7bfcf74a963493dae91`.
The long-punctuation commit `d6754f5` is already included in the integration base.

Retained historical branches are not deleted or integrated here:
`codex/press-enter-after-paste` is patch-equivalent to the integration line;
`codex/outreach-launch-kit` has one unique documentation commit `b72dd9d`;
`codex/research-dictation-cleanup` has one unique roadmap commit `04c45ab`.
Other local branches are integration ancestors. No unclassified implementation
commits block this bounded fix branch.

Private boundaries (metadata only): `.hf` is retained private auth/cache;
`.venv`, `.wix`, `models` are local dependencies; `recordings`, local config/log
are retained private evidence/runtime; `build`, `dist`, `hf_export`, pycache are
generated artifacts. Audit probes under `recordings/ux_audit_20261003` are retained
private evidence, not product files. None of this content enters commits.

## Validation

Record commands and results incrementally below. Synthetic output is not evidence
of actual recipient acceptance, model quality, mixed-DPI rendering or MSI behavior.

- UX-01: `tools/test_dictation_safety.py`, 6 tests PASS. Failed focus, focus exception,
  unavailable/changed identity and changed fallback target send no input; stable
  window fallback still works. Copy failure is no longer described as copied.
- UX-02: safety suite extended to 11 tests. Raw ASR survives load/restore/empty-output
  failures and clipboard errors. Degraded text is never auto-pasted or sent. Preload
  failure is visible; explicit retry and punctuation off/on recover the cached fault.
- UX-03: safety suite extended to 16 tests. Both hold/toggle recordings retain
  start-owned ASR/config/rate; settings are rejected during recording/transcription,
  old-generation callbacks are ignored, and background statuses cannot hide recording.
- Critical baseline: 25 smoke groups PASS after fixing a loaded-without-ASR fixture.
  The first run reached the real loader and downloaded ASR files into the private
  test sandbox, not the application's model directory. The isolated runner now
  denies network and real model loaders; no user models/config or UI were touched.
  Sandbox artifacts are retained private test residue, excluded from Git.
- UX-04: `tools/test_model_readiness.py`, 9 tests PASS. Empty/invalid JSON files and
  manifest-size failures cannot bypass readiness. Background preparation verifies
  cached converted weights with SHA256; metadata-keyed hashing avoids repeated reads.
  UI readiness uses lightweight size checks. Legacy/direct upstream files without
  a local SHA manifest cannot have arbitrary same-size corruption proven by this check.
- UX-05: settings suite, 4 tests PASS. Invalid key names and subset conflicts are
  rejected with an inline error. Legacy conflicting configs dispatch only the overlay
  action for a matching chord. Physical digit handling and supported named keys remain.
- UX-06: settings suite extended to 8 tests. Failed persistence leaves the applied
  config unchanged; failed autostart changes restore the prior saved config. Inline
  errors keep the settings window open, and failed exit persistence cannot trap exit.
- UX-07: settings suite extended to 10 tests. System default remains `None`; a
  missing device is explicitly retained, not replaced by the first available index.
  The sample-rate label explains automatic selection. Stable USB identity remains
  a separate future improvement: PortAudio indices can change between restarts.
- UX-08 / review follow-up: safety suite extended to 18 tests; settings suite to
  12. Model settings expose full live progress and an explicit idle-only retry.
  Labels refresh on loading/readiness events without marking edited settings dirty.
  Warmup uses indeterminate progress; the existing NPU startup guard is unchanged
  and explained. Saving cannot conceal a current readiness failure.
  Non-string and punctuation-only results now fall back at the final boundary;
  synthetic raw fallback never pastes or sends. The safety harness denies real
  loaders, network and audio opening globally. Independent re-review is pending.
- UX-09: settings suite extended to 15 tests. Geometry stays within individual
  workareas at 640/800/1024 widths, 100/150/200% input scales, negative coordinates
  and staggered-monitor bounds. Controls use a single column with width-bound
  wrapping and two-row footer; section selection no longer relies on wide tabs.
  Actual Tk rendering, checkbutton wrapping and mixed-DPI monitor transitions still
  require later visual acceptance; no product window was opened for these checks.
