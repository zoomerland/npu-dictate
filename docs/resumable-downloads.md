# Resumable Model Downloads

## Files and Identity

For `model.bin`, the downloader uses these sibling files:

- `model.bin.download`: candidate bytes; not an installed model.
- `model.bin.download.json`: version 1 resume metadata; not model/cache payload.
- `model.bin.download.json.tmp`: atomic metadata-write staging; not payload.

Cache inventory should count `.download` bytes but exclude both sidecar names.
Metadata records `version`, `source_sha256` (the original URL fingerprint),
`expected_size`, `expected_sha256`, `etag`, `total`, `bytes` and `prefix_sha256`.
It does not store URLs, query tokens, userinfo, authorization headers or cookies.
ETag is an opaque representation validator, not an authenticity proof.

The metadata is checked against the current source/expected size/hash. The actual
partial length and SHA256 are rechecked before every resume. Missing, oversized,
malformed, stale or inconsistent metadata causes a full download, never append.
Unpaired old partials and completed old candidates are not trusted, including
direct ASR downloads without a manifest hash.

## HTTP Contract

Requests explicitly use `Accept-Encoding: identity`. Resume requires a syntactically
strong ETag and a known total. Neither weak ETags nor Last-Modified dates authorize
resume. Requests send `Range: bytes=<retained>-` and `If-Range: <strong ETag>`.

A 206 must have a single numeric `Content-Range`, the exact retained start, the
original total, the final byte as its end, and the same strong ETag. Content-Length,
when present, must match the range length. Encoded/multipart responses, unsolicited
206, malformed/contradictory headers and overlong bodies are rejected and clear
candidate resume state. No chunk is written beyond the known response length.

A 200 to a range request is new full content and replaces the candidate from byte
zero. Manifest size and Content-Length must agree. A 416 discards resume state and
allows exactly one full-request fallback per downloader call. It never proves
that a local partial is complete; artifact retries remain capped at three.

Transport interruption or premature EOF preserves a checked prefix only when its
response supplied a strong ETag and known total. Sidecar publication is atomic.
Save errors propagate; leftover staging metadata is never used as authority.
An abrupt process kill can lose the current checkpoint: inconsistent bytes and
metadata restart safely rather than guessing. Prefix hashing costs local disk I/O.

## Publication and Ownership

`download_url_to_file` keeps its existing arguments and Path return contract;
`expected_sha256` is an optional final argument used to bind resume identity, not
a replacement for caller-side final SHA verification. Successful download removes
resume metadata, returns the candidate, and never changes the installed target.

`install_artifact` retains final size/SHA verification and clears candidate state
after a SHA mismatch. Both direct ASR paths and artifact installation use
`os.replace` on sibling files instead of unlink-then-move. Old targets survive
download, validation and replacement failures.

In-process per-target reentrant ownership covers artifact retries, SHA verification
and final replacement. Direct ASR ownership covers readiness recheck, download and
replacement. Same-target jobs serialize; different targets remain independent.
The public downloader also serializes streaming, but callers doing their own
verification/publication must hold `_download_lock(target)` over that entire
lifecycle, as the built-in install paths do. A returned Path alone is not a lock.
There is no cross-process locking; multiple app processes writing the same target
are unsupported. Lock keys are canonical, case-normalized absolute paths (including
Windows short-name aliases), checked for unsafe paths before resolution; entries live for the
process lifetime. No cancellation UI or new dependency is introduced.

Callback exceptions propagate with their original type and are not artifact
retries. Safely resumable prefixes can survive a stale-generation callback, but
that operation never installs a candidate. Percent includes retained bytes;
speed/ETA use only bytes transferred in the current attempt. Existing status
prefixes are unchanged.

Partial, sidecar, staging, target and parent paths reject existing symlinks/reparse
points, non-regular leaves and filesystem inspection errors before mutation.
Cleanup only addresses the three named candidate siblings. These checks protect
ordinary filesystem mistakes; they do not claim defense against an adversarial
same-user process replacing paths between checks.

## Offline Validation

Run from the feature worktree with the existing runtime:

```powershell
& 'C:/Users/Zoomerland/Documents/Апгрейд лаптопа/.venv/Scripts/python.exe' -B tools/test_resumable_downloads.py
& 'C:/Users/Zoomerland/Documents/Апгрейд лаптопа/.venv/Scripts/python.exe' -B tools/test_model_readiness.py
```

Focused tests use temporary directories, fake HTTP responses, denied real network
and synthetic callback/concurrency faults. Coverage includes retry/later resume,
changed representations, malformed/truncated/overlong ranges, weak/missing
validators, stale/corrupt metadata and bytes, 416 bounds, hash cleanup, target
preservation, progress accounting, links/reparse/errors and same-target ownership
through verification/publication. Existing smoke size validation now rejects a
Content-Length contradicting the explicit expected size. No real server, model,
UI, microphone, user config or credentials are used or validated.

### Worker Checkpoint (2026-10-04)

- Branch: `codex/resumable-model-downloads`; unchanged HEAD/base
  `47fa5d120e57331493be5747b91b4467fb73f341` (also `features/next`).
- `tools/test_resumable_downloads.py`: 38 passing tests, no skips.
- `tools/test_model_readiness.py`: 13 passing tests.
- Isolated `check_direct_download_size_validation` from `tools/smoke_checks.py`:
  PASS (only its fake response class/function executed, no app import).
- AST syntax parsing and `git diff --check`: PASS.
- Four scoped working files are retained as uncommitted integration candidates;
  no ignored/private artifacts in this worktree, no stashes or detached worktrees
  in the metadata listing. No commit, merge, push, model/network activity or
  configuration mutation performed. Other worktree contents were not inspected.
- Independent review and the shared aggregate runner remain parent-owned.
  Live HTTP/model acceptance and cross-process ownership are not established.
- Git integration caveat: `main` at
  `fbd0a53ae1052a34bdc09528c907d7ed8c1948f6` is not an ancestor of this
  `features/next` snapshot. Parent must classify refs before any integration;
  this worker did not change them.
