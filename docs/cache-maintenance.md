# Deferred Compiled-Cache Maintenance

This is a source-only, explicitly scheduled command. It removes only regular
files and nested directories inside the app-managed
`user_data_root()/models/openvino/cache` subtree, leaving the cache root in place.
That subtree is the ownership boundary, not a filename-extension classifier.
Model weights, model XML/config/tokenizer data, manifests and HF caches outside
that subtree are untouched. No regeneration, requantization, config rewrite or
automatic restart is added. Normal compilation/warmup rebuilds caches as needed.

## Request And Startup

Models settings contain a localized explanation, confirmation-protected schedule
button, pending-request cancellation, and a localized result. Scheduling writes
only `user_data_root()/compiled-cache-maintenance.json`. Applying unrelated
settings, opening/relabeling settings and development imports never schedule or
execute cleanup. These actions do not dirty the settings form.
The displayed outcome and actual pending-marker status are kept separately; if
a cancellation write fails, the failure stays visible and the pending request
can still be cancelled after the write problem is resolved.

The small separate marker avoids overwriting config/settings from another UI
operation. Its strict versioned schema has one fixed operation, state, reason
code and removal counts. No paths or traversal limits are stored in the job.
Empty, oversized (>4096 bytes), malformed, duplicate-field, unknown-field,
wrong-version/operation, redirected and nonregular marker files are refused.
Schema errors preserve the marker and never authorize cache access/removal.

The exact root marker and root `.compiled-cache-maintenance-*.tmp` files are
Git-ignored runtime state, not release inputs. `release_payload.checked_path`
rejects marker names (including appended backup suffixes) and matching temporary
names/backup suffixes case-insensitively at every payload depth, for directories
and ZIP entries. `cache_maintenance.py`/bytecode and legitimate runtime binaries
remain allowed. Synthetic folder/ZIP and hypothetical Git-ignore checks cover
this boundary without opening any real marker or building/installing an app.

Normal startup acquires `SingleInstanceLock`, then calls maintenance, then creates
`VoiceDictationApp` and schedules model preparation. Secondary instances, failed
lock initialization and the smoke-import branch bypass maintenance entirely.
The worker did not change the smoke branch; the parent's separate packaged-smoke
workstream owns its diagnostics.

An absent fresh data root means no possible request, not a maintenance error.
Existing ancestors are still checked; a missing descendant below a link or
non-directory is not treated as a safe fresh profile. Reading/cancelling does
not create a missing data root. Explicit scheduling into a missing data root
fails visibly rather than creating a new tree.

## One-Shot States

- `pending`: explicit confirmed request. Repeated scheduling is idempotent.
- `cancelled`: cancellation replaces only a valid pending marker; no cache is
  inspected or deleted. Cancellation with no pending request changes nothing.
- `running`: written atomically and flushed before cache preflight or deletion.
  This consumes the pending authorization. Process interruption or a failed
  result write cannot cause an automatic purge retry.
- `cleared` / `missing`: persisted success or cache-absent no-op, with counts.
- `failed`: persisted first failure, with the known counts. No automatic retry;
  a fresh confirmed schedule is needed to try again.

If consuming the request itself fails, no cache preflight/deletion occurs. The
original pending marker may remain because it could not be replaced. Subsequent
launches may attempt to consume that still-authorized request, but cannot purge
until that state write succeeds. Every such error requires visible startup
acknowledgement; this is not represented as a completed or consumed request.
Corrupt/unreadable state requires owner repair; it is not silently overwritten.

Failed or running results, including persisted results from previous launches,
produce a RU/EN diagnostic **before app/model construction**. The default is No:
stop before loading models. Only an explicit Yes allows the normal launch to use
remaining cache. A failed/unavailable dialog also stops. The result remains in
Models settings; consenting does not schedule a retry or clear the failure.

## Deletion Gates And Limits

The caller supplies the authoritative app data root. The module requires an
absolute, non-volume-root path with no `..`; the cache target is always derived
internally from fixed components. Standard-library `lstat` checks existing root
and parent directories, refusing symlinks, junctions/reparse points and other
non-directory substitutions. No `resolve` expands cache-link targets.

Before any unlink/rmdir, a complete bounded metadata inventory must succeed.
Links/reparse points, nonregular entries, observed read-only modes/attributes,
access failures, observed directory changes or bounds stop the whole preflight
with zero removals. Default bounds: 20,000 entries, depth 32, 10 seconds shared
between cache preflight and removal. No file contents are read or hashed.

