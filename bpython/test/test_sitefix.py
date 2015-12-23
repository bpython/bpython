import sys
import optparse

from bpython.test import FixLanguageTestCase as TestCase
from bpython._py3compat import py3

from bpython.curtsiesfrontend import sitefix


class AttrReplaced(object):
    def __init__(self, module, attr, replacement):
        self.module = module
        self.attr = attr
        self.replacement = replacement

    def __enter__(self):
        if hasattr(self.module, self.attr):
            self.orig_value = getattr(self.module, self.attr)
        setattr(self.module, self.attr, self.replacement)

    def __exit__(self, exc_type, exc_value, traceback):
        if hasattr(self, 'orig_value'):
            setattr(self.module, self.attr, self.replacement)
        else:
            delattr(self.module, self.attr)


class TestCurtsiesReevaluateWithImport(TestCase):
    def test_reload_works(self):
        orig = optparse.SUPPRESS_HELP
        with AttrReplaced(optparse, 'SUPPRESS_HELP', 1):
            #  reload(optparse)
            sitefix.reload(optparse)
            self.assertEqual(optparse.SUPPRESS_HELP, orig)

    def test_reload_sys(self):
        with AttrReplaced(sys, 'stdin', 1):
            with AttrReplaced(sys, 'a', 2):
                with AttrReplaced(sys, 'version', 3):
                    sitefix.reload(sys)
                    self.assertEqual(sys.a, 2)  # new attrs stick around
                    self.assertEqual(sys.stdin, 1)  # stdin stays
                    if not py3:
                        # In Python 3 sys attributes are not replaced on reload
                        self.assertNotEqual(sys.version, 3)  # in Python 2
