# NPU Dictate 0.1.0-alpha.5 Release Checklist

Date: 2026-10-03. Status: preparing an unsigned public prerelease.

## Authority And Boundaries

The owner requested integration into main, remote updates and new builds, then
explicitly approved publishing a GitHub prerelease. No running-app restart,
installed-product upgrade/removal, visible UI, model changes/downloads or private
recording inspection are authorized by this build gate.

Identity: app/tag `0.1.0-alpha.5` / `v0.1.0-alpha.5`, numeric MSI `0.1.5`.
Assets: `NPUDictate-0.1.0-alpha.5-win-x64.zip`,
`NPUDictate-0.1.0-alpha.5.msi`, `SHA256SUMS.txt`.
All binaries remain explicitly unsigned; no signing key or credentials are bundled.

## Git Preservation Snapshot

Before integration there was one clean attached worktree, no stashes and no
unclassified implementation work. Origin is the public
`https://github.com/zoomerland/npu-dictate.git`, default branch main.

- Reviewed fix branch: `e49b8f061e447ba25d6d92b303abe57050748494`;
  product checkpoint `c4d3080e479e3065961ba185827410445d212651`.
- Original features/next: `3af69614c045cbe187f1881bab33d2ba16f76862`.
- Original main/origin/main/origin/features/next:
  `f5a424cc8452759320bca7bfcf74a963493dae91`.
- Fetch added only the existing alpha.1 tag; its peeled commit `4b0c507` is an
  integration ancestor. No remote branch divergence appeared.
- `codex/outreach-launch-kit` unique docs commit `b72dd9d` and
  `codex/research-dictation-cleanup` unique roadmap commit `04c45ab` are retained,
  not silently integrated. Enter branch commits remain patch-equivalent.
- Other historical refs remain preserved, no branch deletion/prune/rebase.
- Ignored `.hf`, models, dependencies, config/log and recordings keep their
  private classifications. Build/dist are generated outputs; preserve old builds
  before replacing them. None are eligible for Git commits.

## Sequential Gates

- [x] User authorizes merge, remote updates and prerelease publication.
- [x] Full Git revision, remote identity and branch divergence checks.
- [x] Integrate reviewed UI/UX branch into features/next (`c72e7dec`).
- [x] Start release preparation from features/next on a separate release branch.
- [x] Version metadata, release notes and CI headless gate validated.
- [x] Independent packaging/release preflight reviewed; findings closed at `e9fada76`.
- [x] Integrated source headless regressions pass.
- [x] Fresh local EXE build, isolated import smoke, payload/version checks.
- [x] Local MSI build, numeric metadata and administrative-extraction smoke.
- [x] Independent local binary evidence and final CI-source delta review.
- [ ] Release preparation merged into features/next, then main.
- [ ] Main/features/next pushed without force.
- [ ] Tag pushed; tagged GitHub Actions build succeeds.
- [ ] CI ZIP/MSI downloaded, independently checked and hashed.
- [ ] GitHub prerelease published with all three assets and limitations.
- [ ] Published asset names, sizes and hashes rechecked.
- [ ] Clean final refs/worktree, owned test processes stopped, handoff recorded.

## Acceptance Limits

Do not check live UI, full NPU model load or installed upgrade as complete based
on imports, synthetic tests or MSI administrative extraction. Those are distinct
future tests. No strict doctor against private user configuration is required
for this bounded build gate. Actual payload inspection must occur after building.

Main profile: Sol 6.1 xhigh, runtime-verified; release reviewer: Sol 6.1 high,
runtime-verified from its current turn_context. No profile change required.

## Execution Evidence

Record incremental outputs, frozen source refs, artifact hashes and exact CI run
here. If any mandatory gate fails, do not tag/publish on the basis of stale assets.

- Integrated alpha.5 source: 69 headless tests PASS, no visible UI/input/model work.
- Packaging safety: 18 synthetic tests PASS. Actual PowerShell script definitions
  run with AST-substituted native commands and owned temporary files, rejecting
  failed builders/cleanup, stale receipts, dirty source and payload/version drift.
