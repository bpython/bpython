# -*- coding: utf-8 -*-

import os

from bpython._py3compat import py3
from bpython import inspection
from bpython.test import unittest
from bpython.test.fodder import encoding_ascii
from bpython.test.fodder import encoding_latin1
from bpython.test.fodder import encoding_utf8


foo_ascii_only = u'''def foo():
    """Test"""
    pass
'''

foo_non_ascii = u'''def foo():
    """Test äöü"""
    pass
'''


class OldCallable:
    def __call__(self):
        pass


class Callable(object):
    def __call__(self):
        pass


class OldNoncallable:
    pass


class Noncallable(object):
    pass


def spam():
    pass


class CallableMethod(object):
    def method(self):
        pass


class TestInspection(unittest.TestCase):
    def test_is_callable(self):
        self.assertTrue(inspection.is_callable(spam))
        self.assertTrue(inspection.is_callable(Callable))
        self.assertTrue(inspection.is_callable(Callable()))
        self.assertTrue(inspection.is_callable(OldCallable))
        self.assertTrue(inspection.is_callable(OldCallable()))
        self.assertFalse(inspection.is_callable(Noncallable()))
        self.assertFalse(inspection.is_callable(OldNoncallable()))
        self.assertFalse(inspection.is_callable(None))
        self.assertTrue(inspection.is_callable(CallableMethod().method))

    @unittest.skipIf(py3, 'old-style classes only exist in Python 2')
    def test_is_new_style_py2(self):
        self.assertTrue(inspection.is_new_style(spam))
        self.assertTrue(inspection.is_new_style(Noncallable))
        self.assertFalse(inspection.is_new_style(OldNoncallable))
        self.assertTrue(inspection.is_new_style(Noncallable()))
        self.assertFalse(inspection.is_new_style(OldNoncallable()))
        self.assertTrue(inspection.is_new_style(None))

    @unittest.skipUnless(py3, 'only in Python 3 are all classes new-style')
    def test_is_new_style_py3(self):
        self.assertTrue(inspection.is_new_style(spam))
        self.assertTrue(inspection.is_new_style(Noncallable))
        self.assertTrue(inspection.is_new_style(OldNoncallable))
        self.assertTrue(inspection.is_new_style(Noncallable()))
        self.assertTrue(inspection.is_new_style(OldNoncallable()))
        self.assertTrue(inspection.is_new_style(None))


    def test_parsekeywordpairs(self):
        # See issue #109
        def fails(spam=['-a', '-b']):
            pass

        default_arg_repr = "['-a', '-b']"
        self.assertEqual(str(['-a', '-b']), default_arg_repr,
                         'This test is broken (repr does not match), fix me.')

        argspec = inspection.getfuncprops('fails', fails)
        defaults = argspec.argspec.defaults
        self.assertEqual(str(defaults[0]), default_arg_repr)

    def test_pasekeywordpairs_string(self):
        def spam(eggs="foo, bar"):
            pass

        defaults = inspection.getfuncprops("spam", spam).argspec.defaults
        self.assertEqual(repr(defaults[0]), "'foo, bar'")

    def test_parsekeywordpairs_multiple_keywords(self):
        def spam(eggs=23, foobar="yay"):
            pass

        defaults = inspection.getfuncprops("spam", spam).argspec.defaults
        self.assertEqual(repr(defaults[0]), "23")
        self.assertEqual(repr(defaults[1]), "'yay'")

    def test_get_encoding_ascii(self):
        self.assertEqual(inspection.get_encoding(encoding_ascii), 'ascii')
        self.assertEqual(inspection.get_encoding(encoding_ascii.foo), 'ascii')

    def test_get_encoding_latin1(self):
        self.assertEqual(inspection.get_encoding(encoding_latin1), 'latin1')
        self.assertEqual(inspection.get_encoding(encoding_latin1.foo),
                         'latin1')

    def test_get_encoding_utf8(self):
        self.assertEqual(inspection.get_encoding(encoding_utf8), 'utf-8')
        self.assertEqual(inspection.get_encoding(encoding_utf8.foo), 'utf-8')

    def test_get_source_ascii(self):
        self.assertEqual(inspection.get_source_unicode(encoding_ascii.foo),
                         foo_ascii_only)

    def test_get_source_utf8(self):
        self.assertEqual(inspection.get_source_unicode(encoding_utf8.foo),
                         foo_non_ascii)

    def test_get_source_latin1(self):
        self.assertEqual(inspection.get_source_unicode(encoding_latin1.foo),
                         foo_non_ascii)

    def test_get_source_file(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'fodder')

        encoding = inspection.get_encoding_file(
            os.path.join(path, 'encoding_ascii.py'))
        self.assertEqual(encoding, 'ascii')
        encoding = inspection.get_encoding_file(
            os.path.join(path, 'encoding_latin1.py'))
        self.assertEqual(encoding, 'latin1')
        encoding = inspection.get_encoding_file(
            os.path.join(path, 'encoding_utf8.py'))
        self.assertEqual(encoding, 'utf-8')


if __name__ == '__main__':
    unittest.main()
