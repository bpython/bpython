import os
import unittest
from itertools import islice
from mock import Mock
try:
    from unittest import skip
except ImportError:
    def skip(f):
        return lambda self: None

from bpython import config, repl, cli, autocomplete

def setup_config(conf):
    config_struct = config.Struct()
    config.loadini(config_struct, os.devnull)
    if 'autocomplete_mode' in conf:
        config_struct.autocomplete_mode = conf['autocomplete_mode']
    return config_struct

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

    def test_issue127(self):
        self.setInputLine("x=range(")
        self.assertTrue(self.repl.get_args())
        self.assertEqual(self.repl.current_func.__name__, "range")

        self.setInputLine("{x:range(")
        self.assertTrue(self.repl.get_args())
        self.assertEqual(self.repl.current_func.__name__, "range")

        self.setInputLine("foo(1, 2, x,range(")
        self.assertEqual(self.repl.current_func.__name__, "range")

        self.setInputLine("(x,range(")
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

    # TODO: figure out how to capture whether foobar is in globals
    @skip('not working yet')
    def test_push(self):
        self.repl = FakeRepl()
        self.repl.push("foobar = 2")
        self.repl.push("\"foobar\" in globals().keys()")

    # COMPLETE TESTS
    # 1. Global tests
    def test_simple_global_complete(self):
        self.repl = FakeRepl({'autocomplete_mode': autocomplete.SIMPLE})
        self.repl.input_line = "d"
        self.repl.current_word = "d"

        self.assertTrue(self.repl.complete())
        self.assertTrue(hasattr(self.repl.completer,'matches'))
        self.assertEqual(self.repl.completer.matches,
            ['def', 'del', 'delattr(', 'dict(', 'dir(', 'divmod('])

    def test_substring_global_complete(self):
        self.repl = FakeRepl({'autocomplete_mode': autocomplete.SUBSTRING})
        self.repl.input_line = "time"
        self.repl.current_word = "time"

        self.assertTrue(self.repl.complete())
        self.assertTrue(hasattr(self.repl.completer,'matches'))
        self.assertEqual(self.repl.completer.matches,
            ['RuntimeError(', 'RuntimeWarning('])

    def test_fuzzy_global_complete(self):
        self.repl = FakeRepl({'autocomplete_mode': autocomplete.FUZZY})
        self.repl.input_line = "doc"
        self.repl.current_word = "doc"

        self.assertTrue(self.repl.complete())
        self.assertTrue(hasattr(self.repl.completer,'matches'))
        self.assertEqual(self.repl.completer.matches,
            ['UnboundLocalError(', '__doc__'])

    # 2. Attribute tests
    def test_simple_attribute_complete(self):
        self.repl = FakeRepl({'autocomplete_mode': autocomplete.SIMPLE})
        self.repl.input_line = "Foo.b"
        self.repl.current_word = "Foo.b"

        code = "class Foo():\n\tdef bar(self):\n\t\tpass\n"
        for line in code.split("\n"):
            self.repl.push(line)

        self.assertTrue(self.repl.complete())
        self.assertTrue(hasattr(self.repl.completer,'matches'))
        self.assertEqual(self.repl.completer.matches,
            ['Foo.bar'])

    def test_substring_attribute_complete(self):
        self.repl = FakeRepl({'autocomplete_mode': autocomplete.SUBSTRING})
        self.repl.input_line = "Foo.az"
        self.repl.current_word = "Foo.az"

        code = "class Foo():\n\tdef baz(self):\n\t\tpass\n"
        for line in code.split("\n"):
            self.repl.push(line)

        self.assertTrue(self.repl.complete())
        self.assertTrue(hasattr(self.repl.completer,'matches'))
        self.assertEqual(self.repl.completer.matches,
            ['Foo.baz'])

    def test_fuzzy_attribute_complete(self):
        self.repl = FakeRepl({'autocomplete_mode': autocomplete.FUZZY})
        self.repl.input_line = "Foo.br"
        self.repl.current_word = "Foo.br"

        code = "class Foo():\n\tdef bar(self):\n\t\tpass\n"
        for line in code.split("\n"):
            self.repl.push(line)

        self.assertTrue(self.repl.complete())
        self.assertTrue(hasattr(self.repl.completer,'matches'))
        self.assertEqual(self.repl.completer.matches,
            ['Foo.bar'])

    # 3. Edge Cases
    def test_updating_namespace_complete(self):
        self.repl = FakeRepl({'autocomplete_mode': autocomplete.SIMPLE})
        self.repl.input_line = "foo"
        self.repl.current_word = "foo"
        self.repl.push("foobar = 2")

        self.assertTrue(self.repl.complete())
        self.assertTrue(hasattr(self.repl.completer,'matches'))
        self.assertEqual(self.repl.completer.matches,
            ['foobar'])

    def test_file_should_not_appear_in_complete(self):
        self.repl = FakeRepl({'autocomplete_mode': autocomplete.SIMPLE})
        self.repl.input_line = "_"
        self.repl.current_word = "_"
        self.assertTrue(self.repl.complete())
        self.assertTrue(hasattr(self.repl.completer,'matches'))
        self.assertTrue('__file__' not in self.repl.completer.matches)


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

        self.repl.s = "import datetime"
        self.assertEqual(self.repl.cw(), 'datetime')

