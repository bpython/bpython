from bpython import autocomplete
from functools import partial
import inspect

import unittest
try:
    from unittest import skip
except ImportError:
    def skip(f):
        return lambda self: None

#TODO: Parts of autocompletion to test:
# Test that the right matches come back from find_matches (test that priority is correct)
# Test the various complete methods (import, filename) to see if right matches
# Test that MatchesIterator.substitute correctly subs given a match and a completer

class TestSafeEval(unittest.TestCase):
    def test_catches_syntax_error(self):
        try:
            autocomplete.safe_eval('1re',{})
        except:
            self.fail('safe_eval raises an error')

class TestFormatters(unittest.TestCase):

    def test_filename(self):
        last_part_of_filename = autocomplete.FilenameCompletion.format
        self.assertEqual(last_part_of_filename('abc'), 'abc')
        self.assertEqual(last_part_of_filename('abc/'), 'abc/')
        self.assertEqual(last_part_of_filename('abc/efg'), 'efg')
        self.assertEqual(last_part_of_filename('abc/efg/'), 'efg/')
        self.assertEqual(last_part_of_filename('/abc'), 'abc')
        self.assertEqual(last_part_of_filename('ab.c/e.f.g/'), 'e.f.g/')

    def test_attribute(self):
        self.assertEqual(autocomplete.after_last_dot('abc.edf'), 'edf')
