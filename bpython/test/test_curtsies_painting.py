# coding: utf8
from __future__ import unicode_literals
import sys
import os
from contextlib import contextmanager

from curtsies.formatstringarray import FormatStringTest, fsarray
from curtsies.fmtfuncs import cyan, bold, green, yellow, on_magenta, red

from bpython.curtsiesfrontend.events import RefreshRequestEvent
from bpython.test import mock
from bpython import config, inspection
from bpython.curtsiesfrontend.repl import Repl
from bpython.curtsiesfrontend import replpainter
from bpython.repl import History
from bpython.curtsiesfrontend.repl import INCONSISTENT_HISTORY_MSG, \
    CONTIGUITY_BROKEN_MSG
from bpython.test import FixLanguageTestCase as TestCase


def setup_config():
    config_struct = config.Struct()
    config.loadini(config_struct, os.devnull)
    return config_struct


class ClearEnviron(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mock_environ = mock.patch.dict('os.environ', {}, clear=True)
        cls.mock_environ.start()
        TestCase.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.mock_environ.stop()
        TestCase.tearDownClass()


class CurtsiesPaintingTest(FormatStringTest, ClearEnviron):
    def setUp(self):
        self.repl = Repl(config=setup_config())
        # clear history
        self.repl.rl_history = History()
        self.repl.height, self.repl.width = (5, 10)

    def assert_paint(self, screen, cursor_row_col):
        array, cursor_pos = self.repl.paint()
        self.assertFSArraysEqual(array, screen)
        self.assertEqual(cursor_pos, cursor_row_col)

    def assert_paint_ignoring_formatting(self, screen, cursor_row_col=None):
        array, cursor_pos = self.repl.paint()
        self.assertFSArraysEqualIgnoringFormatting(array, screen)
        if cursor_row_col is not None:
            self.assertEqual(cursor_pos, cursor_row_col)


class TestCurtsiesPaintingTest(CurtsiesPaintingTest):

    def test_history_is_cleared(self):
        self.assertEqual(self.repl.rl_history.entries, [''])


class TestCurtsiesPaintingSimple(CurtsiesPaintingTest):

    def test_startup(self):
        screen = fsarray([cyan('>>> '), cyan('Welcome to')])
        self.assert_paint(screen, (0, 4))

    def test_enter_text(self):
        [self.repl.add_normal_character(c) for c in '1 + 1']
        screen = fsarray([cyan('>>> ') + bold(green('1') + cyan(' ') +
                          yellow('+') + cyan(' ') + green('1')),
                          cyan('Welcome to')])
        self.assert_paint(screen, (0, 9))

    def test_run_line(self):
        try:
            orig_stdout = sys.stdout
            sys.stdout = self.repl.stdout
            [self.repl.add_normal_character(c) for c in '1 + 1']
            self.repl.on_enter(insert_into_history=False)
            screen = fsarray([u'>>> 1 + 1', '2', 'Welcome to'])
            self.assert_paint_ignoring_formatting(screen, (1, 1))
        finally:
            sys.stdout = orig_stdout

    def test_completion(self):
        self.repl.height, self.repl.width = (5, 32)
        self.repl.current_line = 'se'
        self.cursor_offset = 2
        if config.supports_box_chars():
            screen = [u'>>> se',
                      u'┌───────────────────────┐',
                      u'│ set(     setattr(     │',
                      u'└───────────────────────┘',
                      u'Welcome to bpython! Press <F1> f']
        else:
            screen = [u'>>> se',
                      u'+-----------------------+',
                      u'| set(     setattr(     |',
                      u'+-----------------------+',
                      u'Welcome to bpython! Press <F1> f']
        self.assert_paint_ignoring_formatting(screen, (0, 4))

    def test_argspec(self):
        def foo(x, y, z=10):
            "docstring!"
            pass
        argspec = inspection.getargspec('foo', foo) + [1]
        array = replpainter.formatted_argspec(argspec, 30, setup_config())
        screen = [bold(cyan(u'foo')) + cyan(':') + cyan(' ') + cyan('(') +
                  cyan('x') + yellow(',') + yellow(' ') + bold(cyan('y')) +
                  yellow(',') + yellow(' ') + cyan('z') + yellow('=') +
                  bold(cyan('10')) + yellow(')')]
        self.assertFSArraysEqual(fsarray(array), fsarray(screen))

    def test_formatted_docstring(self):
        actual = replpainter.formatted_docstring(
            'Returns the results\n\n' 'Also has side effects',
            40, config=setup_config())
        expected = fsarray(['Returns the results', '',
                            'Also has side effects'])
        self.assertFSArraysEqualIgnoringFormatting(actual, expected)

    def test_paint_lasts_events(self):
        actual = replpainter.paint_last_events(4, 100, ['a', 'b', 'c'],
                                               config=setup_config())
        if config.supports_box_chars():
            expected = fsarray(["┌─┐",
                                "│c│",
                                "│b│",
                                "└─┘"])
        else:
            expected = fsarray(["+-+",
                                "|c|",
                                "|b|",
                                "+-+"])

        self.assertFSArraysEqualIgnoringFormatting(actual, expected)


@contextmanager
def output_to_repl(repl):
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = repl.stdout, repl.stderr
        yield
    finally:
        sys.stdout, sys.stderr = old_out, old_err


class TestCurtsiesRewindRedraw(CurtsiesPaintingTest):
    def refresh(self):
        self.refresh_requests.append(RefreshRequestEvent())

    def send_refreshes(self):
        while self.refresh_requests:
            self.repl.process_event(self.refresh_requests.pop())
            _, _ = self.repl.paint()

    def enter(self, line=None):
        """Enter a line of text, avoiding autocompletion windows

        autocomplete could still happen if the entered line has
        autocompletion that would happen then, but intermediate
        stages won't happen"""
        if line is not None:
            self.repl.current_line = line
        with output_to_repl(self.repl):
            self.repl.on_enter(insert_into_history=False)
            self.assertEqual(self.repl.rl_history.entries, [''])
            self.send_refreshes()

    def undo(self):
        with output_to_repl(self.repl):
            self.repl.undo()
            self.send_refreshes()

    def setUp(self):
        self.refresh_requests = []
        self.repl = Repl(banner='', config=setup_config(),
                         request_refresh=self.refresh)
        # clear history
        self.repl.rl_history = History()
        self.repl.height, self.repl.width = (5, 32)

    def test_rewind(self):
        self.repl.current_line = '1 + 1'
        self.enter()
        screen = [u'>>> 1 + 1',
                  u'2',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (2, 4))
        self.repl.undo()
        screen = [u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (0, 4))

    def test_rewind_contiguity_loss(self):
        self.enter('1 + 1')
        self.enter('2 + 2')
        self.enter('def foo(x):')
        self.repl.current_line = '    return x + 1'
        screen = [u'>>> 1 + 1',
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> def foo(x):',
                  u'...     return x + 1']
        self.assert_paint_ignoring_formatting(screen, (5, 8))
        self.repl.scroll_offset = 1
        self.assert_paint_ignoring_formatting(screen[1:], (4, 8))
        self.undo()
        screen = [u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (3, 4))
        self.undo()
        screen = [u'2',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (1, 4))
        self.undo()
        screen = [CONTIGUITY_BROKEN_MSG[:self.repl.width],
                  u'>>> ',
                  u'',
                  u'',
                  u'',
                  u' ']  # TODO why is that there? Necessary?
        self.assert_paint_ignoring_formatting(screen, (1, 4))
        screen = [u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (0, 4))

    def test_inconsistent_history_doesnt_happen_if_onscreen(self):
        self.enter("1 + 1")
        screen = [u">>> 1 + 1",
                  u'2',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (2, 4))
        self.enter("2 + 2")
        screen = [u">>> 1 + 1",
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (4, 4))
        self.repl.display_lines[0] = self.repl.display_lines[0] * 2
        self.undo()
        screen = [u">>> 1 + 1",
                  u'2',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (2, 4))

    def test_rewind_inconsistent_history(self):
        self.enter("1 + 1")
        self.enter("2 + 2")
        self.enter("3 + 3")
        screen = [u">>> 1 + 1",
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> 3 + 3',
                  u'6',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (6, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[2:], (4, 4))
        self.repl.display_lines[0] = self.repl.display_lines[0] * 2
        self.undo()
        screen = [INCONSISTENT_HISTORY_MSG[:self.repl.width],
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ',
                  u'',
                  u' ']
        self.assert_paint_ignoring_formatting(screen, (3, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[1:-2], (2, 4))
        self.assert_paint_ignoring_formatting(screen[1:-2], (2, 4))

    def test_rewind_inconsistent_history_more_lines_same_screen(self):
        self.repl.width = 60
        sys.a = 5
        self.enter("import sys")
        self.enter("for i in range(sys.a): print(sys.a)")
        self.enter()
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [u">>> import sys",
                  u">>> for i in range(sys.a): print(sys.a)",
                  u'... ',
                  u'5',
                  u'5',
                  u'5',
                  u'5',
                  u'5',
                  u'>>> 1 + 1',
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (12, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[8:], (4, 4))
        sys.a = 6
        self.undo()
        screen = [INCONSISTENT_HISTORY_MSG[:self.repl.width],
                  u'6',
                  # everything will jump down a line - that's perfectly
                  # reasonable
                  u'>>> 1 + 1',
                  u'2',
                  u'>>> ',
                  u' ']
        self.assert_paint_ignoring_formatting(screen, (4, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[1:-1], (3, 4))

    def test_rewind_inconsistent_history_more_lines_lower_screen(self):
        self.repl.width = 60
        sys.a = 5
        self.enter("import sys")
        self.enter("for i in range(sys.a): print(sys.a)")
        self.enter()
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [u">>> import sys",
                  u">>> for i in range(sys.a): print(sys.a)",
                  u'... ',
                  u'5',
                  u'5',
                  u'5',
                  u'5',
                  u'5',
                  u'>>> 1 + 1',
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (12, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[8:], (4, 4))
        sys.a = 8
        self.undo()
        screen = [INCONSISTENT_HISTORY_MSG[:self.repl.width],
                  u'8',
                  u'8',
                  u'8',
                  u'>>> 1 + 1',
                  u'2',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen)
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[-5:])

    def test_rewind_inconsistent_history_more_lines_raise_screen(self):
        self.repl.width = 60
        sys.a = 5
        self.enter("import sys")
        self.enter("for i in range(sys.a): print(sys.a)")
        self.enter()
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [u">>> import sys",
                  u">>> for i in range(sys.a): print(sys.a)",
                  u'... ',
                  u'5',
                  u'5',
                  u'5',
                  u'5',
                  u'5',
                  u'>>> 1 + 1',
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (12, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[8:], (4, 4))
        sys.a = 1
        self.undo()
        screen = [INCONSISTENT_HISTORY_MSG[:self.repl.width],
                  u'1',
                  u'>>> 1 + 1',
                  u'2',
                  u'>>> ',
                  u' ']
        self.assert_paint_ignoring_formatting(screen)
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[1:-1])

    def test_rewind_history_not_quite_inconsistent(self):
        self.repl.width = 50
        sys.a = 5
        self.enter("for i in range(__import__('sys').a): print(i)")
        self.enter()
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [u">>> for i in range(__import__('sys').a): print(i)",
                  u'... ',
                  u'0',
                  u'1',
                  u'2',
                  u'3',
                  u'4',
                  u'>>> 1 + 1',
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (11, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[7:], (4, 4))
        sys.a = 6
        self.undo()
        screen = [u'5',
                  # everything will jump down a line - that's perfectly
                  # reasonable
                  u'>>> 1 + 1',
                  u'2',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (3, 4))

    def test_rewind_barely_consistent(self):
        self.enter("1 + 1")
        self.enter("2 + 2")
        self.enter("3 + 3")
        screen = [u">>> 1 + 1",
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> 3 + 3',
                  u'6',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (6, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[2:], (4, 4))
        self.repl.display_lines[2] = self.repl.display_lines[2] * 2
        self.undo()
        screen = [u'>>> 2 + 2',
                  u'4',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (2, 4))

    def test_clear_screen(self):
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [u">>> 1 + 1",
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ']
        self.assert_paint_ignoring_formatting(screen, (4, 4))
        self.repl.request_paint_to_clear_screen = True
        screen = [u">>> 1 + 1",
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ', u'', u'', u'', u'']
        self.assert_paint_ignoring_formatting(screen, (4, 4))

    def test_scroll_down_while_banner_visible(self):
        self.repl.status_bar.message('STATUS_BAR')
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [u">>> 1 + 1",
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ',
                  u'STATUS_BAR                      ']
        self.assert_paint_ignoring_formatting(screen, (4, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[1:], (3, 4))

    def test_clear_screen_while_banner_visible(self):
        self.repl.status_bar.message('STATUS_BAR')
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [u">>> 1 + 1",
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ',
                  u'STATUS_BAR                      ']
        self.assert_paint_ignoring_formatting(screen, (4, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[1:], (3, 4))

        self.repl.request_paint_to_clear_screen = True
        screen = [u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ',
                  u'', u'', u'',
                  u'STATUS_BAR                      ']
        self.assert_paint_ignoring_formatting(screen, (3, 4))

    def test_cursor_stays_at_bottom_of_screen(self):
        """infobox showing up during intermediate render was causing this to
        fail, #371"""
        self.repl.width = 50
        self.repl.current_line = "__import__('random').__name__"
        with output_to_repl(self.repl):
            self.repl.on_enter(insert_into_history=False)
        screen = [u">>> __import__('random').__name__",
                  u"'random'"]
        self.assert_paint_ignoring_formatting(screen)

        with output_to_repl(self.repl):
            self.repl.process_event(self.refresh_requests.pop())
        screen = [u">>> __import__('random').__name__",
                  u"'random'",
                  u""]
        self.assert_paint_ignoring_formatting(screen)

        with output_to_repl(self.repl):
            self.repl.process_event(self.refresh_requests.pop())
        screen = [u">>> __import__('random').__name__",
                  u"'random'",
                  u">>> "]
        self.assert_paint_ignoring_formatting(screen, (2, 4))

    def test_unhighlight_paren_bugs(self):
        """two previous bugs, paren did't highlight until next render
        and paren didn't unhighlight until enter"""
        self.assertEqual(self.repl.rl_history.entries, [''])
        self.enter('(')
        self.assertEqual(self.repl.rl_history.entries, [''])
        screen = [u">>> (",
                  u"... "]
        self.assertEqual(self.repl.rl_history.entries, [''])
        self.assert_paint_ignoring_formatting(screen)
        self.assertEqual(self.repl.rl_history.entries, [''])

        with output_to_repl(self.repl):
            self.assertEqual(self.repl.rl_history.entries, [''])
            self.repl.process_event(')')
            self.assertEqual(self.repl.rl_history.entries, [''])
        screen = fsarray([cyan(u">>> ")+on_magenta(bold(red('('))),
                         green(u"... ")+on_magenta(bold(red(')')))])
        self.assert_paint(screen, (1, 5))

        with output_to_repl(self.repl):
            self.repl.process_event(' ')
        screen = fsarray([cyan(u">>> ")+yellow('('),
                         green(u"... ")+yellow(')')+bold(cyan(" "))])
        self.assert_paint(screen, (1, 6))

    def send_key(self, key):
        self.repl.process_event(u'<SPACE>' if key == ' ' else key)
        self.repl.paint()  # has some side effects we need to be wary of

    def test_472(self):
        [self.send_key(c) for c in "(1, 2, 3)"]
        with output_to_repl(self.repl):
            self.send_key('\n')
            self.send_refreshes()
            self.send_key('<UP>')
            self.repl.paint()
            [self.send_key('<LEFT>') for _ in range(4)]
            self.send_key('<BACKSPACE>')
            self.send_key('4')
            self.repl.on_enter()
            self.send_refreshes()
        screen = [">>> (1, 2, 3)",
                  '(1, 2, 3)',
                  '>>> (1, 4, 3)',
                  '(1, 4, 3)',
                  '>>> ']
        self.assert_paint_ignoring_formatting(screen, (4, 4))
