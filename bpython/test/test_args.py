import subprocess
import sys
import tempfile
from textwrap import dedent

from bpython import args
from bpython.test import FixLanguageTestCase as TestCase

try:
    import unittest2 as unittest
except ImportError:
    import unittest

try:
    from nose.plugins.attrib import attr
except ImportError:
    def attr(*args, **kwargs):
        def identity(func):
            return func
        return identity


@attr(speed='slow')
class TestExecArgs(unittest.TestCase):
    def test_exec_dunder_file(self):
        with tempfile.NamedTemporaryFile(mode="w") as f:
            f.write(dedent("""\
                import sys
                sys.stderr.write(__file__)
                sys.stderr.flush()"""))
            f.flush()
            p = subprocess.Popen(
                [sys.executable] +
                (['-W', 'ignore'] if sys.version_info[:2] == (2, 6) else []) +
                ["-m", "bpython.curtsies", f.name],
                stderr=subprocess.PIPE,
                universal_newlines=True)
            (_, stderr) = p.communicate()

            self.assertEquals(stderr.strip(), f.name)


class TestParse(TestCase):

    def test_version(self):
        with self.assertRaises(SystemExit):
            args.parse(['--version'])