class TestCliReplTab(unittest.TestCase):

    def setUp(self):

        def setup_matches(tab=False):

            if self.repl.cw() and len(self.repl.cw().split('.')) == 1:
                self.repl.matches = ["foobar", "foofoobar"]
            else:
                self.repl.matches = ["Foo.foobar", "Foo.foofoobar"]

            self.repl.matches_iter = repl.MatchesIterator()
            self.repl.matches_iter.update(self.repl.cw(), self.repl.matches)

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
        self.repl.config.autocomplete_mode = autocomplete.SIMPLE

    # 3 Types of tab complete
    def test_simple_tab_complete(self):
        self.repl.s = "foo"
        self.repl.tab()
        self.assertEqual(self.repl.s, "foobar")

    def test_substring_tab_complete(self):
        self.repl.s = "bar"
        self.repl.config.autocomplete_mode = autocomplete.FUZZY
        self.repl.tab()
        self.assertEqual(self.repl.s, "foobar")
        self.repl.tab()
        self.assertEqual(self.repl.s, "foofoobar")

    def test_fuzzy_tab_complete(self):
        self.repl.s = "br"
        self.repl.config.autocomplete_mode = autocomplete.FUZZY
        self.repl.tab()
        self.assertEqual(self.repl.s, "foobar")

    # Edge Cases
    def test_normal_tab(self):
        """make sure pressing the tab key will
           still in some cases add a tab"""
        self.repl.s = ""
        self.repl.tab()
        self.assertEqual(self.repl.s, "    ")

    def test_back_parameter(self):
        self.repl.s = "foo"
        self.repl.tab(back=True)
        self.assertEqual(self.repl.s, "foofoobar")

    def test_nth_forward(self):
        """make sure that pressing tab twice will fist expand 
        and then cycle to the first match"""
        self.repl.s = "f"
        self.repl.tab()
        self.repl.tab()
        self.assertEqual(self.repl.s, "foobar")

    def test_current_word(self):
        """Complete should not be affected by words that precede it."""
        self.repl.s = "import f"
        self.repl.tab()
        self.assertEqual(self.repl.s, "import foo")

        self.repl.tab()
        self.assertEqual(self.repl.s, "import foobar")

        self.repl.tab()
        self.assertEqual(self.repl.s, "import foofoobar")

    # Attribute Tests
    def test_fuzzy_attribute_tab_complete(self):
        """Test fuzzy attribute with no text"""
        self.repl.s = "Foo."
        self.repl.config.autocomplete_mode = autocomplete.FUZZY

        self.repl.tab()
        self.assertEqual(self.repl.s, "Foo.foobar")

    def test_fuzzy_attribute_tab_complete2(self):
        """Test fuzzy attribute with some text"""
        self.repl.s = "Foo.br"
        self.repl.config.autocomplete_mode = autocomplete.FUZZY

        self.repl.tab()
        self.assertEqual(self.repl.s, "Foo.foobar")

    # Expand Tests
    def test_simple_expand(self):
        self.repl.s = "f"
        self.repl.tab()
        self.assertEqual(self.repl.s, "foo")

    def test_substring_expand_forward(self):
        self.repl.config.autocomplete_mode = autocomplete.SUBSTRING
        self.repl.s = "ba"
        self.repl.tab()
        self.assertEqual(self.repl.s, "bar")

    def test_fuzzy_expand(self):
        pass



if __name__ == '__main__':
    unittest.main()
