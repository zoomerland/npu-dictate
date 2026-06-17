# Manual Long Dictation Test Plan

Goal: test recording and recognition stability for longer dictation. Paste/focus reliability is already covered by the paste matrix, so these tests focus on audio capture, ASR quality, punctuation, pauses, repeated phrases, and accidental recordings.

Recommended target: Notepad or the textarea in `tools/paste_test_page.html`.

Recommended mode: `toggle` mode or the dictation hotkey, because long hold-to-talk recordings are tiring.

## Result Codes

- `OK` - inserted text is usable and the app stayed responsive.
- `FIRST_WORD_LOST` - the beginning of the phrase was cut.
- `QUALITY` - text inserted, but recognition quality is clearly below the current normal level.
- `SLOW` - recognition completed, but felt unusually slow for the sample length.
- `NO_SPEECH` - app correctly ignored silence or no speech.
- `TOO_SHORT` - app correctly ignored a very short accidental recording.
- `CLIPBOARD` - text reached clipboard but did not paste.
- `WRONG_TARGET` - text pasted into the wrong field/window.
- `OVERWRITE` - existing text was unexpectedly replaced.
- `HANG` - app became unresponsive or stayed in loading/transcribing state.

## L1 - Immediate Start

Action:

1. Put the cursor in an empty Notepad document or test textarea.
2. Start recording and begin speaking immediately.
3. Say: `Первое слово не должно потеряться, даже если я начинаю говорить сразу после нажатия кнопки.`

Expected:

- First word is present.
- Text inserts into the target field.
- No old recording tail appears.

Report example:

- `L1 OK`
- `L1 FIRST_WORD_LOST`

## L2 - Normal Long Paragraph

Action:

1. Record one continuous 25-40 second paragraph at normal speed.
2. Use natural speech, not a tongue twister.

Suggested text idea:

`Сейчас я проверяю обычную длинную диктовку. Я говорю спокойным голосом, стараюсь не торопиться и не делать слишком больших пауз. Мне важно понять, что приложение сохраняет начало, середину и конец фразы, а затем вставляет весь текст в одно поле.`

Expected:

- Text appears once, in the correct field.
- No large missing chunks.
- Recognition quality is close to current normal short-dictation quality.

Report example:

- `L2 OK`
- `L2 QUALITY`, with one short example of the bad fragment.

## L3 - Pauses Inside One Recording

Action:

1. Record 35-60 seconds.
2. Include 2-4 pauses of about 1-2 seconds.

Suggested structure:

- Start with one sentence.
- Pause.
- Continue with a second sentence.
- Pause.
- Finish with a third sentence.

Expected:

- The recording remains one dictation result.
- Pauses do not delete nearby words.
- Punctuation remains usable.

Report example:

- `L3 OK`
- `L3 QUALITY after pauses`

## L4 - Longer Silence Inside Recording

Action:

1. Start recording.
2. Say one short sentence.
3. Stay silent for about 4-6 seconds.
4. Say another short sentence.
5. Stop recording.

Expected:

- Both spoken parts are present.
- The app does not hang during or after the silent gap.
- It is acceptable if punctuation around the silence is imperfect.

Report example:

- `L4 OK`
- `L4 MISSING_SECOND_PART`
- `L4 HANG`

## L5 - Repeated Words

Action:

Record a phrase with intentional repetitions:

`Сейчас я проверяю повторы. Можно делать, делать, делать одно и то же слово несколько раз, и приложение не должно ошибочно удалить честные повторы.`

Expected:

- Intentional repeated words are not aggressively removed.
- Some punctuation variation is acceptable.

Report example:

- `L5 OK`
- `L5 QUALITY repeats trimmed`

## L6 - Fast Speech

Action:

Record 10-20 seconds faster than normal, but still understandable.

Expected:

- Some errors are acceptable.
- It should not collapse into nonsense.
- The app should stay responsive.

Report example:

- `L6 OK`
- `L6 QUALITY`
- `L6 SLOW`

## L7 - Accidental Silence

Action:

1. Start recording.
2. Do not speak for 2-4 seconds.
3. Stop recording.

Expected:

- No text is inserted.
- App shows `No speech` or otherwise returns to ready state.

Report example:

- `L7 NO_SPEECH OK`
- `L7 INSERTED_BAD_TEXT`

## L8 - Too Short Recording

Action:

1. Start and stop recording almost immediately.
2. Do not speak, or say only a tiny sound.

Expected:

- No text is inserted.
- App shows `Too short` or returns safely to ready state.

Report example:

- `L8 TOO_SHORT OK`
- `L8 INSERTED_BAD_TEXT`

## L9 - Overlay Drag Cancellation

Only run this if convenient.

Action:

1. Switch to hold-to-talk mode.
2. Press the overlay button and begin recording.
3. While still pressed, drag the overlay enough that it moves.
4. Release.

Expected:

- Recording is canceled.
- No text is inserted.
- Overlay position changes and remains usable.

Report example:

- `L9 OK`
- `L9 INSERTED_TEXT`
- `L9 HANG`

## What To Send Back

Short format is enough:

`L1 OK, L2 OK, L3 OK, L4 OK, L5 OK, L6 QUALITY, L7 NO_SPEECH OK, L8 TOO_SHORT OK`

If something fails, include:

- test ID;
- result code;
- one short example of what went wrong;
- whether the app stayed responsive.
