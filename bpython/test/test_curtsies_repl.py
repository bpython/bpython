# coding: utf-8
from __future__ import unicode_literals

import code
import os
import sys
import tempfile
import io
from contextlib import contextmanager
from six.moves import StringIO

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from bpython.curtsiesfrontend import repl as curtsiesrepl
from bpython.curtsiesfrontend import interpreter
from bpython.curtsiesfrontend import events as bpythonevents
from bpython import autocomplete
from bpython import config
from bpython import args
from bpython._py3compat import py3
from bpython.test import (FixLanguageTestCase as TestCase, MagicIterMock, mock,
                          builtin_target)


def setup_config(conf):
    config_struct = config.Struct()
    config.loadini(config_struct, os.devnull)
    for key, value in conf.items():
        if not hasattr(config_struct, key):
            raise ValueError("%r is not a valid config attribute" % (key, ))
        setattr(config_struct, key, value)
    return config_struct


class TestCurtsiesRepl(TestCase):

    def setUp(self):
        self.repl = create_repl()

    def cfwp(self, source):
        return interpreter.code_finished_will_parse(source,
                                                    self.repl.interp.compile)

    def test_code_finished_will_parse(self):
        self.repl.buffer = ['1 + 1']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (True, True))
        self.repl.buffer = ['def foo(x):']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (False, True))
        self.repl.buffer = ['def foo(x)']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (True, False))
        self.repl.buffer = ['def foo(x):', 'return 1']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (True, False))
        self.repl.buffer = ['def foo(x):', '    return 1']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (True, True))
        self.repl.buffer = ['def foo(x):', '    return 1', '']
        self.assertTrue(self.cfwp('\n'.join(self.repl.buffer)), (True, True))

    def test_external_communication(self):
        self.repl.send_current_block_to_external_editor()
        self.repl.send_session_to_external_editor()

    @unittest.skipUnless(all(map(config.can_encode, 'å∂ßƒ')),
                         'Charset can not encode characters')
    def test_external_communication_encoding(self):
        with captured_output():
            self.repl.display_lines.append('>>> "åß∂ƒ"')
            self.repl.send_session_to_external_editor()

    def test_get_last_word(self):
        self.repl.rl_history.entries = ['1', '2 3', '4 5 6']
        self.repl._set_current_line('abcde')
        self.repl.get_last_word()
        self.assertEqual(self.repl.current_line, 'abcde6')
        self.repl.get_last_word()
        self.assertEqual(self.repl.current_line, 'abcde3')

    def test_last_word(self):
        self.assertEquals(curtsiesrepl._last_word(''), '')
        self.assertEquals(curtsiesrepl._last_word(' '), '')
        self.assertEquals(curtsiesrepl._last_word('a'), 'a')
        self.assertEquals(curtsiesrepl._last_word('a b'), 'b')

    # this is the behavior of bash - not currently implemented
    @unittest.skip
    def test_get_last_word_with_prev_line(self):
        self.repl.rl_history.entries = ['1', '2 3', '4 5 6']
        self.repl._set_current_line('abcde')
        self.repl.up_one_line()
        self.assertEqual(self.repl.current_line, '4 5 6')
        self.repl.get_last_word()
        self.assertEqual(self.repl.current_line, '4 5 63')
        self.repl.get_last_word()
        self.assertEqual(self.repl.current_line, '4 5 64')
        self.repl.up_one_line()
        self.assertEqual(self.repl.current_line, '2 3')


def mock_next(obj, return_value):
    if py3:
        obj.__next__.return_value = return_value
    else:
        obj.next.return_value = return_value


