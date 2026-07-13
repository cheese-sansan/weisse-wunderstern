"""json_parser 单元测试。"""
import unittest

from noteforge.json_tools import extract_json


class TestJsonParser(unittest.TestCase):

    def test_plain_json(self):
        result, err = extract_json('{"key": "value"}')
        self.assertIsNone(err)
        self.assertEqual(result, {"key": "value"})

    def test_json_in_markdown_block(self):
        text = '```json\n{"key": "value"}\n```'
        result, err = extract_json(text)
        self.assertIsNone(err)
        self.assertEqual(result, {"key": "value"})

    def test_json_with_text_around(self):
        text = 'Here is the result: {"key": "value"} end.'
        result, err = extract_json(text)
        self.assertIsNone(err)
        self.assertEqual(result, {"key": "value"})

    def test_json_array(self):
        result, err = extract_json('[1, 2, 3]')
        self.assertIsNone(err)
        self.assertEqual(result, [1, 2, 3])

    def test_trailing_comma_removed(self):
        text = '{"key": "value",}'
        result, err = extract_json(text)
        self.assertIsNone(err)
        self.assertEqual(result, {"key": "value"})

    def test_trailing_comma_in_array(self):
        text = '{"items": [1, 2,]}'
        result, err = extract_json(text)
        self.assertIsNone(err)
        self.assertEqual(result, {"items": [1, 2]})

    def test_empty_input(self):
        result, err = extract_json("")
        self.assertIsNone(result)
        self.assertIsNotNone(err)

    def test_none_input(self):
        result, err = extract_json(None)
        self.assertIsNone(result)
        self.assertIsNotNone(err)

    def test_nested_json(self):
        text = '{"a": {"b": [1, 2, 3]}, "c": "d"}'
        result, err = extract_json(text)
        self.assertIsNone(err)
        self.assertEqual(result["a"]["b"], [1, 2, 3])

    def test_invalid_json(self):
        result, err = extract_json("not json at all")
        self.assertIsNone(result)
        self.assertIsNotNone(err)


if __name__ == "__main__":
    unittest.main()
