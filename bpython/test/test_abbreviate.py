import bpython.scrollfrontend.abbreviate as abbreviate
import unittest

class TestAbbreviate(unittest.TestCase):

    def test_substitution(self):
        self.assertEqual(abbreviate.substitute_abbreviations(0, 'improt asdf'), (0, 'import asdf'))

    def test_no_substitution(self):
        self.assertEqual(abbreviate.substitute_abbreviations(0, 'foo(x, y() - 2.3242) + "asdf"'), (0, 'foo(x, y() - 2.3242) + "asdf"'))

if __name__ == '__main__':
    unittest.main()