class TestCurtsiesReplTab(TestCase):

    def setUp(self):
        self.repl = create_repl()
        self.repl.matches_iter = MagicIterMock()

        def add_matches(*args, **kwargs):
            self.repl.matches_iter.matches = ['aaa', 'aab', 'aac']

        self.repl.complete = mock.Mock(side_effect=add_matches,
                                       return_value=True)

    def test_tab_with_no_matches_triggers_completion(self):
        self.repl._current_line = ' asdf'
        self.repl._cursor_offset = 5
        self.repl.matches_iter.matches = []
        self.repl.matches_iter.is_cseq.return_value = False
        self.repl.matches_iter.cur_line.return_value = (None, None)
        self.repl.on_tab()
        self.repl.complete.assert_called_once_with(tab=True)

    def test_tab_after_indentation_adds_space(self):
        self.repl._current_line = '    '
        self.repl._cursor_offset = 4
        self.repl.on_tab()
        self.assertEqual(self.repl._current_line, '        ')
        self.assertEqual(self.repl._cursor_offset, 8)

    def test_tab_at_beginning_of_line_adds_space(self):
        self.repl._current_line = ''
        self.repl._cursor_offset = 0
        self.repl.on_tab()
        self.assertEqual(self.repl._current_line, '    ')
        self.assertEqual(self.repl._cursor_offset, 4)

    def test_tab_with_no_matches_selects_first(self):
        self.repl._current_line = ' aa'
        self.repl._cursor_offset = 3
        self.repl.matches_iter.matches = []
        self.repl.matches_iter.is_cseq.return_value = False

        mock_next(self.repl.matches_iter, None)
        self.repl.matches_iter.cur_line.return_value = (None, None)
        self.repl.on_tab()
        self.repl.complete.assert_called_once_with(tab=True)
        self.repl.matches_iter.cur_line.assert_called_once_with()

    def test_tab_with_matches_selects_next_match(self):
        self.repl._current_line = ' aa'
        self.repl._cursor_offset = 3
        self.repl.complete()
        self.repl.matches_iter.is_cseq.return_value = False
        mock_next(self.repl.matches_iter, None)
        self.repl.matches_iter.cur_line.return_value = (None, None)
        self.repl.on_tab()
        self.repl.matches_iter.cur_line.assert_called_once_with()

    def test_tab_completes_common_sequence(self):
        self.repl._current_line = ' a'
        self.repl._cursor_offset = 2
        self.repl.matches_iter.matches = ['aaa', 'aab', 'aac']
        self.repl.matches_iter.is_cseq.return_value = True
        self.repl.matches_iter.substitute_cseq.return_value = (None, None)
        self.repl.on_tab()
        self.repl.matches_iter.substitute_cseq.assert_called_once_with()


class TestCurtsiesReplFilenameCompletion(TestCase):
    def setUp(self):
        self.repl = create_repl()

    def test_list_win_visible_match_selected_on_tab_multiple_options(self):
        self.repl._current_line = " './'"
        self.repl._cursor_offset = 2
        with mock.patch('bpython.autocomplete.get_completer') as m:
            m.return_value = (['./abc', './abcd', './bcd'],
                              autocomplete.FilenameCompletion())
            self.repl.update_completion()
            self.assertEqual(self.repl.list_win_visible, False)
            self.repl.on_tab()
        self.assertEqual(self.repl.current_match, './abc')
        self.assertEqual(self.repl.list_win_visible, True)

    def test_list_win_not_visible_and_cseq_if_cseq(self):
        self.repl._current_line = " './a'"
        self.repl._cursor_offset = 5
        with mock.patch('bpython.autocomplete.get_completer') as m:
            m.return_value = (['./abcd', './abce'],
                              autocomplete.FilenameCompletion())
            self.repl.update_completion()
            self.assertEqual(self.repl.list_win_visible, False)
        self.repl.on_tab()
        self.assertEqual(self.repl._current_line, " './abc'")
        self.assertEqual(self.repl.current_match, None)
        self.assertEqual(self.repl.list_win_visible, False)

    def test_list_win_not_visible_and_match_selected_if_one_option(self):
        self.repl._current_line = " './a'"
        self.repl._cursor_offset = 5
        with mock.patch('bpython.autocomplete.get_completer') as m:
            m.return_value = (['./abcd'], autocomplete.FilenameCompletion())
            self.repl.update_completion()
            self.assertEqual(self.repl.list_win_visible, False)
        self.repl.on_tab()
        self.assertEqual(self.repl._current_line, " './abcd'")
        self.assertEqual(self.repl.current_match, None)
        self.assertEqual(self.repl.list_win_visible, False)


