"""Checks the fixtures themselves, before any decoder exists."""
import unittest

from fixtures import FIXTURES


class FixtureSanity(unittest.TestCase):
    def test_every_fixture_has_magic_version_footer(self):
        for name, (data, _expected) in FIXTURES.items():
            with self.subTest(name=name):
                self.assertEqual(data[:4], b"RTON")
                self.assertEqual(int.from_bytes(data[4:8], "little"), 1)
                self.assertEqual(data[-4:], b"DONE")

    def test_every_fixture_body_ends_with_object_end(self):
        for name, (data, _expected) in FIXTURES.items():
            with self.subTest(name=name):
                self.assertEqual(data[-5], 0xFF)


if __name__ == "__main__":
    unittest.main()
