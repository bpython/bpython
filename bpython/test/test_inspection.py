import unittest

from bpython import inspection

class TestInspection(unittest.TestCase):
    def test_is_callable(self):
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

        self.assertTrue(inspection.is_callable(spam))
        self.assertTrue(inspection.is_callable(Callable))
        self.assertTrue(inspection.is_callable(Callable()))
        self.assertTrue(inspection.is_callable(OldCallable))
        self.assertTrue(inspection.is_callable(OldCallable()))
        self.assertFalse(inspection.is_callable(Noncallable()))
        self.assertFalse(inspection.is_callable(OldNoncallable()))
        self.assertFalse(inspection.is_callable(None))

    def test_parsekeywordpairs(self):
        # See issue #109
        def fails(spam=['-a', '-b']):
            pass

        default_arg_repr = "['-a', '-b']"
        self.assertEqual(str(['-a', '-b']), default_arg_repr,
                         'This test is broken (repr does not match), fix me.')

        argspec = inspection.getargspec('fails', fails)
        defaults = argspec[1][3]
        self.assertEqual(str(defaults[0]), default_arg_repr)

    def test_pasekeywordpairs_string(self):
        def spam(eggs="foo, bar"):
            pass

        defaults = inspection.getargspec("spam", spam)[1][3]
        self.assertEqual(repr(defaults[0]), "'foo, bar'")

    def test_parsekeywordpairs_multiple_keywords(self):
        def spam(eggs=23, foobar="yay"):
            pass

        defaults = inspection.getargspec("spam", spam)[1][3]
        self.assertEqual(repr(defaults[0]), "23")
        self.assertEqual(repr(defaults[1]), "'yay'")

if __name__ == '__main__':
    unittest.main()
