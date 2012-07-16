import os
import unittest
import sys
from itertools import islice
from mock import Mock
from bpython import config, repl, cli

def setup_config(conf):
    config_struct = config.Struct()
    config.loadini(config_struct, os.devnull)
    if 'autocomplete_mode' in conf:
        config_struct.autocomplete_mode = conf['autocomplete_mode']
    return config_struct

class TestHistory(unittest.TestCase):
    def setUp(self):
        self.history = repl.History('#%d' % x for x in range(1000))

    def test_is_at_start(self):
        self.history.first()

        self.assertNotEqual(self.history.index, 0)
        self.assertTrue(self.history.is_at_end)
        self.history.forward()
        self.assertFalse(self.history.is_at_end)

    def test_is_at_end(self):
        self.history.last()

        self.assertEqual(self.history.index, 0)
        self.assertTrue(self.history.is_at_start)
        self.assertFalse(self.history.is_at_end)

    def test_first(self):
        self.history.first()

        self.assertFalse(self.history.is_at_start)
        self.assertTrue(self.history.is_at_end)

    def test_last(self):
        self.history.last()

        self.assertTrue(self.history.is_at_start)
        self.assertFalse(self.history.is_at_end)

    def test_back(self):
        self.assertEqual(self.history.back(), '#999')
        self.assertNotEqual(self.history.back(), '#999')
        self.assertEqual(self.history.back(), '#997')
        for x in range(997):
            self.history.back()
        self.assertEqual(self.history.back(), '#0')

    def test_forward(self):
        self.history.first()

        self.assertEqual(self.history.forward(), '#1')
        self.assertNotEqual(self.history.forward(), '#1')
        self.assertEqual(self.history.forward(), '#3')
        #  1000 == entries   4 == len(range(1, 3) ===> '#1000' (so +1)
        for x in range(1000 - 4 - 1):
            self.history.forward()
        self.assertEqual(self.history.forward(), '#999')

    def test_append(self):
        self.history.append('print "foo\n"\n')
        self.history.append('\n')

        self.assertEqual(self.history.back(), 'print "foo\n"')

    @unittest.skip("currently fails")
    def test_enter(self):
        self.history.enter('#lastnumber!')

        self.assertEqual(self.history.back(), '#999')
        self.assertEqual(self.history.forward(), '#lastnumber!')

    def test_reset(self):
        self.history.enter('#lastnumber!')
        self.history.reset()

        self.assertEqual(self.history.back(), '#999')
        self.assertEqual(self.history.forward(), '')

class TestMatchesIterator(unittest.TestCase):

    def setUp(self):
        self.matches = ['bobby', 'bobbies', 'bobberina']
        self.matches_iterator = repl.MatchesIterator(current_word='bob',
                                                     matches=self.matches)

    def test_next(self):
        self.assertEqual(self.matches_iterator.next(), self.matches[0])

        for x in range(len(self.matches) - 1):
            self.matches_iterator.next()

        self.assertEqual(self.matches_iterator.next(), self.matches[0])
        self.assertEqual(self.matches_iterator.next(), self. matches[1])
        self.assertNotEqual(self.matches_iterator.next(), self.matches[1])

    def test_previous(self):
        self.assertEqual(self.matches_iterator.previous(), self.matches[2])

        for x in range(len(self.matches) - 1):
            self.matches_iterator.previous()

        self.assertNotEqual(self.matches_iterator.previous(), self.matches[0])
        self.assertEqual(self.matches_iterator.previous(), self.matches[1])
        self.assertEqual(self.matches_iterator.previous(), self.matches[0])

    def test_nonzero(self):
        """self.matches_iterator should be False at start,
        then True once we active a match.
        """
        self.assertFalse(self.matches_iterator)
        self.matches_iterator.next()
        self.assertTrue(self.matches_iterator)

    def test_iter(self):
        slice = islice(self.matches_iterator, 0, 9)
        self.assertEqual(list(slice), self.matches * 3)

    def test_current(self):
        self.assertRaises(ValueError, self.matches_iterator.current)
        self.matches_iterator.next()
        self.assertEqual(self.matches_iterator.current(), self.matches[0])

    def test_update(self):
        slice = islice(self.matches_iterator, 0, 3)
        self.assertEqual(list(slice), self.matches)

        newmatches = ['string', 'str', 'set']
        self.matches_iterator.update('s', newmatches)

        newslice = islice(newmatches, 0, 3)
        self.assertNotEqual(list(slice), self.matches)
        self.assertEqual(list(newslice), newmatches)

