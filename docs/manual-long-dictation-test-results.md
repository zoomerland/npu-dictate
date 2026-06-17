# Manual Long Dictation Test Results

This file records manual long-dictation test results reported during local app testing.

## 2026-06-18 - Long dictation pass

Source plan: `docs/manual-long-dictation-test-plan.md`

Summary:

| ID | Scenario | Result | Evidence |
| --- | --- | --- | --- |
| L1 | Immediate start | OK | User reported no critical first-word loss in the manual pass. |
| L2 | Normal long paragraph | OK | User reported the long-dictation tests passed at a solid usable level. |
| L3 | Pauses inside one recording | OK | User reported no critical failures with pauses. |
| L4 | Longer silence inside recording | OK | User reported no critical failures with longer silence. |
| L5 | Repeated words | Partial OK | User reported acceptable behavior for small repetition counts, but repeated-word counts can drift in extreme repeated phrases such as 9 of 10 repeated words. |
| L6 | Fast speech | OK | User reported no critical failures in the overall long-dictation pass. |
| L7 | Accidental silence | OK | User reported the test set passed without critical issues. |
| L8 | Too short recording | OK | User reported the test set passed without critical issues. |
| L9 | Overlay drag cancellation | OK | User reported the test set passed without critical issues. |

Observed status:

- Long dictation is acceptable for v0.1 manual acceptance.
- Minor recognition imperfections remain, but no large blocking failures were reported.
- Repeated-word exact counts are not guaranteed when many identical words are dictated in a row.

Known follow-up:

- Keep repeated-word count drift as a non-blocking known limitation.
- Do not tune this before v0.1 unless it starts affecting realistic daily dictation.
