# Isolated Frozen Offline-Policy Check

## Scope

This is a local EXE import check, not a release, installer test, full model load,
microphone test or OS-wide network audit. It must not replace `dist`, the installed
application, user configuration, models, caches or consent files.

The import-only smoke path now verifies the optional telemetry sentinel, absence
of loaded telemetry child modules and identity of OpenVINO's genuine fallback.
It writes a small `package offline policy` JSON receipt before the existing
success marker. Policy failure records only its exception type and returns 1.
Both paths return before the instance lock, model maintenance and UI creation.
Normal launches do not import the diagnostic helper.

## Validation Protocol

1. Run `tools/test_frozen_smoke.py` and the shared headless suite.
2. Build `packaging/npu_dictate.spec` with distinct `--distpath` and `--workpath`
   under a new local `build` subdirectory. Never use the normal clean/release
   helper merely for this test. Existing Python/PyInstaller dependencies suffice.
3. Build-time hook subprocesses may use a transient `TF_BUILD` opt-out; this is
   explicitly not frozen-runtime evidence. The runtime probe removes that flag,
   vendor `OV_` / `OPENVINO_` flags, CI flags and Python path overrides.
4. Inspect the actual executable archive: the policy/runtime hook/diagnostic
   modules must be present and `openvino_telemetry` absent.
5. Start only the import-only EXE mode, hidden, with a bounded timeout and empty
   temporary HOME/USERPROFILE/APPDATA/LOCALAPPDATA/TEMP/TMP/XDG/HF/Torch/data paths.
   Do not copy config, models, caches or consent into the fixture. This bypasses
   normal application startup and does not restart the user's running app.
6. Require exit 0, the smoke success marker and a JSON receipt with `frozen=true`,
   `optional_telemetry_blocked=true` and
   `fallback=openvino.tools.ovc.telemetry_stub`. Check no consent, model directory
   or user config was created in the temporary profile. Retain EXE SHA256.

`tools/smoke_packaged_exe.ps1 -ImportOnly` remains useful for normal package import
smoke, but alone does not enforce the fresh-home protocol or parse receipt fields.
The stronger local probe and receipts are retained under
`build/autonomous-roadmap-20261004` and `build/autonomous-frozen-20261004`.

## Source Review

Independent reviewer `01a104a8-e91a-7d52-8114-7940e74cdb90`, Sol 6.1/high,
runtime verified at 2026-10-04T02:05:44.781Z: static PASS, no actionable findings.
The reviewer ran no tests. Parent focused tests: 4 PASS. Combined source suite:
184 PASS, exit 0, 91.639 seconds. Packaging safety regressions: 18 PASS, exit 0,
40.327 seconds. The parent owns frozen artifact evidence, still pending below.

## Frozen Result (2026-10-04)

- Existing PyInstaller build completed successfully, exit 0, approximately
  890 seconds. No dependency installation or normal `dist` cleanup occurred.
- Actual EXE archive: 8,030 entries checked, policy/diagnostic/runtime hook and
  storage module present, `openvino_telemetry` absent.
- Hidden import-only process: exit 0, 4.797 seconds; receipt confirmed frozen
  execution, blocked optional telemetry and the genuine vendor fallback.
- Empty test profile remained without consent, user config or models.
- EXE SHA256:
  `d7f530ed336e0619027729d80fedc8810bfc3d707fcbffff6f8488bf51c611c8`.
- Local executable: `build/autonomous-frozen-20261004/dist/NPUDictate/NPUDictate.exe`.
  This is an unsigned test artifact, not a release or replacement installation.
- Local receipts: `build.log`, `smoke-receipt.json`, `smoke.stdout`, `smoke.stderr`
  and fresh-profile log under `build/autonomous-frozen-20261004`.

The tested source was `features/next` at `e0c1218` plus this diagnostic change.
App source SHA256 at build time:
`3956e73cb924bfcab34496f99eff2230180e01358171b662ff4388df476ef015`.
The later deferred-cache-maintenance change is not inside this EXE. Its source
integration needs the shared regressions; the next release must rebuild and
repeat package acceptance. The recorded 4.797 seconds is import-only time,
not model load, compilation or dictation readiness. No installer, native model
readiness or live interaction is implied, and no release provenance is claimed
for this deliberately isolated diagnostic build.
