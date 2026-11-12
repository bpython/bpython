import unittest
import sys
from unittest.mock import Mock

from curtsies.fmtfuncs import bold, green, magenta, cyan, red, plain

from bpython.curtsiesfrontend import interpreter


class Interpreter(interpreter.Interp):
    def __init__(self):
        super().__init__()
        self.a = []
        self.write = self.a.append


class TestInterpreter(unittest.TestCase):
    def test_syntaxerror(self):
        i = Interpreter()

        i.runsource("1.1.1.1")

        expected = (
            "  File "
            + green('"<input>"')
            + ", line "
            + bold(magenta("1"))
            + "\n    1.1.1.1\n       ^^\n"
            + bold(red("SyntaxError"))
            + ": "
            + cyan("invalid syntax")
            + "\n"
        )

        a = i.a
        self.assertMultiLineEqual(str(plain("").join(a)), str(expected))
        self.assertEqual(plain("").join(a), expected)

    def test_semantic_syntaxerrors_leave_interpreter_usable(self):
        for source in ("nonlocal a", "return", "break", "continue"):
            with self.subTest(source=source):
                i = Interpreter()
                callback = Mock()
                i.syntaxerror_callback = callback
                self.assertFalse(i.runsource(source))
                callback.assert_called_once_with()
                output = str(plain("").join(i.a))
                self.assertIn("SyntaxError", output)
                self.assertIn('"<input>"', output)
                self.assertNotIn("<bpython-input-", output)
                self.assertIsInstance(sys.last_value, SyntaxError)
                self.assertEqual(sys.last_value.filename, "<input>")
                self.assertFalse(i.runsource("answer = 6 * 7"))
                self.assertEqual(i.locals["answer"], 42)

    def test_syntaxerror_keeps_original_exception_and_details(self):
        i = Interpreter()
        error = SyntaxError("message")
        error.filename = "<bpython-input-123>"
        error.lineno = 3
        error.offset = 2
        error.end_lineno = 3
        error.end_offset = 5
        error.text = "bad source"
        error.add_note("additional information")
        try:
            raise error
        except SyntaxError:
            i.showsyntaxerror(error.filename)
        self.assertIs(sys.last_value, error)
        self.assertEqual(error.filename, "<input>")
        self.assertEqual((error.lineno, error.offset), (3, 2))
        self.assertEqual((error.end_lineno, error.end_offset), (3, 5))
        self.assertIn("additional information", str(plain("").join(i.a)))

    def test_explicit_syntaxerror_filename(self):
        i = Interpreter()
        i.runsource("1.1.1.1", filename="example.py")
        self.assertIn('"example.py"', str(plain("").join(i.a)))
        self.assertEqual(sys.last_value.filename, "example.py")

    def test_indentationerror_filename(self):
        i = Interpreter()
        i.runsource("  answer = 42")
        output = str(plain("").join(i.a))
        self.assertIn("IndentationError", output)
        self.assertIn('"<input>"', output)
        self.assertIsInstance(sys.last_value, IndentationError)

    def test_traceback(self):
        i = Interpreter()

        def f():
            return 1 / 0

        def gfunc():
            return f()

        i.runsource("gfunc()")

        a = str(plain("").join(i.a))
        self.assertIn("name 'gfunc' is not defined", a)
        self.assertIn("NameErro", a)

    def test_getsource_works_on_interactively_defined_functions(self):
        source = "def foo(x):\n    return x + 1\n"
        i = interpreter.Interp()
        i.runsource(source)
        import inspect

        inspected_source = inspect.getsource(i.locals["foo"])
        self.assertEqual(inspected_source, source)
