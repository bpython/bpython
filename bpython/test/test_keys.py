import unittest
import bpython.keys as keys

class TestKeys(unittest.TestCase):
    def test_keymap_map(self):
        """Verify KeyMap.map being a dictionary with the correct
        length."""
        self.assertEqual(len(keys.key_dispatch.map), 43)

    def test_keymap_setitem(self):
        """Verify keys.KeyMap correctly setting items."""
        keys.key_dispatch['simon'] = 'awesome';
        self.assertEqual(keys.key_dispatch['simon'], 'awesome')

    def test_keymap_delitem(self):
        """Verify keys.KeyMap correctly removing items."""
        keys.key_dispatch['simon'] = 'awesome'
        del keys.key_dispatch['simon']
        if 'simon' in keys.key_dispatch.map:
            raise Exception('Key still exists in dictionary')

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
