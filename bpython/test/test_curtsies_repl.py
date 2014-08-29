import unittest
import sys
import os
py3 = (sys.version_info[0] == 3)

from bpython.curtsiesfrontend import repl
from bpython import config

def setup_config(conf):
    config_struct = config.Struct()
    config.loadini(config_struct, os.devnull)
    for key, value in conf.items():
        if not hasattr(config_struct, key):
            raise ValueError("%r is not a valid config attribute", (key,))
        setattr(config_struct, key, value)
    return config_struct

class TestCurtsiesRepl(unittest.TestCase):

    def setUp(self):
        self.config = setup_config({'editor':'true'})
        self.repl = repl.Repl(config=self.config)
        os.environ['PAGER'] = 'true'
        self.repl.width = 50
        self.repl.height = 20

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

    def test_external_communication(self):
        self.assertEqual(type(self.repl.version_help_text()), type(b''))
        self.repl.send_current_block_to_external_editor()
        self.repl.send_session_to_external_editor()


if __name__ == '__main__':
    unittest.main()
