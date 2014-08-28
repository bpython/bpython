# coding: utf8
import unittest
import sys
import os

from curtsies.formatstringarray import FormatStringTest, fsarray

from curtsies.fmtfuncs import *

from bpython import config
from bpython.curtsiesfrontend.repl import Repl
from bpython.repl import History

def setup_config():
    config_struct = config.Struct()
    config.loadini(config_struct, os.devnull)
    return config_struct

class TestCurtsiesPainting(FormatStringTest):
    def setUp(self):
        self.refresh_requests = []
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

    def test_startup(self):
        screen = fsarray([cyan('>>> '), cyan('Welcome to')])
        self.assert_paint(screen, (0, 4))

    def test_enter_text(self):
        [self.repl.add_normal_character(c) for c in '1 + 1']
        screen = fsarray([cyan('>>> ') + bold(blue('1')+cyan(' ')+
                          yellow('+') + cyan(' ') + green('1')), cyan('welcome')])
        self.assert_paint(screen, (0, 9))

    def test_run_line(self):
        try:
            orig_stdout = sys.stdout
            sys.stdout = self.repl.stdout
            [self.repl.add_normal_character(c) for c in '1 + 1']
            self.repl.on_enter()
            screen = fsarray([u'>>> 1 + 1', '2', 'Welcome to'])
            self.assert_paint_ignoring_formatting(screen, (0, 9))
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
        self.assert_paint_ignoring_formatting(screen, (0, 9))
