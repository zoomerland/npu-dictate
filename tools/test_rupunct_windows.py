"""Deterministic punctuation-window regressions; no model files or devices needed."""

import re
import unittest

import numpy as np

from rupunct_restore import RUPunctRestorer


LABELS = {0: "LOWER_O", 1: "UPPER_O", 2: "LOWER_PERIOD", 3: "LOWER_COMMA"}


class FakeTokenizer:
    def __init__(self, piece_length=None):
        self.piece_length = piece_length
        self.calls = []
        self.token_words = {}

    def num_special_tokens_to_add(self, pair=False):
        return 2

    def __call__(self, text, **kwargs):
        self.calls.append(kwargs)
        tokens = []
        self.token_words = {}
        for match in re.finditer(r"\S+", text):
            step = self.piece_length or len(match.group())
            for start in range(match.start(), match.end(), step):
                token_id = len(tokens) + 10
                tokens.append((token_id, (start, min(start + step, match.end()))))
                self.token_words[token_id] = match.group()
        max_len = kwargs["max_length"]
        budget = max_len - 2
        stride = kwargs.get("stride", 0)
        assert 0 <= stride < budget
        windows = []
        start = 0
        while True:
            piece = tokens[start : start + budget]
            ids = [1] + [token_id for token_id, _offset in piece] + [2]
            offsets = [(0, 0)] + [offset for _token_id, offset in piece] + [(0, 0)]
            mask = [1] * len(ids) + [0] * (max_len - len(ids))
            ids += [0] * (max_len - len(ids))
            offsets += [(0, 0)] * (max_len - len(offsets))
            windows.append((ids, offsets, mask))
            if start + budget >= len(tokens) or not kwargs.get("return_overflowing_tokens"):
                break
            start += budget - stride
        return {
            "input_ids": np.array([window[0] for window in windows]),
            "offset_mapping": np.array([window[1] for window in windows]),
            "attention_mask": np.array([window[2] for window in windows]),
            "token_type_ids": np.zeros((len(windows), max_len), dtype=np.int64),
            "overflow_to_sample_mapping": np.zeros(len(windows), dtype=np.int64),
        }


class FakeCompiled:
    def __init__(self, tokenizer, edge_labels=False, word_labels=None):
        self.tokenizer = tokenizer
        self.edge_labels = edge_labels
        self.word_labels = word_labels or {}
        self.calls = []

    def output(self, name):
        assert name == "logits"
        return name

    def __call__(self, inputs):
        self.calls.append(inputs)
        assert set(inputs) == {"input_ids", "attention_mask", "token_type_ids"}
        ids = inputs["input_ids"]
        assert ids.shape[0] == 1
        assert all(value.dtype == np.int64 for value in inputs.values())
        logits = np.full((*ids.shape, len(LABELS)), -8.0)
        positions = np.flatnonzero(ids[0] >= 10)
        for position in range(ids.shape[1]):
            word = self.tokenizer.token_words.get(int(ids[0, position]), "")
            label = self.word_labels.get(word, 0)
            if self.edge_labels and len(positions):
                if position == positions[0]:
                    label = 1
                if position == positions[-1]:
                    label = 2
            logits[0, position, label] = 8.0
        return {"logits": logits}


def make_restorer(max_len=128, **kwargs):
    restorer = RUPunctRestorer.__new__(RUPunctRestorer)
    restorer.max_len = max_len
    restorer.id2label = LABELS
    restorer.tokenizer = FakeTokenizer(kwargs.pop("piece_length", None))
    restorer.compiled = FakeCompiled(restorer.tokenizer, **kwargs)
    return restorer


def lexical_words(text):
    return re.findall(r"\w+", text.casefold())


