# -*- coding: utf-8 -*-

import ast
import numbers

from bpython.simpleeval import (simple_eval,
                                evaluate_current_expression,
                                EvaluationError,
                                safe_get_attribute,
                                safe_get_attribute_new_style)
from bpython.test import unittest
from bpython._py3compat import py3


class TestSimpleEval(unittest.TestCase):
    def assertMatchesStdlib(self, expr):
        self.assertEqual(ast.literal_eval(expr), simple_eval(expr))

    def test_matches_stdlib(self):
        """Should match the stdlib literal_eval if no names or indexing"""
        self.assertMatchesStdlib("[1]")
        self.assertMatchesStdlib("{(1,): [2,3,{}]}")

    def test_indexing(self):
        """Literals can be indexed into"""
        self.assertEqual(simple_eval('[1,2][0]'), 1)
        self.assertEqual(simple_eval('a', {'a': 1}), 1)

    def test_name_lookup(self):
        """Names can be lookup up in a namespace"""
        self.assertEqual(simple_eval('a', {'a': 1}), 1)
        self.assertEqual(simple_eval('map'), map)
        self.assertEqual(simple_eval('a[b]', {'a': {'c': 1}, 'b': 'c'}), 1)

    def test_allow_name_lookup(self):
        """Names can be lookup up in a namespace"""
        self.assertEqual(simple_eval('a', {'a': 1}), 1)

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

    def test_operators_on_suspicious_types(self):
        class Spam(numbers.Number):
            def __add__(inner_self, other):
                self.fail("doing attribute lookup might have side effects")

        with self.assertRaises(ValueError):
            simple_eval('a + 1', {'a': Spam()})

    def test_operators_on_numbers(self):
        self.assertEqual(simple_eval('-2'), -2)
        self.assertEqual(simple_eval('1 + 1'), 2)
        self.assertEqual(simple_eval('a - 2', {'a': 1}), -1)
        with self.assertRaises(ValueError):
            simple_eval('2 * 3')
        with self.assertRaises(ValueError):
            simple_eval('2 ** 3')

    def test_function_calls_raise(self):
        with self.assertRaises(ValueError):
            simple_eval('1()')

    def test_nonexistant_names_raise(self):
        with self.assertRaises(EvaluationError):
            simple_eval('a')

    def test_attribute_access(self):
        class Foo(object):
            abc = 1

        self.assertEqual(simple_eval('foo.abc', {'foo': Foo()}), 1)


class TestEvaluateCurrentExpression(unittest.TestCase):

    def assertEvaled(self, line, value, ns=None):
        assert line.count('|') == 1
        cursor_offset = line.find('|')
        line = line.replace('|', '')
        self.assertEqual(evaluate_current_expression(cursor_offset, line, ns),
                         value)

    def assertCannotEval(self, line, ns=None):
        assert line.count('|') == 1
        cursor_offset = line.find('|')
        line = line.replace('|', '')
        with self.assertRaises(EvaluationError):
            evaluate_current_expression(cursor_offset, line, ns)

    def test_simple(self):
        self.assertEvaled('[1].a|bc', [1])
        self.assertEvaled('[1].abc|', [1])
        self.assertEvaled('[1].|abc', [1])
        self.assertEvaled('[1]. |abc', [1])
        self.assertEvaled('[1] .|abc', [1])
        self.assertCannotEval('[1].abc |', [1])
        self.assertCannotEval('[1]. abc |', [1])
        self.assertCannotEval('[2][1].a|bc', [1])

    def test_nonsense(self):
        self.assertEvaled('!@#$ [1].a|bc', [1])
        self.assertEvaled('--- [2][0].a|bc', 2)
        self.assertCannotEval('"asdf".centered()[1].a|bc')
        self.assertEvaled('"asdf"[1].a|bc', 's')

    def test_with_namespace(self):
        self.assertEvaled('a[1].a|bc', 'd', {'a': 'adsf'})
        self.assertCannotEval('a[1].a|bc', {})


