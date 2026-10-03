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

- [ ] UX-01: stop paste on failed target restoration/identity drift; retain manual text.
- [ ] UX-02: retain raw ASR on punctuation failure, avoid automatic sending, retry safely.
- [ ] UX-03: defer recording-incompatible settings; preserve live recording indicators.
- [ ] Independent review and critical-path regression gate.
- [ ] UX-04: consistent cached-model readiness and integrity checks.
- [ ] UX-05: validate hotkey tokens and overlapping shortcuts.
- [ ] UX-06: recoverable settings-save failures and exit behavior.
- [ ] UX-07: preserve the system-default/missing microphone choice.
- [ ] UX-08: full live model progress, refresh installed labels, honest warmup states.
- [ ] UX-09: responsive settings widths and per-monitor workarea placement.
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
