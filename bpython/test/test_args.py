import unittest
import subprocess
import tempfile
import sys




class TestExecArgs(unittest.TestCase):
    def test_exec_dunder_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(
            "import sys; print 'hello'; sys.stderr.write(__file__); sys.stderr.flush();")
            f.flush()
            print open(f.name).read()
            p = subprocess.Popen(['bpython-curtsies', f.name], stderr= subprocess.PIPE)
            
            self.assertEquals(p.stderr.read().strip(), f.name)


