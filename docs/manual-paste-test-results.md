# Manual Paste Test Results

This file records manual paste/focus test results reported during local app testing.

## 2026-06-17 - Browser test page

Source page: `tools/paste_test_page.html`

Tester report time: about 23:31-23:32 Europe/Moscow.

Summary:

| ID | Target | Result | Evidence |
| --- | --- | --- | --- |
| B1 | Plain input | OK | Page log emitted both `paste` and `input`, final length 25. |
| B2 | Search input | OK | Page log emitted both `paste` and `input`, final length 28. |
| B3 | Prefilled input | OK | Existing prefix was preserved; page log emitted both `paste` and `input`, final length 34. |
| B4 | Textarea | OK | Page log emitted both `paste` and `input`, final length 182. |
| B5 | Textarea second/longer insertion | Partial OK | Same textarea accepted a longer dictated fragment; do a clean second-insertion pass later if needed. |
| B6 | Contenteditable | OK | Existing prefix was preserved; page log emitted both `paste` and `input`, final length 51. |
| B7 | Iframe textarea | OK | Iframe target emitted both `paste` and `input`, final length 57. |
| B8 | Tab switching/current target | OK | User verified the same browser test page in Chrome and reported `B8 OK`. |

Observed status:

- No `CLIPBOARD`-only case in the browser page log.
- No `WRONG_TARGET` case in the browser page log.
- No `OVERWRITE` case in the browser page log.
- No `FOCUS_BACK` without insertion in the browser page log.
- Chrome tab switching/current-target behavior passed in the follow-up B8 check.

Next paste-test focus:

- Native Windows matrix: Notepad and Windows search.
- Downloadable/real apps: VS Code or VSCodium, Telegram Desktop, Discord, LibreOffice Writer, or Obsidian.
