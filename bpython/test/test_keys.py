#!/usr/bin/env python
import unittest
import bpython.keys as keys

class TestKeys(unittest.TestCase):
    def test_keymap_getitem(self):
        """Verify keys.KeyMap correctly looking up items."""
        self.assertEqual(keys.key_dispatch['C-['], (chr(27), '^['))
        self.assertEqual(keys.key_dispatch['F11'], ('KEY_F(11)',))
        self.assertEqual(keys.key_dispatch['C-a'], ('\x01', '^A'))

    def test_keymap_keyerror(self):
        """Verify keys.KeyMap raising KeyError when getting undefined key"""
        def raiser():
            keys.key_dispatch['C-asdf']
            keys.key_dispatch['C-qwerty']
        self.assertRaises(KeyError, raiser);

if __name__ == '__main__':
    unittest.main()