class PunctuationWindowTests(unittest.TestCase):
    def assert_preserved(self, source, result):
        self.assertEqual(lexical_words(source), lexical_words(result))
        self.assertNotIn("\n", result)
        self.assertNotIn("\r", result)

    def test_short_path_keeps_legacy_groups(self):
        restorer = make_restorer(word_labels={"today": 3})
        text = "hello today we test"
        groups = restorer._predict_groups(text)
        self.assertEqual([(g["start"], g["end"], g["label"]) for g in groups],
                         [(0, 5, "LOWER_O"), (6, 11, "LOWER_COMMA"), (12, 19, "LOWER_O")])
        self.assertEqual(restorer._render_groups(text, groups), "Hello today, we test")
        self.assertEqual(len(restorer.compiled.calls), 1)

    def test_long_text_preserves_order_and_static_shape(self):
        restorer = make_restorer()
        text = " ".join(f"word{index:04d}" for index in range(500))
        self.assert_preserved(text, restorer.restore(text))
        self.assertGreater(len(restorer.compiled.calls), 1)
        for inputs in restorer.compiled.calls:
            self.assertEqual(inputs["input_ids"].shape, (1, 128))

    def test_window_edges_do_not_create_sentence_breaks(self):
        restorer = make_restorer(edge_labels=True)
        text = " ".join(f"word{index:04d}" for index in range(400))
        result = restorer.restore(text)
        self.assert_preserved(text, result)
        self.assertEqual(result, text[:1].upper() + text[1:] + ".")

    def test_word_split_across_windows_is_rendered_once(self):
        restorer = make_restorer(max_len=16, piece_length=3)
        text = " ".join(f"multisyllable{index:02d}" for index in range(30))
        result = restorer.restore(text)
        self.assert_preserved(text, result)
        self.assertEqual(result.split(), [word.capitalize() if index == 0 else word
                                         for index, word in enumerate(text.split())])

    def test_oversized_word_is_not_truncated_or_split(self):
        restorer = make_restorer(max_len=8, piece_length=2)
        text = "before " + "unusuallylong" * 20 + " after"
        self.assert_preserved(text, restorer.restore(text))
        self.assertEqual(restorer.restore(text).split()[1], text.split()[1])

    def test_real_label_inside_overlap_is_kept(self):
        text = " ".join(f"word{index:04d}" for index in range(300))
        restorer = make_restorer(edge_labels=True, word_labels={"word0100": 3, "word0180": 2})
        result = restorer.restore(text)
        self.assert_preserved(text, result)
        self.assertIn("word0100, word0101", result)
        self.assertIn("word0180. Word0181", result)
        self.assertEqual(result.count("."), 2)

    def test_long_inserted_text_uses_context_without_copying_it(self):
        context = " ".join(f"old{index:04d}" for index in range(200)) + "."
        raw = " ".join(f"new{index:04d}" for index in range(250))
        restorer = make_restorer()
        result = restorer.restore_inserted(context, raw)
        self.assert_preserved(raw, result)
        self.assertTrue(result.startswith("New0000 "))
        self.assertNotIn("old", result)

    def test_unfinished_context_keeps_lowercase_and_clause_prefix(self):
        context = " ".join(f"old{index:04d}" for index in range(200))
        restorer = make_restorer(word_labels={"old0199": 3})
        result = restorer.restore_inserted(context, "continue here")
        self.assertEqual(result, ", continue here")
        self.assertEqual(restorer.restore_inserted(context + ",", "continue here"), "continue here")

    def test_unicode_and_whitespace_preserve_whole_words(self):
        words = ["\u043f\u0440\u0438\u0432\u0435\u0442", "caf\u00e9", "\u65e5\u672c\u8a9e"] * 100
        restorer = make_restorer(piece_length=2)
        text = "\n\t".join(words)
        self.assert_preserved(text, restorer.restore(text))

    def test_empty_text_and_empty_insert_do_not_add_content(self):
        restorer = make_restorer()
        self.assertEqual(restorer.restore(""), "")
        self.assertEqual(restorer.restore("   "), "")
        self.assertEqual(restorer.restore_inserted("context", ""), "")

    def test_invalid_window_budget_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "at least one text token"):
            make_restorer(max_len=2).restore("hello")


if __name__ == "__main__":
    unittest.main()
