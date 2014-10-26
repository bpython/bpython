# coding: utf8
import sys
import os
from contextlib import contextmanager

try:
    from unittest import skip
except ImportError:
    def skip(f):
        return lambda self: None

from curtsies.formatstringarray import FormatStringTest, fsarray
from curtsies.fmtfuncs import *
from bpython.curtsiesfrontend.events import RefreshRequestEvent

from bpython import config
from bpython.curtsiesfrontend.repl import Repl
from bpython.repl import History
from bpython.curtsiesfrontend.repl import INCONSISTENT_HISTORY_MSG, CONTIGUITY_BROKEN_MSG

def setup_config():
    config_struct = config.Struct()
    config.loadini(config_struct, os.devnull)
    return config_struct

class TestCurtsiesPainting(FormatStringTest):
    def setUp(self):
        self.repl = Repl(config=setup_config())
        self.repl.rl_history = History() # clear history
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

class TestCurtsiesPaintingTest(TestCurtsiesPainting):

    def test_history_is_cleared(self):
        self.assertEqual(self.repl.rl_history.entries, [''])

class TestCurtsiesPaintingSimple(TestCurtsiesPainting):

    def test_startup(self):
        screen = fsarray([cyan('>>> '), cyan('Welcome to')])
        self.assert_paint(screen, (0, 4))

    def test_enter_text(self):
        [self.repl.add_normal_character(c) for c in '1 + 1']
        screen = fsarray([cyan('>>> ') + bold(green('1')+cyan(' ')+
                          yellow('+') + cyan(' ') + green('1')), cyan('Welcome to')])
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
        screen = [u'>>> se',
                  u'┌───────────────────────┐',
                  u'│ set(     setattr(     │',
                  u'└───────────────────────┘',
                  u'Welcome to bpython! Press <F1> f']
        self.assert_paint_ignoring_formatting(screen, (0, 4))

@contextmanager
def output_to_repl(repl):
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = repl.stdout, repl.stderr
        yield
    finally:
        sys.stdout, sys.stderr = old_out, old_err

class TestCurtsiesRewindRedraw(TestCurtsiesPainting):
    def refresh(self):
        self.refresh_requests.append(RefreshRequestEvent())

    def send_refreshes(self):
        while self.refresh_requests:
            self.repl.process_event(self.refresh_requests.pop())

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
        self.repl = Repl(banner='', config=setup_config(), request_refresh=self.refresh)
        self.repl.rl_history = History() # clear history
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
                  u' '] #TODO why is that there? Necessary?
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
                  u'>>> 1 + 1', # everything will jump down a line - that's perfectly reasonable
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
                  u'>>> 1 + 1', # everything will jump down a line - that's perfectly reasonable
                  u'2',
                  u'>>> ',]
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
        """infobox showing up during intermediate render was causing this to fail, #371"""
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
