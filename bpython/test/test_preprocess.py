import difflib
import inspect
import re
import unittest

from code import compile_command as compiler
from codeop import CommandCompiler
from functools import partial

from bpython.curtsiesfrontend.interpreter import code_finished_will_parse
from bpython.curtsiesfrontend.preprocess import preprocess
from bpython.test.fodder import original, processed


preproc = partial(preprocess, compiler=CommandCompiler())


def get_fodder_source(test_name):
    pattern = rf"#StartTest-{test_name}\n(.*?)#EndTest"
    orig, xformed = (
        re.search(pattern, inspect.getsource(module), re.DOTALL)
        for module in [original, processed]
    )

    if not orig:
        raise ValueError(
            f"Can't locate test {test_name} in original fodder file"
        )
    if not xformed:
        raise ValueError(
            f"Can't locate test {test_name} in processed fodder file"
        )
    return orig.group(1), xformed.group(1)


class TestPreprocessing(unittest.TestCase):
    def assertCompiles(self, source):
        finished, parsable = code_finished_will_parse(source, compiler)
        return finished and parsable

    def test_indent_empty_lines_nops(self):
        self.assertEqual(preproc("hello"), "hello")
        self.assertEqual(preproc("hello\ngoodbye"), "hello\ngoodbye")
        self.assertEqual(preproc("a\n    b\nc\n"), "a\n    b\nc\n")

    def assertShowWhitespaceEqual(self, a, b):
        self.assertEqual(
            a,
            b,
            "".join(
                difflib.context_diff(
                    a.replace(" ", "~").splitlines(True),
                    b.replace(" ", "~").splitlines(True),
                    fromfile="actual",
                    tofile="expected",
                    n=5,
                )
            ),
        )

    def assertDefinitionIndented(self, obj):
        name = obj.__name__
        obj2 = getattr(processed, name)
        orig = inspect.getsource(obj)
        xformed = inspect.getsource(obj2)
        self.assertShowWhitespaceEqual(preproc(orig), xformed)
        self.assertCompiles(xformed)

    def assertLinesIndented(self, test_name):
        orig, xformed = get_fodder_source(test_name)
        self.assertShowWhitespaceEqual(preproc(orig), xformed)
        self.assertCompiles(xformed)

    def assertIndented(self, obj_or_name):
        if isinstance(obj_or_name, str):
            self.assertLinesIndented(obj_or_name)
        else:
            self.assertDefinitionIndented(obj_or_name)

    def test_empty_line_between_methods(self):
        self.assertIndented(original.BlankLineBetweenMethods)

    def test_empty_line_within_class(self):
        self.assertIndented(original.BlankLineInFunction)

    def test_blank_lines_in_for_loop(self):
        self.assertIndented("blank_lines_in_for_loop")

    @unittest.skip(
        "More advanced technique required: need to try compiling and "
        "backtracking"
    )
    def test_blank_line_in_try_catch(self):
        self.assertIndented("blank_line_in_try_catch")

    @unittest.skip(
        "More advanced technique required: need to try compiling and "
        "backtracking"
    )
    def test_blank_line_in_try_catch_else(self):
        self.assertIndented("blank_line_in_try_catch_else")

    def test_blank_trailing_line(self):
        self.assertIndented("blank_trailing_line")

    def test_tabs(self):
        self.assertIndented(original.tabs)


class TestSeparateBlocks(unittest.TestCase):
    """Pasted code has no blank line after a block, so one has to be added
    for the statement that follows it to be run separately (#1057)"""

    def test_statement_after_block(self):
        self.assertEqual(
            preproc("for i in r:\n    f(i)\nprint(1)\n"),
            "for i in r:\n    f(i)\n\nprint(1)\n",
        )

    def test_statement_after_nested_blocks(self):
        self.assertEqual(
            preproc("for i in r:\n    if i:\n        f(i)\nprint(1)\n"),
            "for i in r:\n    if i:\n        f(i)\n\nprint(1)\n",
        )

    def test_consecutive_blocks(self):
        self.assertEqual(
            preproc("if a:\n    f()\nwhile b:\n    g()\n"),
            "if a:\n    f()\n\nwhile b:\n    g()\n",
        )

    def test_clauses_continuing_a_block_are_left_alone(self):
        for source in (
            "if a:\n    f()\nelif b:\n    g()\nelse:\n    h()\n",
            "try:\n    f()\nexcept E:\n    g()\nfinally:\n    h()\n",
            "for i in r:\n    f(i)\nelse:\n    g()\n",
        ):
            with self.subTest(source=source):
                self.assertEqual(preproc(source), source)

    def test_unindented_lines_inside_brackets_are_left_alone(self):
        # an unclosed bracket keeps the statement going, so these lines are
        # continuations rather than new statements
        for source in (
            "total = (\n1 +\n2\n)\n",
            "items = [\n'a',\n'b',\n]\n",
            "f(\nx,\n)\n",
        ):
            with self.subTest(source=source):
                self.assertEqual(preproc(source), source)

    def test_consecutive_simple_statements_are_left_alone(self):
        source = "a = 1\nb = 2\nprint(a + b)\n"
        self.assertEqual(preproc(source), source)

    def test_existing_blank_line_is_not_doubled(self):
        source = "for i in r:\n    f(i)\n\nprint(1)\n"
        self.assertEqual(preproc(source), source)

    def test_block_after_statement(self):
        source = "a = 1\nfor i in r:\n    f(i)\n"
        self.assertEqual(preproc(source), source)

    def test_comment_above_a_continuing_clause_is_left_alone(self):
        source = "if a:\n    f()\n# why not\nelse:\n    g()\n"
        self.assertEqual(preproc(source), source)

    def test_decorator_is_not_separated_from_its_definition(self):
        self.assertEqual(
            preproc("@deco\ndef f():\n    pass\nprint(1)\n"),
            "@deco\ndef f():\n    pass\n\nprint(1)\n",
        )

    def test_lines_inside_a_string_are_left_alone(self):
        source = 's = """\nabc\ndef\n"""\nprint(s)\n'
        self.assertEqual(preproc(source), source)

    def test_backslash_continuation_is_left_alone(self):
        source = "a = 1 + \\\n    2\nprint(a)\n"
        self.assertEqual(preproc(source), source)
