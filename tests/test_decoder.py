import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fixtures import FIXTURES, FOOTER, HEADER  # noqa: E402
from mini_rton import RtonError, decode  # noqa: E402


class DecodeFixtures(unittest.TestCase):
    def test_all_fixtures(self):
        for name, (data, expected) in FIXTURES.items():
            with self.subTest(name=name):
                self.assertEqual(decode(data), expected)


class ErrorHandling(unittest.TestCase):
    def body(self, hex_text):
        return HEADER + bytes.fromhex(hex_text) + FOOTER

    def test_bad_magic(self):
        with self.assertRaises(RtonError):
            decode(b"XXXX" + FIXTURES["empty"][0][4:])

    def test_bad_version(self):
        data = b"RTON" + (2).to_bytes(4, "little") + b"\xff" + FOOTER
        with self.assertRaises(RtonError):
            decode(data)

    def test_missing_footer(self):
        with self.assertRaises(RtonError):
            decode(HEADER + b"\xff")

    def test_trailing_bytes(self):
        with self.assertRaises(RtonError):
            decode(FIXTURES["empty"][0] + b"\x00")

    def test_truncated_string(self):
        with self.assertRaises(RtonError):
            decode(HEADER + bytes.fromhex("81 05 61"))  # claims 5 bytes, has 1

    def test_cache_index_out_of_range(self):
        with self.assertRaises(RtonError):
            decode(self.body("91 03 00 FF"))

    def test_unsupported_tag(self):
        with self.assertRaises(RtonError):
            decode(self.body("81 01 61 42 00 FF"))  # 0x42 is not implemented

    def test_array_missing_end_marker(self):
        with self.assertRaises(RtonError):
            decode(self.body("81 01 61 86 FD 01 08 01 FF"))

    def test_runaway_varint(self):
        with self.assertRaises(RtonError):
            decode(self.body("81 01 61 24" + " FF" * 12))

    def test_depth_limit(self):
        nested = "81 01 61 85 " * 70
        with self.assertRaises(RtonError):
            decode(self.body(nested))

    def test_invalid_utf8_string(self):
        with self.assertRaises(RtonError):
            decode(self.body("81 01 FF 00 FF"))


if __name__ == "__main__":
    unittest.main()
