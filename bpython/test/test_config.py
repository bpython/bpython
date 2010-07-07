import os
import unittest

from bpython import config

TEST_THEME_PATH = os.path.join(os.path.dirname(__file__), "test.theme")

class TestConfig(unittest.TestCase):
    def test_load_theme(self):
        struct = config.Struct()
        config.load_theme(struct, TEST_THEME_PATH, "test.ini", dict())
        expected = {"keyword": "y"}
        self.assertEquals(struct.color_scheme, expected)

        defaults = {"name": "c"}
        expected.update(defaults)
        config.load_theme(struct, TEST_THEME_PATH, "test.ini", defaults)
        self.assertEquals(struct.color_scheme, expected)

    def test_load_gtk_scheme(self):
        struct = config.Struct()
        config.load_gtk_theme(struct, TEST_THEME_PATH, "test.ini", dict())
        expected = {"keyword": "y"}
        self.assertEquals(struct.color_gtk_scheme, expected)

        defaults = {"name": "c"}
        expected.update(defaults)
        config.load_gtk_theme(struct, TEST_THEME_PATH, "test.ini", defaults)
        self.assertEquals(struct.color_gtk_scheme, expected)


if __name__ == '__main__':
    unittest.main()