class FakeHistory(repl.History):

    def __init__(self):
        pass

    def reset(self):
        pass

class FakeRepl(repl.Repl):
    def __init__(self, conf={}):
        repl.Repl.__init__(self, repl.Interpreter(), setup_config(conf))
        self.input_line = ""
        self.current_word = ""
        self.cpos = 0

    def current_line(self):
        return self.input_line

    def cw(self):
        return self.current_word

class FakeCliRepl(cli.CLIRepl, FakeRepl):
    def __init__(self):
        self.s = ''
        self.cpos = 0
        self.rl_history = FakeHistory()

class TestArgspec(unittest.TestCase):
    def setUp(self):
        self.repl = FakeRepl()
        self.repl.push("def spam(a, b, c):\n", False)
        self.repl.push("    pass\n", False)
        self.repl.push("\n", False)

    def setInputLine(self, line):
        """Set current input line of the test REPL."""
        self.repl.input_line = line

    def test_func_name(self):
        for (line, expected_name) in [("spam(", "spam"),
                                      ("spam(map([]", "map"),
                                      ("spam((), ", "spam")]:
            self.setInputLine(line)
            self.assertTrue(self.repl.get_args())
            self.assertEqual(self.repl.current_func.__name__, expected_name)

    def test_syntax_error_parens(self):
        for line in ["spam(]", "spam([)", "spam())"]:
            self.setInputLine(line)
            # Should not explode
            self.repl.get_args()

    def test_kw_arg_position(self):
        self.setInputLine("spam(a=0")
        self.assertTrue(self.repl.get_args())
        self.assertEqual(self.repl.argspec[3], "a")

        self.setInputLine("spam(1, b=1")
        self.assertTrue(self.repl.get_args())
        self.assertEqual(self.repl.argspec[3], "b")

        self.setInputLine("spam(1, c=2")
        self.assertTrue(self.repl.get_args())
        self.assertEqual(self.repl.argspec[3], "c")

    def test_lambda_position(self):
        self.setInputLine("spam(lambda a, b: 1, ")
        self.assertTrue(self.repl.get_args())
        self.assertTrue(self.repl.argspec)
        # Argument position
        self.assertEqual(self.repl.argspec[3], 1)

    @unittest.skip('currently fails')
    def test_name_in_assignment_without_spaces(self):
        # Issue #127
        self.setInputLine("x=range(")
        self.assertTrue(self.repl.get_args())
        self.assertEqual(self.repl.current_func.__name__, "range")

    def test_nonexistent_name(self):
        self.setInputLine("spamspamspam(")
        self.assertFalse(self.repl.get_args())

class TestRepl(unittest.TestCase):

    def setUp(self):
        self.repl = FakeRepl()

    def test_current_string(self):
        self.repl.input_line = 'a = "2"'
        self.assertEqual(self.repl.current_string(), '"2"')

        self.repl.input_line = 'a = "2" + 2'
        self.assertEqual(self.repl.current_string(), '')

    def test_default_complete(self):
        self.repl = FakeRepl({'autocomplete_mode':"1"})
        self.repl.input_line = "d"
        self.repl.current_word = "d"

        self.assertTrue(self.repl.complete())
        self.assertTrue(hasattr(self.repl.completer,'matches'))
        self.assertEqual(self.repl.completer.matches,
            ['def', 'del', 'delattr(', 'dict(', 'dir(', 'divmod('])

    def test_alternate_complete(self):
        self.repl = FakeRepl({'autocomplete_mode':"2"})
        self.repl.input_line = "doc"
        self.repl.current_word = "doc"

        self.assertTrue(self.repl.complete())
        self.assertTrue(hasattr(self.repl.completer,'matches'))
        self.assertEqual(self.repl.completer.matches,
            ['UnboundLocalError(', '__doc__'])

