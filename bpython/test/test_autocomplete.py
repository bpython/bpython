from bpython import autocomplete
from functools import partial
import inspect

import unittest


# Parts of autocompletion to test:
# Test that the right matches come back from find_matches (test that priority is correct)
# Test the various complete methods (import, filename) to see if right matches
# Test that MatchesIterator.substitute correctly subs given a match and a completer
"""
    def test_cw(self):

        self.repl.cpos = 2
        self.assertEqual(self.repl.cw(), None)
        self.repl.cpos = 0

        self.repl.s = ''
        self.assertEqual(self.repl.cw(), None)

        self.repl.s = "this.is.a.test\t"
        self.assertEqual(self.repl.cw(), None)

        s = "this.is.a.test"
        self.repl.s = s
        self.assertEqual(self.repl.cw(), s)

        s = "\t\tthis.is.a.test"
        self.repl.s = s
        self.assertEqual(self.repl.cw(), s.lstrip())

        self.repl.s = "import datetime"
        self.assertEqual(self.repl.cw(), 'datetime')
"""

class TestSafeEval(unittest.TestCase):
    def test_catches_syntax_error(self):
        try:
            autocomplete.safe_eval('1re',{})
        except:
            self.fail('safe_eval raises an error')

# make some fake files? Dependency inject? mock?
class TestFilenameCompletion(unittest.TestCase):
    pass


class TestFormatters(unittest.TestCase):

    @unittest.skip('not done yet')
    def test_filename(self):
        self.assertEqual(autocomplete.last_part_of_filename('abc'), 'abc')
        self.assertEqual(autocomplete.last_part_of_filename('abc/'), 'abc/')
        self.assertEqual(autocomplete.last_part_of_filename('abc/efg'), 'efg')
        self.assertEqual(autocomplete.last_part_of_filename('abc/efg/'), 'efg/')
        self.assertEqual(autocomplete.last_part_of_filename('/abc'), 'abc')
        self.assertEqual(autocomplete.last_part_of_filename('ab.c/e.f.g/'), 'e.f.g/')

    @unittest.skip('not done yet')
    def test_attribute(self):
        self.assertEqual(autocomplete.after_last_dot('abc.edf'), 'edf')
