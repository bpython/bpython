import unittest
import sys
py3 = (sys.version_info[0] == 3)

from bpython.curtsiesfrontend import repl

class TestCurtsiesRepl(unittest.TestCase):

    def setUp(self):
        self.repl = repl.Repl()

    def test_buffer_finished_will_parse(self):
        self.repl.buffer = ['1 + 1']
        self.assertTrue(self.repl.buffer_finished_will_parse(), (True, True))
        self.repl.buffer = ['def foo(x):']
        self.assertTrue(self.repl.buffer_finished_will_parse(), (False, True))
        self.repl.buffer = ['def foo(x)']
        self.assertTrue(self.repl.buffer_finished_will_parse(), (True, False))
        self.repl.buffer = ['def foo(x):', 'return 1']
        self.assertTrue(self.repl.buffer_finished_will_parse(), (True, False))
        self.repl.buffer = ['def foo(x):', '    return 1']
        self.assertTrue(self.repl.buffer_finished_will_parse(), (True, True))
        self.repl.buffer = ['def foo(x):', '    return 1', '']
        self.assertTrue(self.repl.buffer_finished_will_parse(), (True, True))

if __name__ == '__main__':
    unittest.main()
