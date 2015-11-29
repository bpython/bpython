# -*- coding: utf-8 -*-

import ast

from bpython.simpleeval import simple_eval
from bpython.test import unittest


class TestInspection(unittest.TestCase):
    def assertMatchesStdlib(self, expr):
        self.assertEqual(ast.literal_eval(expr), simple_eval(expr))

    def test_matches_stdlib(self):
        """Should match the stdlib literal_eval if no names or indexing"""
        self.assertMatchesStdlib("[1]")
        self.assertMatchesStdlib("{(1,): [2,3,{}]}")

    def test_indexing(self):
        """Literals can be indexed into"""
        self.assertEqual(simple_eval('[1,2][0]'), 1)
        self.assertEqual(simple_eval('a', {'a':1}), 1)

    def test_name_lookup(self):
        """Names can be lookup up in a namespace"""
        self.assertEqual(simple_eval('a', {'a':1}), 1)
        self.assertEqual(simple_eval('map'), map)
        self.assertEqual(simple_eval('a[b]', {'a':{'c':1}, 'b':'c'}), 1)

    def test_allow_name_lookup(self):
        """Names can be lookup up in a namespace"""
        self.assertEqual(simple_eval('a', {'a':1}), 1)

    def test_lookup_on_suspicious_types(self):
        class FakeDict(object):
            pass

        with self.assertRaises(ValueError):
            simple_eval('a[1]', {'a': FakeDict()})

        class TrickyDict(dict):
            def __getitem__(self, index):
                self.fail("doing key lookup isn't safe")

        with self.assertRaises(ValueError):
            simple_eval('a[1]', {'a': TrickyDict()})

        class SchrodingersDict(dict):
            def __getattribute__(inner_self, attr):
                self.fail("doing attribute lookup might have side effects")

        with self.assertRaises(ValueError):
            simple_eval('a[1]', {'a': SchrodingersDict()})

        class SchrodingersCatsDict(dict):
            def __getattr__(inner_self, attr):
                self.fail("doing attribute lookup might have side effects")

        with self.assertRaises(ValueError):
            simple_eval('a[1]', {'a': SchrodingersDict()})

    def test_function_calls_raise(self):
        with self.assertRaises(ValueError):
            simple_eval('1()')

    def test_nonexistant_names_raise(self):
        with self.assertRaises(KeyError):
            simple_eval('a')


if __name__ == '__main__':
    unittest.main()