class TestCliRepl(unittest.TestCase):

    def setUp(self):
        self.repl = FakeCliRepl()

    def test_atbol(self):
        self.assertTrue(self.repl.atbol())

        self.repl.s = "\t\t"
        self.assertTrue(self.repl.atbol())

        self.repl.s = "\t\tnot an empty line"
        self.assertFalse(self.repl.atbol())

    def test_addstr(self):
        self.repl.complete = Mock(True)

        self.repl.s = "foo"
        self.repl.addstr("bar")
        self.assertEqual(self.repl.s, "foobar")

        self.repl.cpos = 3
        self.repl.addstr('buzz')
        self.assertEqual(self.repl.s, "foobuzzbar")

    def test_cw(self):

        self.repl.cpos = 2
        self.assertEqual(self.repl.cw(), None)
        self.repl.cpos = 0

        self.repl.s = ''
        self.assertEqual(self.repl.cw(), None)

        self.repl.s = "this.is.a.test\t"
        self.assertEqual(self.repl.cw(), None)

        s = "this.is.a.test"
        self.repl.s = s
        self.assertEqual(self.repl.cw(), s)

        s = "\t\tthis.is.a.test"
        self.repl.s = s
        self.assertEqual(self.repl.cw(), s.lstrip())

        self.repl.s = "this.is.\ta.test"
        self.assertEqual(self.repl.cw(), 'a.test')


class TestCliReplTab(unittest.TestCase):

    def setUp(self):

        def setup_matches(tab=False):
            self.repl.matches = ["foobar", "foofoobar"]
            self.repl.matches_iter = repl.MatchesIterator()
            self.repl.matches_iter.update('f', self.repl.matches)

        self.repl = FakeCliRepl()

        # Stub out CLIRepl attributes
        self.repl.buffer = []
        self.repl.argspec = Mock()
        self.repl.print_line = Mock()
        self.repl.show_list = Mock()

        # Stub out complete
        self.repl.complete = Mock()
        self.repl.complete.return_value = True
        self.repl.complete.side_effect = setup_matches
        self.repl.matches_iter = None

        # Stub out the config logic
        self.repl.config = Mock()
        self.repl.config.tab_length = 4
        self.repl.config.auto_display_list = True
        self.repl.config.list_win_visible = True
        self.repl.config.autocomplete_mode = 1


    def test_tab(self):
        def test_normal_tab(self):
            self.repl.s = ""
            setup_complete()
            self.repl.tab()
            self.assertEqual(self.repl.s, "    ")

        def test_expand(self):
            self.repl.s = "f"
            setup_complete()
            self.repl.tab()
            self.assertEqual(self.repl.s, "foo")

        def test_first_forward(self):
            self.repl.s = "foo"
            setup_complete()
            self.repl.tab()
            self.assertEqual(self.repl.s, "foobar")

        def test_first_back(self):
            self.repl.s = "foo"
            setup_complete()
            self.repl.tab(back=True)
            self.assertEqual(self.repl.s, "foofoobar")

        def test_nth_forward(self):
            self.repl.s = "f"
            setup_complete()
            self.repl.tab()
            self.repl.tab()
            self.assertEqual(self.repl.s, "foobar")

        def test_nth_back(self):
            self.repl.s = "f"
            setup_complete()
            self.repl.tab()
            self.repl.tab(back=True)
            self.assertEqual(self.repl.s, "foofoobar")

        def test_non_contiguous_tab_complete(self):
            self.repl.s = "br"
            self.repl.config.autocomplete_mode = 2
            setup_complete()
            self.repl.tab()
            self.assertEqual(self.repl.s, "foobar")

        def test_non_appending_tab_complete(self):
            self.repl.s = "bar"
            self.repl.config.autocomplete_mode = 2
            setup_complete()
            self.repl.tab()
            self.assertEqual(self.repl.s, "foobar")
            self.repl.tab()
            self.assertEqual(self.repl.s, "foofoobar")

if __name__ == '__main__':
    unittest.main()