- Preflight at `e49b8f0` required changes for native build failure and incomplete
  payload checking. New build receipts bind commit, EXE hash and full payload
  inventory; MSI refuses mismatched or dirty source. Final independent recheck
  remains required before integration/publication.
- A preliminary alpha.5 EXE built before the packaging hardening passed import,
  version and payload checks (5,861 files, 920,335,933 bytes, NotSigned). It is not
  accepted as the final frozen build; the guarded builder must run again after commit.
- Dependencies: pip check PASS; existing PyInstaller 6.17.0, WiX/UI extension 5.0.2.
  No replacement paid installer tool or license acceptance was introduced.
- First local .NET SDK invocation initialized its own development HTTPS certificate.
  That is not application code signing; no installer signing certificate is claimed.
- Previous generated alpha.4 EXE folder retained in ignored
  `dist/preserved-alpha4-20261003`; prior installer assets retained as well.
- Source follow-up at `549a2dd` closed native-failure/metadata/claims findings but
  required unconditional prior-output protection and broader config/weight names.
  Existing dist is now validated before ALL builder paths, with explicit backend
  dist/work paths. Contamination rejects both Clean/default modes before deletion;
  sentinel bytes survive. Config backups and standard model-weight filename
  families are denied at every depth while public examples/library binaries remain.
  Independent final source review closed these findings at `e9fada76`.
- Final local build source: `e9fada76da8644c377438352b4ee837541d797ae`.
  EXE/ZIP/MSI-extracted payloads match 5,861 files / 920,335,933 bytes.
  All three isolated import smokes PASS, without visible UI or model initialization.
  EXE ProductVersion/FileVersion: `0.1.0-alpha.5`, EXE/MSI: NotSigned.
  MSI ProductVersion: `0.1.5`; stable UpgradeCode:
  `{EF3E8984-DA8E-4615-BD86-ACE089338FB3}`. This is extraction, not installation.
- Local inventory SHA256:
  `8E275D2271DE329A81161820272F3BAFF0120F801E0DAEFCFE91817D60493A73`.
  Local EXE SHA256:
  `EB90A42C0BDD12ED56205A2C0EFA966F3C454E188DC56DAFC0AE9978CADC37D3`.
  Local MSI: 254,808,734 bytes; SHA256:
  `976A2A7F081389E7568EC416CE997C26DA32A800130573E7C073B26951E6F282`.
  Local ZIP: 339,560,660 bytes; SHA256:
  `7F50BCF8113D468199909FD615E9EC711EDE67E590F261E71500C44E38522430`.
- CI will produce fresh artifacts from the final tagged source. Its separate
  build-evidence artifact contains the source receipt and full payload inventory;
  downloaded packages must be checked against THAT inventory, not local hashes.
  These local hashes are not the public-release checksums.
- Independent LOCAL-BINARY and CI-DELTA reviews: PASS_WITH_LIMITATIONS.
  All four local payload representations matched the full inventory and receipt.
  Frozen CI-source delta `4cd6a71431bc472cbee8e38d4684914c6be71a74` adds only
  provenance upload, explicit inventory selection and documentation; app payload
  source remains the reviewed local source. Final source headless tests: 69 PASS;
  packaging tests: 18 PASS; four PowerShell parsers and diff checks PASS.
- Build warnings include optional dependencies and UIAutomationClient VC140 DLL
  collection. ImportOnly passes but does not exercise lazy automation/context
  paths. Live input/model acceptance remains separate; do not claim warning-free.
- Pre-integration Git delta: one clean worktree at `4cd6a714`, no stashes or
  detached HEAD, historical refs unchanged, remotes still at `f5a424cc` after
  fetch. Ignored build/dist and owned review reports are generated evidence;
  dependency/model/private-data classifications from the full snapshot remain.
  No new ignored implementation or unresolved tracked work appeared.
