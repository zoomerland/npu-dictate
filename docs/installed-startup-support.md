# Installed Startup Support

## Scope And State

- Worker: `installed-startup-support`, bounded implementation/contract tests.
- Branch: `codex/installed-startup-support` in the primary workspace.
- Base/HEAD: `47fa5d120e57331493be5747b91b4467fb73f341` (`features/next` base).
- Runtime: parent supplied independent fresh `turn_context` evidence for
  `gpt-6.1-sol / medium`, timestamp `2026-10-04T01:36:20.38Z`.
  Source: `RUNTIME_VERIFIED`; recommended profile unchanged.
- Candidate remains uncommitted for parent review. No merge, push, release,
  restart, runner edit, roadmap edit, or progress-document edit.
- Changed files: startup helper block in `tools/voice_dictation_app.py`,
  `tools/test_startup_support.py`, and this report only.

## Behavior

The original helpers already supported installed/frozen execution:
`startup_target_python()` returns `sys.executable` when frozen, shortcut arguments
are empty, and working directory is `app_root()`, not `user_data_root()`.
Source execution prefers `.venv/Scripts/pythonw.exe`, falls back to
`sys.executable`, and uses a quoted script argument. These contracts remain intact.

The concrete persistence defect was direct COM Save into the final startup link.
A failed Save could leave a partial link that `is_startup_enabled()` counted as
enabled, or damage an existing link.

New enable lifecycle:

1. If the named startup link exists, return success without opening or rewriting
   it. Repeated enable is idempotent and cannot rewrite an unrelated/stale link.
2. Reserve a unique `.lnk` path with `mkstemp` in Startup's parent directory,
   outside Startup and on the same filesystem. Close its descriptor and remove
   only this owned empty placeholder before WSH CreateShortcut. WSH may try to
   load an existing `.lnk`; an empty placeholder is not a valid shortcut.
3. Populate and Save through WScript.Shell. Reject missing/empty Save output.
4. Publish with `Path.rename`, not overwrite-capable `Path.replace`. On Windows,
   rename refuses an existing destination, preserving a concurrently created link.
5. On failure, report `False` and log the exception type; clean only the owned
   temporary path. Cleanup errors are separately logged. A cleanup residue stays
   outside Startup, never masquerading as the enabled named startup link.

Disable retains `unlink(missing_ok=True)` and reports deletion errors. Repeated
disable succeeds. Settings persistence/rollback order is unchanged: persist the
candidate config first, mutate startup second, restore previous saved config on
failure, and publish active config only after success.

## Validation

Commands use existing dependencies, modern PowerShell, and bytecode suppression:

```powershell
.venv/Scripts/python.exe -B tools/test_startup_support.py
.venv/Scripts/python.exe -B tools/headless_ux_checks.py
git diff --check
```

- Focused gate: **47 tests PASS**, including 21 startup tests and 26 existing
  settings tests. Includes the original
  `test_startup_failure_restores_previous_saved_config` regression.
- Default aggregate gate: **109 tests PASS** on the final implementation,
  including the owned-placeholder correction.
- `git diff --check`: PASS; Git emits only its existing LF/CRLF conversion notice.

All shortcut COM objects are fake modules injected into `sys.modules`. Startup
folder resolution is redirected to temporary directories before helper calls.
Path/rename/unlink behavior uses temporary files only; no real Startup access,
COM instantiation, registry, GUI, microphone, model loading, dependency install,
or network work is performed. The existing headless runner denies real UI,
input, model and network operations. Its fresh-process import regressions use
guarded real library imports, not model inference.

Coverage includes frozen EXE/empty args/install directory, redirected data root,
source pythonw/fallback, spaces/Unicode quoting, idempotence, preserved existing
links, concurrent destination creation, COM/Create/partial Save/empty Save
failures, publication errors, unlink/cleanup/placeholder errors, mkdir/mkstemp
errors, unsupported OS, pure APPDATA/home resolution, settings rollback and
rollback-error reporting. Fake WSH explicitly rejects existing invalid `.lnk`
placeholders. Overwrite-capable replace is forbidden by a successful-enable test.

## Limitations And Next Gate

- Native COM compatibility and actual OS-login launch have **not** been observed.
  Fake contracts are not installed-build/live acceptance.
- `is_startup_enabled()` still means the expected filename exists. It does not
  prove valid shortcut structure, current target, ownership, or launchability.
  Existing stale/source-era links are not repaired by repeat enable or unrelated
  settings saves. Parent must decide a separate ownership/migration design before
  adding repair behavior.
- Explicit disable retains the historical named-link deletion contract. A user
  may have placed an unrelated link under the same application filename; there
  is no owner marker. Ownership-safe disable is a separate policy/design question.
- Startup's parent must be writable for staging. Failure is reported without
  publishing a partial link. Cleanup failure can leave one owned residue outside
  Startup; no broad cleanup scan or deletion is performed.
- When config rollback itself fails, active config remains unchanged and the UI
  reports that failure; the persisted candidate may remain. This pre-existing
  broader settings-recovery limitation was tested, not refactored.
- No private-state inspection or mutation, no retained test audio/models/logs;
  all test-owned temporary directories are cleaned by fixtures.

Next action: parent independent review of the frozen candidate, then decide
commit/integration and runner registration of `StartupSupportTests`. The worker
does not message other tasks or integrate the branch.
