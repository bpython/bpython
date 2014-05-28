from bpython import autocomplete
from functools import partial

import unittest

class TestSimpleComplete(unittest.TestCase):

    simple_config = type('', (), {})()
    simple_config.autocomplete_mode = autocomplete.SIMPLE
    complete = partial(autocomplete.complete,
                       namespace={'zabcdef':1, 'zabcqwe':2, 'ze':3},
                       config=simple_config)

    def test_simple_completion(self):
        self.assertEqual(self.complete('zab'), ['zabcdef', 'zabcqwe'])
        self.assertEqual(self.complete('zabc'), ['zabcdef', 'zabcqwe'])
        self.assertEqual(self.complete('zabcd'), ['zabcdef'])

