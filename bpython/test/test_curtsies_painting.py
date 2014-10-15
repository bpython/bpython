# coding: utf8
import unittest
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
from curtsies.events import RefreshRequestEvent

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

    def assert_paint_ignoring_formatting(self, screen, cursor_row_col):
        array, cursor_pos = self.repl.paint()
        self.assertFSArraysEqualIgnoringFormatting(array, screen)
        self.assertEqual(cursor_pos, cursor_row_col)

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
            self.repl.on_enter()
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
                  u'',
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
    def refresh(self, when='now'):
        self.refresh_requests.append(RefreshRequestEvent(when=when))

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
            self.repl.on_enter()
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

    @skip('wrong message')
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

    @skip('why is everything moved up?')
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
                  u'']
        self.assert_paint_ignoring_formatting(screen, (5, 4))

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

    @skip('the screen moved up again!')
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
        screen = [u">>> 1 + 1",
                  u'2',
                  u'>>> 2 + 2',
                  u'4',
                  u'>>> ',
                  u'', u'', u'',
                  u'STATUS_BAR                      ']
        self.assert_paint_ignoring_formatting(screen, (0, 4))