Deletion uses only the explicit inventory: file `unlink`, then deepest-first
directory `rmdir`, each after root confinement and parent identity/link checks.
Files must still match their metadata fingerprint. There is no shell deletion,
`shutil.rmtree`, arbitrary path job, native WinAPI pinning or forced permission
change. Before `cleared`, a bounded final root/ancestor identity-and-no-link check
and empty-root enumeration must succeed. A new root-level entry or replaced
cache root produces `changed` with known partial counts; the new entry is not
deleted. Root/parents and all model/HF sibling trees are retained.

This is ordinary-race detection, not a hostile same-user TOCTOU sandbox or an
atomic filesystem transaction. Permission/ACL/lock changes can defeat preflight
predictions. A changed/missing file, new directory entry, unlink/rmdir failure or
timeout during removal stops at the first error and reports an honest partial
result. Removed files cannot be rolled back. Counts do not include entries whose
removal failed. A crash may leave only `running`, so exact partial counts may be
unknown; the interrupted diagnostic never claims exact success/zero.

Bounds are cooperative between OS calls; an individual metadata/state I/O call
cannot be forcibly interrupted. Marker writes use a unique exclusive temporary
file, flush/fsync and atomic replacement, not a power-loss transaction guarantee.
Own temporary-state cleanup failure can leave a small residue and is returned as
an error. No temporary files or cache cleanup are attempted merely by importing
the module or running the app's smoke-import branch.

## Validation

All fixtures are temporary. Dialogs, widgets, instance lock, model construction,
hardware, input and network are fake/forbidden. Native Windows junction fixtures
are created and unlinked inside the temporary tree without traversing their
targets. Production user cache/config/audio/Startup folders were not accessed.

```powershell
Set-Location -LiteralPath 'C:/Users/Zoomerland/.codex/worktrees/model-storage/Апгрейд лаптопа'
$env:PYTHONPATH = (Join-Path (Get-Location) 'tools')
& 'C:/Users/Zoomerland/Documents/Апгрейд лаптопа/.venv/Scripts/python.exe' -B tools/test_cache_maintenance.py
& 'C:/Users/Zoomerland/Documents/Апгрейд лаптопа/.venv/Scripts/python.exe' -B tools/headless_ux_checks.py
```

The final focused run includes cache and payload tests together under the same
hermetic harness (no actual EXE/MSI build):

```powershell
& 'C:/Users/Zoomerland/Documents/Апгрейд лаптопа/.venv/Scripts/python.exe' -B -c "import os,sys; from headless_ux_checks import main; from test_cache_maintenance import CacheMaintenanceTests,CacheStartupTests,CacheUiTests; from test_release_payload import PayloadTests; code=main(test_cases=(CacheMaintenanceTests,CacheStartupTests,CacheUiTests,PayloadTests)); sys.stdout.flush(); sys.stderr.flush(); os._exit(code)"
```

First-red evidence retained: initial focused run on 2026-10-04 had 23 tests and
28 failures/subtest failures in 12.177 s, mostly `changed` during marker reads,
before cache preflight/deletion. A metadata-only temporary Windows-file check
confirmed equal identity/size/mtime but unequal `lstat`/`fstat` ctime. The fix
compares stable cross-API fields and retains full `lstat`-to-`lstat` before/after
validation; an explicit regression covers the mismatch. No safety policy or
deletion boundary was relaxed. The next focused run passed 24 tests in 18.386 s.

Payload first-red evidence: initial selected `PayloadTests` run had 10 tests and
one failure in 0.467 s: Git's newline-framed `check-ignore --stdin` fixture returned
1 on Windows despite correct patterns. Argument-based and binary NUL-framed
checks matched both root names without creating any files. The fixture now uses
Git's `-z` protocol; the payload deny policy was not weakened.

Final-source gates on 2026-10-04:

- Combined focused cache/startup/fake-UI/payload: 38 tests PASS in 11.137 s,
  exit 0. Includes both new-root-entry and root-replacement regressions.
- Existing guarded headless aggregate: 109 tests PASS in 36.931 s, exit 0.
- `git diff --check`: PASS (only Git's normal working-copy CRLF warnings).

Frozen candidate branch: `codex/deferred-cache-maintenance`, unchanged base/HEAD
`e9dade0d2ca7f0dd51e8bfc7fd6b4872bf231233`. Seven scoped files, uncommitted;
no merge, pull, push, release build or production cache operation was performed.

Live GUI/DPI rendering, real model/cache contents, packaged execution and actual
application restarts were not tested. Parent owns shared-runner integration,
independent review, roadmap records and later integration. The worker handoff
is frozen/uncommitted, not deployment or approval to purge a user cache.
