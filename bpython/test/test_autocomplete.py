# encoding: utf-8

from collections import namedtuple
import inspect
import keyword
import sys

try:
    import unittest2 as unittest
except ImportError:
    import unittest

try:
    import jedi
    has_jedi = True
except ImportError:
    has_jedi = False

from bpython import autocomplete
from bpython._py3compat import py3
from bpython.test import mock

is_py34 = sys.version_info[:2] >= (3, 4)
if is_py34:
    glob_function = 'glob.iglob'
else:
    glob_function = 'glob.glob'


class TestSafeEval(unittest.TestCase):
    def test_catches_syntax_error(self):
        with self.assertRaises(autocomplete.EvaluationError):
            autocomplete.safe_eval('1re', {})


class TestFormatters(unittest.TestCase):

    def test_filename(self):
        completer = autocomplete.FilenameCompletion()
        last_part_of_filename = completer.format
        self.assertEqual(last_part_of_filename('abc'), 'abc')
        self.assertEqual(last_part_of_filename('abc/'), 'abc/')
        self.assertEqual(last_part_of_filename('abc/efg'), 'efg')
        self.assertEqual(last_part_of_filename('abc/efg/'), 'efg/')
        self.assertEqual(last_part_of_filename('/abc'), 'abc')
        self.assertEqual(last_part_of_filename('ab.c/e.f.g/'), 'e.f.g/')

    def test_attribute(self):
        self.assertEqual(autocomplete.after_last_dot('abc.edf'), 'edf')


def completer(matches):
    mock_completer = autocomplete.BaseCompletionType()
    mock_completer.matches = mock.Mock(return_value=matches)
    return mock_completer


class TestGetCompleter(unittest.TestCase):

    def test_no_completers(self):
        self.assertTupleEqual(autocomplete.get_completer([], 0, ''),
                              ([], None))

    def test_one_completer_without_matches_returns_empty_list_and_none(self):
        a = completer([])
        self.assertTupleEqual(autocomplete.get_completer([a], 0, ''),
                              ([], None))

    def test_one_completer_returns_matches_and_completer(self):
        a = completer(['a'])
        self.assertTupleEqual(autocomplete.get_completer([a], 0, ''),
                              (['a'], a))

    def test_two_completers_with_matches_returns_first_matches(self):
        a = completer(['a'])
        b = completer(['b'])
        self.assertEqual(autocomplete.get_completer([a, b], 0, ''), (['a'], a))

    def test_first_non_none_completer_matches_are_returned(self):
        a = completer([])
        b = completer(['a'])
        self.assertEqual(autocomplete.get_completer([a, b], 0, ''), ([], None))

    def test_only_completer_returns_None(self):
        a = completer(None)
        self.assertEqual(autocomplete.get_completer([a], 0, ''), ([], None))

    def test_first_completer_returns_None(self):
        a = completer(None)
        b = completer(['a'])
        self.assertEqual(autocomplete.get_completer([a, b], 0, ''), (['a'], b))


class TestCumulativeCompleter(unittest.TestCase):

    def completer(self, matches, ):
        mock_completer = autocomplete.BaseCompletionType()
        mock_completer.matches = mock.Mock(return_value=matches)
        return mock_completer

    def test_no_completers_fails(self):
        with self.assertRaises(ValueError):
            autocomplete.CumulativeCompleter([])

    def test_one_empty_completer_returns_empty(self):
        a = self.completer([])
        cumulative = autocomplete.CumulativeCompleter([a])
        self.assertEqual(cumulative.matches(3, 'abc'), set())

    def test_one_none_completer_returns_empty(self):
        a = self.completer(None)
        cumulative = autocomplete.CumulativeCompleter([a])
        self.assertEqual(cumulative.matches(3, 'abc'), set())

    def test_two_completers_get_both(self):
        a = self.completer(['a'])
        b = self.completer(['b'])
        cumulative = autocomplete.CumulativeCompleter([a, b])
        self.assertEqual(cumulative.matches(3, 'abc'), set(['a', 'b']))


