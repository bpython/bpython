from bpython import autocomplete
from functools import partial
import inspect

import unittest

class TestSimpleComplete(unittest.TestCase):

    complete = partial(autocomplete.complete,
                       namespace={'zabcdef':1, 'zabcqwe':2, 'ze':3},
                       config=simple_config)
    kwargs = {locals_={'zabcdef':1, 'zabcqwe':2, 'ze':3},
              argspec=inspect.getargspec(lambda x: x),

    def test_simple_completion(self):
        self.assertEqual(self.complete('zab'), ['zabcdef', 'zabcqwe'])
        self.assertEqual(self.complete('zabc'), ['zabcdef', 'zabcqwe'])
        self.assertEqual(self.complete('zabcd'), ['zabcdef'])



# Parts of autocompletion to test:
# Test that the right matches come back from find_matches (test that priority is correct)
# Test the various complete methods (import, filename) to see if right matches
# Test that MatchesIterator.substitute correctly subs given a match and a completer


# make some fake files? Dependency inject? mock?
class TestFilenameCompletion(unittest.TestCase):
    pass


class TestFormatters(unittest.TestCase):

    def test_filename(self):
        self.assertEqual(autocomplete.last_part_of_filename('abc'), 'abc')
        self.assertEqual(autocomplete.last_part_of_filename('abc/'), 'abc/')
        self.assertEqual(autocomplete.last_part_of_filename('abc/efg'), 'efg')
        self.assertEqual(autocomplete.last_part_of_filename('abc/efg/'), 'efg/')
        self.assertEqual(autocomplete.last_part_of_filename('/abc'), 'abc')
        self.assertEqual(autocomplete.last_part_of_filename('ab.c/e.f.g/'), 'e.f.g/')

    def test_attribute(self):
        self.assertEqual(autocomplete.after_last_dot('abc.edf'), 'edf')
