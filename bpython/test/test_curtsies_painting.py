# coding: utf8

from __future__ import unicode_literals
import itertools
import os
import pydoc
import string
import sys
from contextlib import contextmanager

from curtsies.formatstringarray import FormatStringTest, fsarray
from curtsies.fmtfuncs import cyan, bold, green, yellow, on_magenta, red

from bpython.curtsiesfrontend.events import RefreshRequestEvent
from bpython.test import mock
from bpython import config, inspection
from bpython.curtsiesfrontend.repl import BaseRepl
from bpython.curtsiesfrontend import replpainter
from bpython.curtsiesfrontend.repl import (
    INCONSISTENT_HISTORY_MSG,
    CONTIGUITY_BROKEN_MSG,
)
from bpython.test import FixLanguageTestCase as TestCase, TEST_CONFIG


def setup_config():
    config_struct = config.Struct()
    config.loadini(config_struct, TEST_CONFIG)
    config_struct.cli_suggestion_width = 1
    return config_struct


class ClearEnviron(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_environ = mock.patch.dict("os.environ", {}, clear=True)
        cls.mock_environ.start()
        TestCase.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.mock_environ.stop()
        TestCase.tearDownClass()


class CurtsiesPaintingTest(FormatStringTest, ClearEnviron):
    def setUp(self):
        class TestRepl(BaseRepl):
            def _request_refresh(inner_self):
                pass

        self.repl = TestRepl(config=setup_config())
        self.repl.height, self.repl.width = (5, 10)

    @property
    def locals(self):
        return self.repl.coderunner.interp.locals

    def assert_paint(self, screen, cursor_row_col):
        array, cursor_pos = self.repl.paint()
        self.assertFSArraysEqual(array, screen)
        self.assertEqual(cursor_pos, cursor_row_col)

    def assert_paint_ignoring_formatting(
        self, screen, cursor_row_col=None, **paint_kwargs
    ):
        array, cursor_pos = self.repl.paint(**paint_kwargs)
        self.assertFSArraysEqualIgnoringFormatting(array, screen)
        if cursor_row_col is not None:
            self.assertEqual(cursor_pos, cursor_row_col)


class TestCurtsiesPaintingTest(CurtsiesPaintingTest):
    def test_history_is_cleared(self):
        self.assertEqual(self.repl.rl_history.entries, [""])


class TestCurtsiesPaintingSimple(CurtsiesPaintingTest):
    def test_startup(self):
        screen = fsarray([cyan(">>> "), cyan("Welcome to")])
        self.assert_paint(screen, (0, 4))

    def test_enter_text(self):
        [self.repl.add_normal_character(c) for c in "1 + 1"]
        screen = fsarray(
            [
                cyan(">>> ")
                + bold(
                    green("1")
                    + cyan(" ")
                    + yellow("+")
                    + cyan(" ")
                    + green("1")
                ),
                cyan("Welcome to"),
            ]
        )
        self.assert_paint(screen, (0, 9))

    def test_run_line(self):
        try:
            orig_stdout = sys.stdout
            sys.stdout = self.repl.stdout
            [self.repl.add_normal_character(c) for c in "1 + 1"]
            self.repl.on_enter(new_code=False)
            screen = fsarray([">>> 1 + 1", "2", "Welcome to"])
            self.assert_paint_ignoring_formatting(screen, (1, 1))
        finally:
            sys.stdout = orig_stdout

    def test_completion(self):
        self.repl.height, self.repl.width = (5, 32)
        self.repl.current_line = "an"
        self.cursor_offset = 2
        if config.supports_box_chars():
            screen = [
                ">>> an",
                "┌──────────────────────────────┐",
                "│ and  any(                    │",
                "└──────────────────────────────┘",
                "Welcome to bpython! Press <F1> f",
            ]
        else:
            screen = [
                ">>> an",
                "+------------------------------+",
                "| and  any(                    |",
                "+------------------------------+",
                "Welcome to bpython! Press <F1> f",
            ]
        self.assert_paint_ignoring_formatting(screen, (0, 4))

    def test_argspec(self):
        def foo(x, y, z=10):
            "docstring!"
            pass

        argspec = inspection.getfuncprops("foo", foo)
        array = replpainter.formatted_argspec(argspec, 1, 30, setup_config())
        screen = [
            bold(cyan("foo"))
            + cyan(":")
            + cyan(" ")
            + cyan("(")
            + cyan("x")
            + yellow(",")
            + yellow(" ")
            + bold(cyan("y"))
            + yellow(",")
            + yellow(" ")
            + cyan("z")
            + yellow("=")
            + bold(cyan("10"))
            + yellow(")")
        ]
        self.assertFSArraysEqual(fsarray(array), fsarray(screen))

    def test_formatted_docstring(self):
        actual = replpainter.formatted_docstring(
            "Returns the results\n\n" "Also has side effects",
            40,
            config=setup_config(),
        )
        expected = fsarray(["Returns the results", "", "Also has side effects"])
        self.assertFSArraysEqualIgnoringFormatting(actual, expected)

    def test_unicode_docstrings(self):
        "A bit of a special case in Python 2"
        # issue 653

        def foo():
            "åß∂ƒ"

        actual = replpainter.formatted_docstring(
            foo.__doc__, 40, config=setup_config()
        )
        expected = fsarray(["åß∂ƒ"])
        self.assertFSArraysEqualIgnoringFormatting(actual, expected)

    def test_nonsense_docstrings(self):
        for docstring in [
            123,
            {},
            [],
        ]:
            try:
                replpainter.formatted_docstring(
                    docstring, 40, config=setup_config()
                )
            except Exception:
                self.fail("bad docstring caused crash: {!r}".format(docstring))

    def test_weird_boto_docstrings(self):
        # Boto does something like this.
        # botocore: botocore/docs/docstring.py
        class WeirdDocstring(str):
            # a mighty hack. See botocore/docs/docstring.py
            def expandtabs(self, tabsize=8):
                return "asdfåß∂ƒ".expandtabs(tabsize)

        def foo():
            pass

        foo.__doc__ = WeirdDocstring()
        wd = pydoc.getdoc(foo)
        actual = replpainter.formatted_docstring(wd, 40, config=setup_config())
        expected = fsarray(["asdfåß∂ƒ"])
        self.assertFSArraysEqualIgnoringFormatting(actual, expected)

    def test_paint_lasts_events(self):
        actual = replpainter.paint_last_events(
            4, 100, ["a", "b", "c"], config=setup_config()
        )
        if config.supports_box_chars():
            expected = fsarray(["┌─┐", "│c│", "│b│", "└─┘"])
        else:
            expected = fsarray(["+-+", "|c|", "|b|", "+-+"])

        self.assertFSArraysEqualIgnoringFormatting(actual, expected)


@contextmanager
def output_to_repl(repl):
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = repl.stdout, repl.stderr
        yield
    finally:
        sys.stdout, sys.stderr = old_out, old_err


class HigherLevelCurtsiesPaintingTest(CurtsiesPaintingTest):
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
            self.repl._set_cursor_offset(len(line), update_completion=False)
            self.repl.current_line = line
        with output_to_repl(self.repl):
            self.repl.on_enter(new_code=False)
            self.assertEqual(self.repl.rl_history.entries, [""])
            self.send_refreshes()

    def undo(self):
        with output_to_repl(self.repl):
            self.repl.undo()
            self.send_refreshes()

    def setUp(self):
        self.refresh_requests = []

        class TestRepl(BaseRepl):
            def _request_refresh(inner_self):
                self.refresh()

        self.repl = TestRepl(banner="", config=setup_config())
        self.repl.height, self.repl.width = (5, 32)

    def send_key(self, key):
        self.repl.process_event("<SPACE>" if key == " " else key)
        self.repl.paint()  # has some side effects we need to be wary of


class TestCurtsiesRewindRedraw(HigherLevelCurtsiesPaintingTest):
    def test_rewind(self):
        self.repl.current_line = "1 + 1"
        self.enter()
        screen = [">>> 1 + 1", "2", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (2, 4))
        self.repl.undo()
        screen = [">>> "]
        self.assert_paint_ignoring_formatting(screen, (0, 4))

    def test_rewind_contiguity_loss(self):
        self.enter("1 + 1")
        self.enter("2 + 2")
        self.enter("def foo(x):")
        self.repl.current_line = "    return x + 1"
        screen = [
            ">>> 1 + 1",
            "2",
            ">>> 2 + 2",
            "4",
            ">>> def foo(x):",
            "...     return x + 1",
        ]
        self.assert_paint_ignoring_formatting(screen, (5, 8))
        self.repl.scroll_offset = 1
        self.assert_paint_ignoring_formatting(screen[1:], (4, 8))
        self.undo()
        screen = ["2", ">>> 2 + 2", "4", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (3, 4))
        self.undo()
        screen = ["2", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (1, 4))
        self.undo()
        screen = [
            CONTIGUITY_BROKEN_MSG[: self.repl.width],
            ">>> ",
            "",
            "",
            "",
            " ",
        ]  # TODO why is that there? Necessary?
        self.assert_paint_ignoring_formatting(screen, (1, 4))
        screen = [">>> "]
        self.assert_paint_ignoring_formatting(screen, (0, 4))

    def test_inconsistent_history_doesnt_happen_if_onscreen(self):
        self.enter("1 + 1")
        screen = [">>> 1 + 1", "2", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (2, 4))
        self.enter("2 + 2")
        screen = [">>> 1 + 1", "2", ">>> 2 + 2", "4", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (4, 4))
        self.repl.display_lines[0] = self.repl.display_lines[0] * 2
        self.undo()
        screen = [">>> 1 + 1", "2", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (2, 4))

    def test_rewind_inconsistent_history(self):
        self.enter("1 + 1")
        self.enter("2 + 2")
        self.enter("3 + 3")
        screen = [">>> 1 + 1", "2", ">>> 2 + 2", "4", ">>> 3 + 3", "6", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (6, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[2:], (4, 4))
        self.repl.display_lines[0] = self.repl.display_lines[0] * 2
        self.undo()
        screen = [
            INCONSISTENT_HISTORY_MSG[: self.repl.width],
            ">>> 2 + 2",
            "4",
            ">>> ",
            "",
            " ",
        ]
        self.assert_paint_ignoring_formatting(screen, (3, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[1:-2], (2, 4))
        self.assert_paint_ignoring_formatting(screen[1:-2], (2, 4))

    def test_rewind_inconsistent_history_more_lines_same_screen(self):
        self.repl.width = 60
        sys.a = 5
        self.enter("import sys")
        self.enter("for i in range(sys.a):")
        self.enter("    print(sys.a)")
        self.enter("")
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [
            ">>> import sys",
            ">>> for i in range(sys.a):",
            "...     print(sys.a)",
            "... ",
            "5",
            "5",
            "5",
            "5",
            "5",
            ">>> 1 + 1",
            "2",
            ">>> 2 + 2",
            "4",
            ">>> ",
        ]
        self.assert_paint_ignoring_formatting(screen, (13, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[9:], (4, 4))
        sys.a = 6
        self.undo()
        screen = [
            INCONSISTENT_HISTORY_MSG[: self.repl.width],
            "6",
            # everything will jump down a line - that's perfectly
            # reasonable
            ">>> 1 + 1",
            "2",
            ">>> ",
            " ",
        ]
        self.assert_paint_ignoring_formatting(screen, (4, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[1:-1], (3, 4))

    def test_rewind_inconsistent_history_more_lines_lower_screen(self):
        self.repl.width = 60
        sys.a = 5
        self.enter("import sys")
        self.enter("for i in range(sys.a):")
        self.enter("    print(sys.a)")
        self.enter("")
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [
            ">>> import sys",
            ">>> for i in range(sys.a):",
            "...     print(sys.a)",
            "... ",
            "5",
            "5",
            "5",
            "5",
            "5",
            ">>> 1 + 1",
            "2",
            ">>> 2 + 2",
            "4",
            ">>> ",
        ]
        self.assert_paint_ignoring_formatting(screen, (13, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[9:], (4, 4))
        sys.a = 8
        self.undo()
        screen = [
            INCONSISTENT_HISTORY_MSG[: self.repl.width],
            "8",
            "8",
            "8",
            ">>> 1 + 1",
            "2",
            ">>> ",
        ]
        self.assert_paint_ignoring_formatting(screen)
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[-5:])

    def test_rewind_inconsistent_history_more_lines_raise_screen(self):
        self.repl.width = 60
        sys.a = 5
        self.enter("import sys")
        self.enter("for i in range(sys.a):")
        self.enter("    print(sys.a)")
        self.enter("")
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [
            ">>> import sys",
            ">>> for i in range(sys.a):",
            "...     print(sys.a)",
            "... ",
            "5",
            "5",
            "5",
            "5",
            "5",
            ">>> 1 + 1",
            "2",
            ">>> 2 + 2",
            "4",
            ">>> ",
        ]
        self.assert_paint_ignoring_formatting(screen, (13, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[9:], (4, 4))
        sys.a = 1
        self.undo()
        screen = [
            INCONSISTENT_HISTORY_MSG[: self.repl.width],
            "1",
            ">>> 1 + 1",
            "2",
            ">>> ",
            " ",
        ]
        self.assert_paint_ignoring_formatting(screen)
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[1:-1])

    def test_rewind_history_not_quite_inconsistent(self):
        self.repl.width = 50
        sys.a = 5
        self.enter("for i in range(__import__('sys').a):")
        self.enter("    print(i)")
        self.enter("")
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [
            ">>> for i in range(__import__('sys').a):",
            "...     print(i)",
            "... ",
            "0",
            "1",
            "2",
            "3",
            "4",
            ">>> 1 + 1",
            "2",
            ">>> 2 + 2",
            "4",
            ">>> ",
        ]
        self.assert_paint_ignoring_formatting(screen, (12, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[8:], (4, 4))
        sys.a = 6
        self.undo()
        screen = [
            "5",
            # everything will jump down a line - that's perfectly
            # reasonable
            ">>> 1 + 1",
            "2",
            ">>> ",
        ]
        self.assert_paint_ignoring_formatting(screen, (3, 4))

    def test_rewind_barely_consistent(self):
        self.enter("1 + 1")
        self.enter("2 + 2")
        self.enter("3 + 3")
        screen = [">>> 1 + 1", "2", ">>> 2 + 2", "4", ">>> 3 + 3", "6", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (6, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[2:], (4, 4))
        self.repl.display_lines[2] = self.repl.display_lines[2] * 2
        self.undo()
        screen = [">>> 2 + 2", "4", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (2, 4))

    def test_clear_screen(self):
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [">>> 1 + 1", "2", ">>> 2 + 2", "4", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (4, 4))
        self.repl.request_paint_to_clear_screen = True
        screen = [">>> 1 + 1", "2", ">>> 2 + 2", "4", ">>> ", "", "", "", ""]
        self.assert_paint_ignoring_formatting(screen, (4, 4))

    def test_scroll_down_while_banner_visible(self):
        self.repl.status_bar.message("STATUS_BAR")
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [
            ">>> 1 + 1",
            "2",
            ">>> 2 + 2",
            "4",
            ">>> ",
            "STATUS_BAR                      ",
        ]
        self.assert_paint_ignoring_formatting(screen, (4, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[1:], (3, 4))

    def test_clear_screen_while_banner_visible(self):
        self.repl.status_bar.message("STATUS_BAR")
        self.enter("1 + 1")
        self.enter("2 + 2")
        screen = [
            ">>> 1 + 1",
            "2",
            ">>> 2 + 2",
            "4",
            ">>> ",
            "STATUS_BAR                      ",
        ]
        self.assert_paint_ignoring_formatting(screen, (4, 4))
        self.repl.scroll_offset += len(screen) - self.repl.height
        self.assert_paint_ignoring_formatting(screen[1:], (3, 4))

        self.repl.request_paint_to_clear_screen = True
        screen = [
            "2",
            ">>> 2 + 2",
            "4",
            ">>> ",
            "",
            "",
            "",
            "STATUS_BAR                      ",
        ]
        self.assert_paint_ignoring_formatting(screen, (3, 4))

    def test_cursor_stays_at_bottom_of_screen(self):
        """infobox showing up during intermediate render was causing this to
        fail, #371"""
        self.repl.width = 50
        self.repl.current_line = "__import__('random').__name__"
        with output_to_repl(self.repl):
            self.repl.on_enter(new_code=False)
        screen = [">>> __import__('random').__name__", "'random'"]
        self.assert_paint_ignoring_formatting(screen)

        with output_to_repl(self.repl):
            self.repl.process_event(self.refresh_requests.pop())
        screen = [">>> __import__('random').__name__", "'random'", ""]
        self.assert_paint_ignoring_formatting(screen)

        with output_to_repl(self.repl):
            self.repl.process_event(self.refresh_requests.pop())
        screen = [">>> __import__('random').__name__", "'random'", ">>> "]
        self.assert_paint_ignoring_formatting(screen, (2, 4))

    def test_unhighlight_paren_bugs(self):
        """two previous bugs, parent didn't highlight until next render
        and paren didn't unhighlight until enter"""
        self.assertEqual(self.repl.rl_history.entries, [""])
        self.enter("(")
        self.assertEqual(self.repl.rl_history.entries, [""])
        screen = [">>> (", "... "]
        self.assertEqual(self.repl.rl_history.entries, [""])
        self.assert_paint_ignoring_formatting(screen)
        self.assertEqual(self.repl.rl_history.entries, [""])

        with output_to_repl(self.repl):
            self.assertEqual(self.repl.rl_history.entries, [""])
            self.repl.process_event(")")
            self.assertEqual(self.repl.rl_history.entries, [""])
        screen = fsarray(
            [
                cyan(">>> ") + on_magenta(bold(red("("))),
                green("... ") + on_magenta(bold(red(")"))),
            ]
        )
        self.assert_paint(screen, (1, 5))

        with output_to_repl(self.repl):
            self.repl.process_event(" ")
        screen = fsarray(
            [
                cyan(">>> ") + yellow("("),
                green("... ") + yellow(")") + bold(cyan(" ")),
            ]
        )
        self.assert_paint(screen, (1, 6))

    def test_472(self):
        [self.send_key(c) for c in "(1, 2, 3)"]
        with output_to_repl(self.repl):
            self.send_key("\n")
            self.send_refreshes()
            self.send_key("<UP>")
            self.repl.paint()
            [self.send_key("<LEFT>") for _ in range(4)]
            self.send_key("<BACKSPACE>")
            self.send_key("4")
            self.repl.on_enter()
            self.send_refreshes()
        screen = [
            ">>> (1, 2, 3)",
            "(1, 2, 3)",
            ">>> (1, 4, 3)",
            "(1, 4, 3)",
            ">>> ",
        ]
        self.assert_paint_ignoring_formatting(screen, (4, 4))


def completion_target(num_names, chars_in_first_name=1):
    class Class(object):
        pass

    if chars_in_first_name < 1:
        raise ValueError("need at least one char in each name")
    elif chars_in_first_name == 1 and num_names > len(string.ascii_letters):
        raise ValueError("need more chars to make so many names")

    names = gen_names()
    if num_names > 0:
        setattr(Class, "a" * chars_in_first_name, 1)
        next(names)  # use the above instead of first name
    for _, name in zip(range(num_names - 1), names):
        setattr(Class, name, 0)

    return Class()


def gen_names():
    for letters in itertools.chain(
        itertools.combinations_with_replacement(string.ascii_letters, 1),
        itertools.combinations_with_replacement(string.ascii_letters, 2),
    ):
        yield "".join(letters)


class TestCompletionHelpers(TestCase):
    def test_gen_names(self):
        self.assertEqual(
            list(zip([1, 2, 3], gen_names())), [(1, "a"), (2, "b"), (3, "c")]
        )

    def test_completion_target(self):
        target = completion_target(14)
        self.assertEqual(
            len([x for x in dir(target) if not x.startswith("_")]), 14
        )


class TestCurtsiesInfoboxPaint(HigherLevelCurtsiesPaintingTest):
    def test_simple(self):
        self.repl.width, self.repl.height = (20, 30)
        self.locals["abc"] = completion_target(3, 50)
        self.repl.current_line = "abc"
        self.repl.cursor_offset = 3
        self.repl.process_event(".")
        screen = [
            ">>> abc.",
            "+------------------+",
            "| aaaaaaaaaaaaaaaa |",
            "| b                |",
            "| c                |",
            "+------------------+",
        ]
        self.assert_paint_ignoring_formatting(screen, (0, 8))

    def test_fill_screen(self):
        self.repl.width, self.repl.height = (20, 15)
        self.locals["abc"] = completion_target(20, 100)
        self.repl.current_line = "abc"
        self.repl.cursor_offset = 3
        self.repl.process_event(".")
        screen = [
            ">>> abc.",
            "+------------------+",
            "| aaaaaaaaaaaaaaaa |",
            "| b                |",
            "| c                |",
            "| d                |",
            "| e                |",
            "| f                |",
            "| g                |",
            "| h                |",
            "| i                |",
            "| j                |",
            "| k                |",
            "| l                |",
            "+------------------+",
        ]
        self.assert_paint_ignoring_formatting(screen, (0, 8))

    def test_lower_on_screen(self):
        self.repl.get_top_usable_line = lambda: 10  # halfway down terminal
        self.repl.width, self.repl.height = (20, 15)
        self.locals["abc"] = completion_target(20, 100)
        self.repl.current_line = "abc"
        self.repl.cursor_offset = 3
        self.repl.process_event(".")
        screen = [
            ">>> abc.",
            "+------------------+",
            "| aaaaaaaaaaaaaaaa |",
            "| b                |",
            "| c                |",
            "| d                |",
            "| e                |",
            "| f                |",
            "| g                |",
            "| h                |",
            "| i                |",
            "| j                |",
            "| k                |",
            "| l                |",
            "+------------------+",
        ]
        # behavior before issue #466
        self.assert_paint_ignoring_formatting(
            screen, try_preserve_history_height=0
        )
        self.assert_paint_ignoring_formatting(screen, min_infobox_height=100)
        # behavior after issue #466
        screen = [
            ">>> abc.",
            "+------------------+",
            "| aaaaaaaaaaaaaaaa |",
            "| b                |",
            "| c                |",
            "+------------------+",
        ]
        self.assert_paint_ignoring_formatting(screen)

    def test_at_bottom_of_screen(self):
        self.repl.get_top_usable_line = lambda: 17  # two lines from bottom
        self.repl.width, self.repl.height = (20, 15)
        self.locals["abc"] = completion_target(20, 100)
        self.repl.current_line = "abc"
        self.repl.cursor_offset = 3
        self.repl.process_event(".")
        screen = [
            ">>> abc.",
            "+------------------+",
            "| aaaaaaaaaaaaaaaa |",
            "| b                |",
            "| c                |",
            "| d                |",
            "| e                |",
            "| f                |",
            "| g                |",
            "| h                |",
            "| i                |",
            "| j                |",
            "| k                |",
            "| l                |",
            "+------------------+",
        ]
        # behavior before issue #466
        self.assert_paint_ignoring_formatting(
            screen, try_preserve_history_height=0
        )
        self.assert_paint_ignoring_formatting(screen, min_infobox_height=100)
        # behavior after issue #466
        screen = [
            ">>> abc.",
            "+------------------+",
            "| aaaaaaaaaaaaaaaa |",
            "| b                |",
            "| c                |",
            "+------------------+",
        ]
        self.assert_paint_ignoring_formatting(screen)
