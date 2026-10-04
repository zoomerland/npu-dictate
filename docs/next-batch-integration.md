# Next Batch Integration

## Scope

On 2026-10-04 (Europe/Moscow), the owner authorized merging the completed NPU
preparation and optional telemetry branches into `features/next`, followed by
automated checks without GUI or microphone participation. This is not approval
to update `main`, push, rebuild EXE/MSI, publish a release or restart the app.

## Git Revision And Preservation

The full pre-merge revision found one clean root worktree, no untracked files,
stash, detached HEAD or unresolved index entries. The private metadata inventory
and full local checkpoint are retained under the ignored
`build/feature-integration-20261004/pre-merge-checkpoint.md`.

- Integration base / origin/features/next:
  `8700d1d8d6288877287328ba9da0363633693113`.
- Main / origin/main: `fbd0a53ae1052a34bdc09528c907d7ed8c1948f6`.
- Preparation tip: `1fe6bae7f39fa1b8b117c0ee46ba18cc300ab691`, containing source
  commit `8c6d9ff` and the isolated native acceptance report.
- Telemetry tip: `41a6246e6ae05f0b01c65a75dddf28ccf408c1e6`.

Both feature branches started from the integration base, and `git cherry`
confirmed their unique patches before merging. The pre-merge main and integration
trees were content-identical. Unrelated outreach/research branches and historical
patch-equivalent refs retain their preceding classifications and exact hashes.
No branch was deleted, rebased or rewritten, and no unrelated work was adopted.

Ignored `.hf` credentials, audio, config/log, models/cache, dependency runtimes,
generated artifacts and prior native test receipts remain local/private. Only
metadata was inventoried for these boundaries. The previous native helper and
first-red receipts are retained test evidence, not new product source.

## Merge Resolution

Preparation merged in the no-fast-forward commit
`46db6562c6a348aed4b6fe3958d6e3f8839a0f77`. Telemetry required manual resolution
in two files:

- `tools/headless_ux_checks.py`: retain `main(test_cases=None)`, the real Core
  constructor guard and all prior hermetic boundaries; include both the 24
  preparation regressions and all four telemetry classes (16 tests).
- `ROADMAP.md`: retain completed preparation work and historical telemetry
  discovery; use the newer source telemetry fix with the rebuilt-EXE gate open.

The three runtime modules auto-merged preparation behavior with the early
telemetry bootstrap. Packaging retains the runtime hook/helper and exclusion.
Historical feature reports are preserved rather than rewritten as if integration
or a new native run had already happened when those reports were produced.

## Combined Validation

Parent-run checks on the frozen combined source:

- `.venv/Scripts/python.exe -B tools/headless_ux_checks.py`: 109 tests PASS in
  34.891 seconds, process exit 0.
- `.venv/Scripts/python.exe -B tools/smoke_checks.py --suite preparation`:
  24 tests PASS in 0.068 seconds inside the runner, process exit 0. This is a
  subset of the 109, not 24 additional distinct tests; dependency import time
  is excluded from the test runner's elapsed value.
- `git diff --cached --check`: PASS; no unresolved index entries or unowned
  source changes remained before the final merge commit.

The aggregate preserves 69 existing tests plus 24 preparation and 16 telemetry
tests. Fresh-process real-import probes retain their no-opt-out-file, network,
GUI/input and model-data guards. Source tests do not construct real Core or
perform native compilation/inference. The preparation subset uses the same
hermetic runner rather than the full smoke suite's hardware paths.

Test receipts remain ignored under `build/feature-integration-20261004/`:

- `headless-aggregate.log` SHA-256:
  `e367834fbc1a8c552e521038559c0973439a1ca4d69f0e20c7d2d1c507fa0d2e`.
- `preparation-subset.log` SHA-256:
  `c87db7cd69ec851eb2e633c3e45dd5db9f381ab2e81aa48371e049cf9d0301f7`.

## Frozen Source And Review

Git blob identities avoid misleading CRLF-dependent worktree hash comparisons:

| Path | Blob |
| --- | --- |
| tools/voice_dictation_app.py | f4fb3ebfd687c382e9411bea0abd4cda2368255d |
| tools/gigaam_openvino_asr.py | a34e3f47a5845310e736651cee8fe6e7a7f79a58 |
| tools/rupunct_restore.py | 4a6af8c3d3cd97a7f31b3a34630acbc6271a9213 |
| tools/offline_runtime.py | 8995de9f1a7caf41ce6a6049916cf6597c5fbeb6 |
| tools/headless_ux_checks.py | 43bc577ce56f74fceb50dfa746d2ffa2cdb7ccf9 |
| tools/test_npu_preparation.py | 62783d8f65b3289b77e13e7179aedc10eeb0f4ed |
| tools/test_offline_runtime.py | 0ce57f12408b27cd33df38585e800c030284e51c |
| packaging/npu_dictate.spec | 84b40a7e0a6136ccc6348ac9e518d2a08c0c55c0 |
| packaging/hooks/rthook_offline_runtime.py | 40f6af51f3354f2eb433c0ec8354ca2826990edd |

Parent profile: `gpt-6.1-sol / xhigh`, independently verified from fresh runtime
context. Reviewer `01a10472-c078-7a20-869e-22261efaf1b5` uses
`gpt-6.1-sol / high`, independently verified by the parent from its initial
turn context at `2026-10-04T01:06:35.775Z`. Its initial profile-only stop made no
source review claim; independent runtime evidence resolved that stop without
changing the profile. Final static review of the frozen combined candidate
passed with no actionable findings. The reviewer confirmed that preparation
implementation matches its tip below the four-line bootstrap, preparation tests
and smoke dispatch are unchanged, telemetry helper/probes/hook/spec match their
tip, and all nine source/test/spec blob identities match before and after review.
The union and hermetic guards are retained. The parent owns execution; the
reviewer did not run tests or inspect private receipts. Only the disclosed parent
documentation additions changed during the review.

## Remaining Gates

Live UI/microphone checks remain owner-deferred, not passed. The historical native
cold/warm/deferred results belong to the preparation branch's earlier gate; native
inference was not rerun against this combined source. Source/spec acceptance does
not prove new frozen-binary behavior. Packaging/runtime checks and any promotion
to `main` or remote publication require a separate explicit request.

This report is included in the telemetry merge commit on `features/next`, after
the frozen-source check and independent static acceptance. Both source feature
tips remain preserved. The final Git readback is retained in the local checkpoint.
No remote publication or stable-branch movement belongs to this integration.

Next action: await an explicit request for the next bounded gate; live input
acceptance remains deferred and release/packaging work is not authorized here.
