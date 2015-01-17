import mock
import os

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from bpython.curtsiesfrontend.filewatch import ModuleChangedEventHandler

class TestModuleChangeEventHandler(unittest.TestCase):
    
    def setUp(self):
        self.module = ModuleChangedEventHandler([], 1)
        self.module.observer = mock.Mock()
        
    def test_create_module_handler(self):
        self.assertIsInstance(self.module, ModuleChangedEventHandler)
        
    def test_add_module(self):
        self.module._add_module('something/test.py')
        self.assertIn(os.path.abspath('something/test'), 
                      self.module.dirs[os.path.abspath('something')])
    
    def test_activate_throws_error_when_already_activated(self):
        self.module.activated = True
        with self.assertRaises(ValueError):
            self.module.activate()
    
    