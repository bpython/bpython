import sys
import unittest

from curtsies.fmtfuncs import bold, green, magenta, cyan, red, plain

from bpython.curtsiesfrontend import interpreter

pypy = "PyPy" in sys.version


class Interpreter(interpreter.Interp):
    def __init__(self):
        super().__init__()
        self.a = []
        self.write = self.a.append


class TestInterpreter(unittest.TestCase):
    def test_syntaxerror(self):
        i = Interpreter()

        i.runsource("1.1.1.1")

        if (3, 10, 1) <= sys.version_info[:3]:
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
        elif (3, 10) <= sys.version_info[:2]:
            expected = (
                "  File "
                + green('"<input>"')
                + ", line "
                + bold(magenta("1"))
                + "\n    1.1.1.1\n    ^^^^^\n"
                + bold(red("SyntaxError"))
                + ": "
                + cyan("invalid syntax. Perhaps you forgot a comma?")
                + "\n"
            )
        elif (3, 8) <= sys.version_info[:2]:
            expected = (
                "  File "
                + green('"<input>"')
                + ", line "
                + bold(magenta("1"))
                + "\n    1.1.1.1\n       ^\n"
                + bold(red("SyntaxError"))
                + ": "
                + cyan("invalid syntax")
                + "\n"
            )
        elif pypy:
            expected = (
                "  File "
                + green('"<input>"')
                + ", line "
                + bold(magenta("1"))
                + "\n    1.1.1.1\n       ^\n"
                + bold(red("SyntaxError"))
                + ": "
                + cyan("invalid syntax")
                + "\n"
            )
        else:
            expected = (
                "  File "
                + green('"<input>"')
                + ", line "
                + bold(magenta("1"))
                + "\n    1.1.1.1\n        ^\n"
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

        global_not_found = "name 'gfunc' is not defined"

        if (3, 13) <= sys.version_info[:2]:
            expected = (
                "Traceback (most recent call last):\n  File "
                + green('"<input>"')
                + ", line "
                + bold(magenta("1"))
                + ", in "
                + cyan("<module>")
                + "\n    gfunc()"
                + "\n    ^^^^^\n"
                + bold(red("NameError"))
                + ": "
                + cyan(global_not_found)
                + "\n"
            )
        elif (3, 11) <= sys.version_info[:2]:
            expected = (
                "Traceback (most recent call last):\n  File "
                + green('"<input>"')
                + ", line "
                + bold(magenta("1"))
                + ", in "
                + cyan("<module>")
                + "\n    gfunc()"
                + "\n     ^^^^^\n"
                + bold(red("NameError"))
                + ": "
                + cyan(global_not_found)
                + "\n"
            )
        else:
            expected = (
                "Traceback (most recent call last):\n  File "
                + green('"<input>"')
                + ", line "
                + bold(magenta("1"))
                + ", in "
                + cyan("<module>")
                + "\n    gfunc()\n"
                + bold(red("NameError"))
                + ": "
                + cyan(global_not_found)
                + "\n"
            )

        a = i.a
        self.assertMultiLineEqual(str(expected), str(plain("").join(a)))
        self.assertEqual(expected, plain("").join(a))

    def test_getsource_works_on_interactively_defined_functions(self):
        source = "def foo(x):\n    return x + 1\n"
        i = interpreter.Interp()
        i.runsource(source)
        import inspect

        inspected_source = inspect.getsource(i.locals["foo"])
        self.assertEqual(inspected_source, source)
