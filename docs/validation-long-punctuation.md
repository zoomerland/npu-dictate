# Long Punctuation Regression

Date: 2026-10-03.
Scope: prevent silent text loss after ASR when RUPunct exceeds its static
128-token input limit. This is not a new ASR model, audio-bucket change,
semantic paragraph detector, or release build.

## Failure and Fix

The old tokenizer used `truncation=True` without consuming overflow windows.
The renderer therefore discarded every word beyond the first window. Context
before the cursor used part of the same budget and could leave no room for
newly dictated text.

The restorer now consumes all tokenizer overflow windows with 32 text tokens
of overlap. Each inference still receives one static `[1, 128]` input, including
special tokens. Whole-word character spans select predictions with the most
token context on both sides. Each original word is rendered once, in order;
an oversized word that fits no window is retained without inferred punctuation.
Casing and punctuation are rendered over the combined groups, rather than
reset at every window. No paragraph breaks are inserted by the window join.

Single-window input uses the existing grouping and rendering logic. The
same fix applies to `restore()` and `restore_inserted()` on CPU or NPU.
Model files, audio capture, VAD, ASR stitching, and paste behavior are unchanged.

## Real Long-Audio Check

The test WAV contains exactly 300 seconds assembled from 14 distinct saved
dictations and brief silence. It is not an original continuous monologue.
The fixed run reads the diagnostic fixture's saved PCM16 WAV. The earlier
run used its in-memory float samples before that PCM16 serialization, so
small ASR text differences are not a controlled ASR regression comparison.

The application handler `DictationEngine._transcribe_recording` ran headlessly
with GigaAM OpenVINO NNCF INT8 bucket 400, VAD segmentation, and RUPunct FP16
static 128, both on the available Intel NPU. Clipboard writes were intercepted
in memory. No live microphone, real clipboard, or foreground application was
used.

| Check | Before | Fixed |
| --- | ---: | ---: |
| Audio duration | 300 s | 300 s |
| ASR chunks | 116 | 116 |
| Raw whitespace-delimited words | 453 | 453 |
| Final whitespace-delimited items | 122 | 460 |
| All raw lexical words retained in order | No | Yes |
| Final ten raw words retained | No | Yes |
| Added LF / CR | 0 / 0 | 0 / 0 |
| Punctuation input windows | 1 | 6 |
| Punctuation time, excluding loading | 0.802 s | 0.527 s |
| Handler time, excluding loading | 22.355 s | 23.378 s |

Punctuation can add standalone dashes, which count as whitespace-delimited
items. Preservation was checked with ordered, case-folded `\w+` sequences,
not by equating these item counts. The exact original pre-fix raw transcript
was also fed directly to the fixed NPU punctuator; all lexical words were
preserved. Timings are individual diagnostic runs, not a throughput benchmark
or proof that processing more text is faster.
Two fixed NPU runs retained all words with identical final text and six windows;
the earlier fixed run took 0.638 s for punctuation and 26.406 s for the handler.

No complete ground-truth transcript exists for this fixture. The test proves
preservation after ASR, not recognition accuracy. The originally reported
paragraph formatting came from a separate agent's transcription script;
that exact script/output was not tested here. This fix does not repair an
already generated external TXT file.

## Regression Checks

- Eleven deterministic tests cover overflow, static batch shape, edge labels,
  multi-token words, oversized words, Unicode/whitespace, genuine punctuation,
  insertion context beyond one window, short legacy groups, and empty input.
- Five real CPU short/context examples were captured before the edit and
  compared after it. All five outputs are identical.
- Full `tools/smoke_checks.py --rupunct-timeout 120` passed with zero failures
  and zero warnings. Its real CPU check now also exercises long text and
  insertion after a long context.

Reproduce the model-free and ordinary local checks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tools -p test_rupunct_windows.py -v
.\.venv\Scripts\python.exe tools/smoke_checks.py --rupunct-timeout 120
git diff --check
```

Private WAV/TXT/JSON diagnostic artifacts remain in ignored `recordings/`.
No recordings, transcript contents, models, or local configuration are included
in the feature commit. The work starts from `features/next` at `f5a424c` on
`codex/long-punctuation-windows`; release and outreach publication are separate.
