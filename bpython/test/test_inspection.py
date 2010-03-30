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
