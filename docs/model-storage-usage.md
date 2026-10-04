# App-local model storage

Models settings show **logical file sizes**, not physical allocated disk space
or whole-PC model usage. The declared root is `user_data_root()/models`.
No file content, model weights, hashes, config, credentials, or private HF cache
are read by the scanner. It performs only directory enumeration and metadata
queries. This item adds no delete, rebuild, or cache-management action.

## Categories

- Model files: regular files in the declared tree, excluding the categories and
  metadata below. This includes model XML, JSON/config and tokenizer files.
- Compiled cache: regular files below `models/openvino/cache`, including nested
  directories.
- Incomplete downloads: any regular file ending in `.download`, even inside the
  compiled-cache subtree. Its actual current size is counted separately.
- `.download.json` and `.download.meta.json` sidecars and their `.tmp` variants
  (`.download.json.tmp`, `.download.meta.json.tmp`) are excluded, as are
  administrative `.manifests` directories. No sidecar content is parsed.
- `.hf` directories are excluded without enumeration. Global/private HF caches
  and other applications' model trees are outside the declared root entirely.

Sizes are displayed as exact byte counts with binary-unit approximations for
larger values. Hard-linked files are counted per directory entry; sparse files,
compression and filesystem allocation are not measured.

## Traversal And Snapshot Limits

The scanner uses standard-library `lstat` and `scandir`. It checks the root and
its ancestors for symlinks or Windows reparse attributes before enumeration;
static symlinks, junctions and other reparse points within the tree are skipped.
Child paths are checked against the lexical root; no `resolve` is used to expand
their targets. Directories are checked again before enumeration and afterwards.
Files are checked twice for identity, size and timestamp changes.

This is a **non-transactional metadata snapshot**, not an OS sandbox or an atomic
filesystem inventory. Ordinary disappearance, access failures, observed growth
or directory changes produce a partial snapshot; changes after a file's final
metadata query may not be observed. Deliberate concurrent path substitution by
a hostile same-user process is not covered. No native handle pinning is used.

An inaccessible, missing or redirected root is unavailable, never exact zero.
Skipped links, unsupported entries, errors, observed races or limits qualify the
display as partial, including when the known subtotal is zero. Only a successful
empty tree produces unqualified zero. Partial counts are known subtotals, not
estimates of missing entries; the issue count is not a unique-file count.

Default limits: 100,000 entries, depth 64 below the root, and 10 seconds checked
between metadata operations. Cancellation is also checked between operations.
An individual OS metadata/enumeration call cannot be forcibly interrupted, so
these are cooperative bounds, not a hard wall-clock deadline.

## UI Lifecycle

Opening settings starts a background scan. The worker only enqueues an immutable
result in the app's existing queue; Tk values and widgets change on the main
thread. One worker runs at a time. Requests from model preparation/download/status
events and the refresh button coalesce into one pending request; starts are
throttled to at most once per five seconds within a settings lifetime.

Closing settings or exiting cancels the current generation. Reopening creates
a fresh lifetime and waits for any older worker to finish before starting one;
old results cannot update the new window. No scan starts while settings are
closed. A refresh retains the last snapshot with a refreshing indicator. Storage
updates are not config changes and never mark settings dirty.

RU/EN labels and byte values follow the settings language selector immediately,
without rescanning. Apply/Save, scrolling, responsive label wrapping and the
existing stacked single-column layout are retained.

## Headless Validation

Use the primary absolute interpreter with this worktree's `tools` import path:

```powershell
Set-Location -LiteralPath 'C:/Users/Zoomerland/.codex/worktrees/model-storage/Апгрейд лаптопа'
$env:PYTHONPATH = (Join-Path (Get-Location) 'tools')
& 'C:/Users/Zoomerland/Documents/Апгрейд лаптопа/.venv/Scripts/python.exe' -B tools/test_model_storage.py
& 'C:/Users/Zoomerland/Documents/Апгрейд лаптопа/.venv/Scripts/python.exe' -B tools/headless_ux_checks.py
```

The script uses the existing hermetic headless runner with only the three new
test classes. Real GUI/input/model loading/network/hardware are forbidden. All
filesystem fixtures are temporary. The Windows fixture creates and unlinks one
temporary junction to prove static refusal, without traversing its destination.
The existing settings test only mocks storage startup so it never scans a real
tree. Parent owns aggregate-runner integration and independent review.

Synthetic checks do not prove actual Tk painting, DPI/screen-reader behavior or
real-model sizes. Those remain explicit live acceptance limits; no GUI, mic,
downloads, user model/cache trees or app restarts were used for this work.

Worker validation on 2026-10-04: 12 focused tests passed (4.670 s), followed by
109 existing aggregate tests passed (65.485 s). Branch `codex/model-storage-usage`,
base/HEAD `47fa5d120e57331493be5747b91b4467fb73f341`. No commit, merge, push, release
or dependency installation. The working tree is the review candidate; parent
owns independent review and integration.