# from http://stackoverflow.com/a/17981937/398212 - thanks @rkennedy
@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def create_repl(**kwargs):
    config = setup_config({'editor': 'true'})
    repl = curtsiesrepl.Repl(config=config, **kwargs)
    os.environ['PAGER'] = 'true'
    os.environ.pop('PYTHONSTARTUP', None)
    repl.width = 50
    repl.height = 20
    return repl


class TestFutureImports(TestCase):

    def test_repl(self):
        repl = create_repl()
        with captured_output() as (out, err):
            repl.push('from __future__ import division')
            repl.push('1 / 2')
        self.assertEqual(out.getvalue(), '0.5\n')

    def test_interactive(self):
        interp = code.InteractiveInterpreter(locals={})
        with captured_output() as (out, err):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py') as f:
                f.write('from __future__ import division\n')
                f.write('print(1/2)\n')
                f.flush()
                args.exec_code(interp, [f.name])

            repl = create_repl(interp=interp)
            repl.push('1 / 2')

        self.assertEqual(out.getvalue(), '0.5\n0.5\n')


class TestPredictedIndent(TestCase):
    def setUp(self):
        self.repl = create_repl()

    def test_simple(self):
        self.assertEqual(self.repl.predicted_indent(''), 0)
        self.assertEqual(self.repl.predicted_indent('class Foo:'), 4)
        self.assertEqual(self.repl.predicted_indent('class Foo: pass'), 0)
        self.assertEqual(self.repl.predicted_indent('def asdf():'), 4)
        self.assertEqual(self.repl.predicted_indent('def asdf(): return 7'), 0)

    @unittest.skip
    def test_complex(self):
        self.assertEqual(self.repl.predicted_indent('[a, '), 1)
        self.assertEqual(self.repl.predicted_indent('reduce(asdfasdf, '), 7)


class TestCurtsiesReevaluate(TestCase):
    def setUp(self):
        self.repl = create_repl()

    def test_variable_is_cleared(self):
        self.repl._current_line = 'b = 10'
        self.repl.on_enter()
        self.assertIn('b', self.repl.interp.locals)
        self.repl.undo()
        self.assertNotIn('b', self.repl.interp.locals)


class TestCurtsiesPagerText(TestCase):

    def setUp(self):
        self.repl = create_repl()
        self.repl.pager = self.assert_pager_gets_unicode

    def assert_pager_gets_unicode(self, text):
        self.assertIsInstance(text, type(''))

    def test_help(self):
        self.repl.pager(self.repl.help_text())

    @unittest.skipUnless(all(map(config.can_encode, 'å∂ßƒ')),
                         'Charset can not encode characters')
    def test_show_source_not_formatted(self):
        self.repl.config.highlight_show_source = False
        self.repl.get_source_of_current_name = lambda: 'source code å∂ßƒåß∂ƒ'
        self.repl.show_source()

    @unittest.skipUnless(all(map(config.can_encode, 'å∂ßƒ')),
                         'Charset can not encode characters')
    def test_show_source_formatted(self):
        self.repl.config.highlight_show_source = True
        self.repl.get_source_of_current_name = lambda: 'source code å∂ßƒåß∂ƒ'
        self.repl.show_source()


class TestCurtsiesStartup(TestCase):

    def setUp(self):
        self.repl = create_repl()

    def write_startup_file(self, fname, encoding):
        with io.open(fname, mode='wt', encoding=encoding) as f:
            f.write('# coding: ')
            f.write(encoding)
            f.write('\n')
            f.write('from __future__ import unicode_literals\n')
            f.write('a = "äöü"\n')

    def test_startup_event_utf8(self):
        with tempfile.NamedTemporaryFile() as temp:
            self.write_startup_file(temp.name, 'utf-8')
            with mock.patch.dict('os.environ', {'PYTHONSTARTUP': temp.name}):
                self.repl.process_event(bpythonevents.RunStartupFileEvent())
        self.assertIn('a', self.repl.interp.locals)

    def test_startup_event_latin1(self):
        with tempfile.NamedTemporaryFile() as temp:
            self.write_startup_file(temp.name, 'latin-1')
            with mock.patch.dict('os.environ', {'PYTHONSTARTUP': temp.name}):
                self.repl.process_event(bpythonevents.RunStartupFileEvent())
        self.assertIn('a', self.repl.interp.locals)


if __name__ == '__main__':
    unittest.main()
