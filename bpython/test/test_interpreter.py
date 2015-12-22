# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import sys

from curtsies.fmtfuncs import bold, green, magenta, cyan, red, plain

from bpython.curtsiesfrontend import interpreter
from bpython._py3compat import py3
from bpython.test import mock, unittest

pypy = 'PyPy' in sys.version


class TestInterpreter(unittest.TestCase):
    def test_syntaxerror(self):
        i = interpreter.Interp()
        a = []

        def append_to_a(message):
            a.append(message)

        i.write = append_to_a
        i.runsource('1.1.1.1')

        if pypy:
            expected = (
                '  File ' + green('"<input>"') +
                ', line ' + bold(magenta('1')) + '\n    1.1.1.1\n      ^\n' +
                bold(red('SyntaxError')) + ': ' + cyan('invalid syntax') +
                '\n')
        else:
            expected = (
                '  File ' + green('"<input>"') +
                ', line ' + bold(magenta('1')) + '\n    1.1.1.1\n        ^\n' +
                bold(red('SyntaxError')) + ': ' + cyan('invalid syntax') +
                '\n')

        self.assertMultiLineEqual(str(plain('').join(a)), str(expected))
        self.assertEquals(plain('').join(a), expected)

    def test_traceback(self):
        i = interpreter.Interp()
        a = []

        def append_to_a(message):
            a.append(message)

        i.write = append_to_a

        def f():
            return 1/0

        def g():
            return f()

        i.runsource('g()')

        if pypy:
            global_not_found = "global name 'g' is not defined"
        else:
            global_not_found = "name 'g' is not defined"

        expected = (
            'Traceback (most recent call last):\n  File ' +
            green('"<input>"') + ', line ' +
            bold(magenta('1')) + ', in ' + cyan('<module>') + '\n    g()\n' +
            bold(red('NameError')) + ': ' + cyan(global_not_found) + '\n')

        self.assertMultiLineEqual(str(plain('').join(a)), str(expected))
        self.assertEquals(plain('').join(a), expected)

    @unittest.skipIf(py3, "runsource() accepts only unicode in Python 3")
    def test_runsource_bytes(self):
        i = interpreter.Interp(encoding='latin-1')

        i.runsource("a = b'\xfe'".encode('latin-1'), encode=False)
        self.assertIsInstance(i.locals['a'], str)
        self.assertEqual(i.locals['a'], b"\xfe")

        i.runsource("b = u'\xfe'".encode('latin-1'), encode=False)
        self.assertIsInstance(i.locals['b'], unicode)
        self.assertEqual(i.locals['b'], "\xfe")

    @unittest.skipUnless(py3, "Only a syntax error in Python 3")
    def test_runsource_bytes_over_128_syntax_error_py3(self):
        i = interpreter.Interp(encoding='latin-1')
        i.showsyntaxerror = mock.Mock(return_value=None)

        i.runsource("a = b'\xfe'", encode=True)
        i.showsyntaxerror.assert_called_with(mock.ANY)

    @unittest.skipIf(py3, "encode is Python 2 only")
    def test_runsource_bytes_over_128_syntax_error_py2(self):
        i = interpreter.Interp(encoding='latin-1')

        i.runsource("a = b'\xfe'", encode=True)
        self.assertIsInstance(i.locals['a'], type(b''))
        self.assertEqual(i.locals['a'], b"\xfe")

    @unittest.skipIf(py3, "encode is Python 2 only")
    def test_runsource_unicode(self):
        i = interpreter.Interp(encoding='latin-1')

        i.runsource("a = u'\xfe'", encode=True)
        self.assertIsInstance(i.locals['a'], type(u''))
        self.assertEqual(i.locals['a'], u"\xfe")

    def test_getsource_works_on_interactively_defined_functions(self):
        source = 'def foo(x):\n    return x + 1\n'
        i = interpreter.Interp()
        i.runsource(source)
        import inspect
        inspected_source = inspect.getsource(i.locals['foo'])
        self.assertEquals(inspected_source, source)