class A(object):
    a = 'a'


class B(A):
    b = 'b'


class Property(object):
    @property
    def prop(self):
        raise AssertionError('Property __get__ executed')


class Slots(object):
    __slots__ = ['s1', 's2', 's3']

    if not py3:
        @property
        def s3(self):
            raise AssertionError('Property __get__ executed')


class SlotsSubclass(Slots):
    @property
    def s4(self):
        raise AssertionError('Property __get__ executed')


class OverriddenGetattr(object):
    def __getattr__(self, attr):
        raise AssertionError('custom __getattr__ executed')
    a = 1


class OverriddenGetattribute(object):
    def __getattribute__(self, attr):
        raise AssertionError('custom __getattribute__ executed')
    a = 1


class OverriddenMRO(object):
    def __mro__(self):
        raise AssertionError('custom mro executed')
    a = 1


member_descriptor = type(Slots.s1)


class TestSafeGetAttribute(unittest.TestCase):

    def test_lookup_on_object(self):
        a = A()
        a.x = 1
        self.assertEquals(safe_get_attribute_new_style(a, 'x'), 1)
        self.assertEquals(safe_get_attribute_new_style(a, 'a'), 'a')
        b = B()
        b.y = 2
        self.assertEquals(safe_get_attribute_new_style(b, 'y'), 2)
        self.assertEquals(safe_get_attribute_new_style(b, 'a'), 'a')
        self.assertEquals(safe_get_attribute_new_style(b, 'b'), 'b')

    def test_avoid_running_properties(self):
        p = Property()
        self.assertEquals(safe_get_attribute_new_style(p, 'prop'),
                          Property.prop)

    @unittest.skipIf(py3, 'Old-style classes not in Python 3')
    def test_raises_on_old_style_class(self):
        class Old:
            pass
        with self.assertRaises(ValueError):
            safe_get_attribute_new_style(Old, 'asdf')

    def test_lookup_with_slots(self):
        s = Slots()
        s.s1 = 's1'
        self.assertEquals(safe_get_attribute(s, 's1'), 's1')
        self.assertIsInstance(safe_get_attribute_new_style(s, 's1'),
                              member_descriptor)
        with self.assertRaises(AttributeError):
            safe_get_attribute(s, 's2')
        self.assertIsInstance(safe_get_attribute_new_style(s, 's2'),
                              member_descriptor)

    def test_lookup_on_slots_classes(self):
        sga = safe_get_attribute
        s = SlotsSubclass()
        self.assertIsInstance(sga(Slots, 's1'), member_descriptor)
        self.assertIsInstance(sga(SlotsSubclass, 's1'), member_descriptor)
        self.assertIsInstance(sga(SlotsSubclass, 's4'), property)
        self.assertIsInstance(sga(s, 's4'), property)

    @unittest.skipIf(py3, "Py 3 doesn't allow slots and prop in same class")
    def test_lookup_with_property_and_slots(self):
        sga = safe_get_attribute
        s = SlotsSubclass()
        self.assertIsInstance(sga(Slots, 's3'), property)
        self.assertEquals(safe_get_attribute(s, 's3'),
                          Slots.__dict__['s3'])
        self.assertIsInstance(sga(SlotsSubclass, 's3'), property)

    def test_lookup_on_overridden_methods(self):
        sga = safe_get_attribute
        self.assertEqual(sga(OverriddenGetattr(), 'a'), 1)
        self.assertEqual(sga(OverriddenGetattribute(), 'a'), 1)
        self.assertEqual(sga(OverriddenMRO(), 'a'), 1)
        with self.assertRaises(AttributeError):
            sga(OverriddenGetattr(), 'b')
        with self.assertRaises(AttributeError):
            sga(OverriddenGetattribute(), 'b')
        with self.assertRaises(AttributeError):
            sga(OverriddenMRO(), 'b')

if __name__ == '__main__':
    unittest.main()