class TestFilenameCompletion(unittest.TestCase):

    def setUp(self):
        self.completer = autocomplete.FilenameCompletion()

    def test_locate_fails_when_not_in_string(self):
        self.assertEqual(self.completer.locate(4, "abcd"), None)

    def test_locate_succeeds_when_in_string(self):
        self.assertEqual(self.completer.locate(4, "a'bc'd"), (2, 4, 'bc'))

    def test_issue_491(self):
        self.assertNotEqual(self.completer.matches(9, '"a[a.l-1]'), None)

    @mock.patch(glob_function, new=lambda text: [])
    def test_match_returns_none_if_not_in_string(self):
        self.assertEqual(self.completer.matches(2, 'abcd'), None)

    @mock.patch(glob_function, new=lambda text: [])
    def test_match_returns_empty_list_when_no_files(self):
        self.assertEqual(self.completer.matches(2, '"a'), set())

    @mock.patch(glob_function, new=lambda text: ['abcde', 'aaaaa'])
    @mock.patch('os.path.expanduser', new=lambda text: text)
    @mock.patch('os.path.isdir', new=lambda text: False)
    @mock.patch('os.path.sep', new='/')
    def test_match_returns_files_when_files_exist(self):
        self.assertEqual(sorted(self.completer.matches(2, '"x')),
                         ['aaaaa', 'abcde'])

    @mock.patch(glob_function, new=lambda text: ['abcde', 'aaaaa'])
    @mock.patch('os.path.expanduser', new=lambda text: text)
    @mock.patch('os.path.isdir', new=lambda text: True)
    @mock.patch('os.path.sep', new='/')
    def test_match_returns_dirs_when_dirs_exist(self):
        self.assertEqual(sorted(self.completer.matches(2, '"x')),
                         ['aaaaa/', 'abcde/'])

    @mock.patch(glob_function,
                new=lambda text: ['/expand/ed/abcde', '/expand/ed/aaaaa'])
    @mock.patch('os.path.expanduser',
                new=lambda text: text.replace('~', '/expand/ed'))
    @mock.patch('os.path.isdir', new=lambda text: False)
    @mock.patch('os.path.sep', new='/')
    def test_tilde_stays_pretty(self):
        self.assertEqual(sorted(self.completer.matches(4, '"~/a')),
                         ['~/aaaaa', '~/abcde'])

    @mock.patch('os.path.sep', new='/')
    def test_formatting_takes_just_last_part(self):
        self.assertEqual(self.completer.format('/hello/there/'), 'there/')
        self.assertEqual(self.completer.format('/hello/there'), 'there')


class MockNumPy(object):
    """This is a mock numpy object that raises an error when there is an atempt
    to convert it to a boolean."""

    def __nonzero__(self):
        raise ValueError("The truth value of an array with more than one "
                         "element is ambiguous. Use a.any() or a.all()")


class TestDictKeyCompletion(unittest.TestCase):

    def test_set_of_keys_returned_when_matches_found(self):
        com = autocomplete.DictKeyCompletion()
        local = {'d': {"ab": 1, "cd": 2}}
        self.assertSetEqual(com.matches(2, "d[", locals_=local),
                            set(["'ab']", "'cd']"]))

    def test_empty_set_returned_when_eval_error(self):
        com = autocomplete.DictKeyCompletion()
        local = {'e': {"ab": 1, "cd": 2}}
        self.assertSetEqual(com.matches(2, "d[", locals_=local), set())

    def test_empty_set_returned_when_not_dict_type(self):
        com = autocomplete.DictKeyCompletion()
        local = {'l': ["ab", "cd"]}
        self.assertSetEqual(com.matches(2, "l[", locals_=local), set())

    def test_obj_that_does_not_allow_conversion_to_bool(self):
        com = autocomplete.DictKeyCompletion()
        local = {'mNumPy': MockNumPy()}
        self.assertSetEqual(com.matches(7, "mNumPy[", locals_=local), set())


class Foo(object):
    a = 10

    def __init__(self):
        self.b = 20

    def method(self, x):
        pass


class OldStyleFoo:
    a = 10

    def __init__(self):
        self.b = 20

    def method(self, x):
        pass


skip_old_style = unittest.skipIf(py3,
                                 'In Python 3 there are no old style classes')


class TestAttrCompletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.com = autocomplete.AttrCompletion()

    def test_att_matches_found_on_instance(self):
        self.assertSetEqual(self.com.matches(2, 'a.', locals_={'a': Foo()}),
                            set(['a.method', 'a.a', 'a.b']))

    @skip_old_style
    def test_att_matches_found_on_old_style_instance(self):
        self.assertSetEqual(self.com.matches(2, 'a.',
                                             locals_={'a': OldStyleFoo()}),
                            set(['a.method', 'a.a', 'a.b']))
        self.assertIn(u'a.__dict__',
                      self.com.matches(4, 'a.__', locals_={'a': OldStyleFoo()}))

    @skip_old_style
    def test_att_matches_found_on_old_style_class_object(self):
        self.assertIn(u'A.__dict__',
                      self.com.matches(4, 'A.__', locals_={'A': OldStyleFoo}))

    @skip_old_style
    def test_issue536(self):
        class OldStyleWithBrokenGetAttr:
            def __getattr__(self, attr):
                raise Exception()

        locals_ = {'a': OldStyleWithBrokenGetAttr()}
        self.assertIn(u'a.__module__',
                      self.com.matches(4, 'a.__', locals_=locals_))


class TestArrayItemCompletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.com = autocomplete.ArrayItemMembersCompletion()

    def test_att_matches_found_on_instance(self):
        self.assertSetEqual(self.com.matches(5, 'a[0].', locals_={'a': [Foo()]}),
                            set(['a[0].method', 'a[0].a', 'a[0].b']))

    @skip_old_style
    def test_att_matches_found_on_old_style_instance(self):
        self.assertSetEqual(self.com.matches(5, 'a[0].',
                                             locals_={'a': [OldStyleFoo()]}),
                            set(['a[0].method', 'a[0].a', 'a[0].b']))


class TestMagicMethodCompletion(unittest.TestCase):

    def test_magic_methods_complete_after_double_underscores(self):
        com = autocomplete.MagicMethodCompletion()
        block = "class Something(object)\n    def __"
        self.assertSetEqual(com.matches(10, '    def __', current_block=block),
                            set(autocomplete.MAGIC_METHODS))


Comp = namedtuple('Completion', ['name', 'complete'])


@unittest.skipUnless(has_jedi, "jedi required")
class TestMultilineJediCompletion(unittest.TestCase):

    def test_returns_none_with_single_line(self):
        com = autocomplete.MultilineJediCompletion()
        self.assertEqual(com.matches(2, 'Va', current_block='Va', history=[]),
                         None)

    def test_returns_non_with_blank_second_line(self):
        com = autocomplete.MultilineJediCompletion()
        self.assertEqual(com.matches(0, '', current_block='class Foo():\n',
                                     history=['class Foo():']), None)

    def matches_from_completions(self, cursor, line, block, history,
                                 completions):
        with mock.patch('bpython.autocomplete.jedi.Script') as Script:
            script = Script.return_value
            script.completions.return_value = completions
            com = autocomplete.MultilineJediCompletion()
            return com.matches(cursor, line, current_block=block,
                               history=history)

    def test_completions_starting_with_different_letters(self):
        matches = self.matches_from_completions(
            2, ' a', 'class Foo:\n a', ['adsf'],
            [Comp('Abc', 'bc'), Comp('Cbc', 'bc')])
        self.assertEqual(matches, None)

    def test_completions_starting_with_different_cases(self):
        matches = self.matches_from_completions(
            2, ' a', 'class Foo:\n a', ['adsf'],
            [Comp('Abc', 'bc'), Comp('ade', 'de')])
        self.assertSetEqual(matches, set(['ade']))

    @unittest.skipUnless(is_py34, 'asyncio required')
    def test_issue_544(self):
        com = autocomplete.MultilineJediCompletion()
        code = '@asyncio.coroutine\ndef'
        history = ('import asyncio', '@asyncio.coroutin')
        com.matches(3, 'def', current_block=code, history=history)


class TestGlobalCompletion(unittest.TestCase):

    def setUp(self):
        self.com = autocomplete.GlobalCompletion()

    def test_function(self):
        def function():
            pass

        self.assertEqual(self.com.matches(8, 'function',
                                          locals_={'function': function}),
                         set(('function(', )))

    def test_completions_are_unicode(self):
        for m in self.com.matches(1, 'a', locals_={'abc': 10}):
            self.assertIsInstance(m, type(u''))

    @unittest.skipIf(py3, "in Python 3 invalid identifiers are passed through")
    def test_ignores_nonascii_encodable(self):
        self.assertSetEqual(self.com.matches(3, 'abc', locals_={'abcß': 10}),
                            set())

    def test_mock_kwlist(self):
        with mock.patch.object(keyword, 'kwlist', new=['abcd']):
            self.assertSetEqual(self.com.matches(3, 'abc', locals_={}), set())

    def test_mock_kwlist_non_ascii(self):
        with mock.patch.object(keyword, 'kwlist', new=['abcß']):
            self.assertSetEqual(self.com.matches(3, 'abc', locals_={}), set())


class TestParameterNameCompletion(unittest.TestCase):
    def test_set_of_params_returns_when_matches_found(self):
        def func(apple, apricot, banana, carrot):
            pass
        if py3:
            argspec = list(inspect.getfullargspec(func))
        else:
            argspec = list(inspect.getargspec(func))

        argspec = ["func", argspec, False]
        com = autocomplete.ParameterNameCompletion()
        self.assertSetEqual(com.matches(1, "a", argspec=argspec),
                            set(['apple=', 'apricot=']))
        self.assertSetEqual(com.matches(2, "ba", argspec=argspec),
                            set(['banana=']))
        self.assertSetEqual(com.matches(3, "car", argspec=argspec),
                            set(['carrot=']))
