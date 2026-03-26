import unittest

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
