import subprocess
import sys
import tempfile
from textwrap import dedent

try:
    import unittest2 as unittest
except ImportError:
    import unittest

class TestExecArgs(unittest.TestCase):
    def test_exec_dunder_file(self):
        with tempfile.NamedTemporaryFile(mode="w") as f:
            f.write(dedent("""\
                import sys
                sys.stderr.write(__file__)
                sys.stderr.flush()"""))
            f.flush()
            p = subprocess.Popen(
                [sys.executable, "-m", "bpython.curtsies", f.name],
                stderr=subprocess.PIPE,
                universal_newlines=True)
            (_, stderr) = p.communicate()

            self.assertEquals(stderr.strip(), f.name)
