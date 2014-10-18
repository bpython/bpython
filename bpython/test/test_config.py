import os
import unittest
import tempfile

from bpython import config

TEST_THEME_PATH = os.path.join(os.path.dirname(__file__), "test.theme")

class TestConfig(unittest.TestCase):
    def test_load_theme(self):
        struct = config.Struct()
        struct.color_scheme = dict()
        config.load_theme(struct, TEST_THEME_PATH, struct.color_scheme, dict())
        expected = {"keyword": "y"}
        self.assertEquals(struct.color_scheme, expected)

        defaults = {"name": "c"}
        expected.update(defaults)
        config.load_theme(struct, TEST_THEME_PATH, struct.color_scheme, defaults)
        self.assertEquals(struct.color_scheme, expected)

    def test_load_config(self):
        struct = config.Struct()
        with tempfile.NamedTemporaryFile() as f:
            f.write(''.encode('utf8'))
            f.write('[keyboard]\nhelp = C-h\n'.encode('utf8'))
            f.flush()
            config.loadini(struct, f.name)
        self.assertEqual(struct.help_key, 'C-h')
        self.assertEqual(struct.backspace_key, '')

