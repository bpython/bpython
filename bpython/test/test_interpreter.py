# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import sys
import re
from textwrap import dedent

from curtsies.fmtfuncs import bold, green, magenta, cyan, red, plain

from bpython.curtsiesfrontend import interpreter
from bpython._py3compat import py3
from bpython.test import mock, unittest

pypy = 'PyPy' in sys.version


def remove_ansi(s):
    return re.sub(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]'.encode('ascii'), b'', s)


class TestInterpreter(unittest.TestCase):
    def interp_errlog(self):
        i = interpreter.Interp()
        a = []
        i.write = a.append
        return i, a

    def err_lineno(self, a):
        strings = [x.__unicode__() for x in a]
        for line in reversed(strings):
            clean_line = remove_ansi(line)
            m = re.search(r'line (\d+)[,]', clean_line)
            if m:
                return int(m.group(1))
        return None

    def test_syntaxerror(self):
        i, a = self.interp_errlog()

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
        i, a = self.interp_errlog()

        def f():
            return 1 / 0

        def gfunc():
            return f()

        i.runsource('gfunc()')

        if pypy:
            global_not_found = "global name 'gfunc' is not defined"
        else:
            global_not_found = "name 'gfunc' is not defined"

        expected = (
            'Traceback (most recent call last):\n  File ' +
            green('"<input>"') + ', line ' +
            bold(magenta('1')) + ', in ' + cyan('<module>') + '\n    gfunc()\n' +
            bold(red('NameError')) + ': ' + cyan(global_not_found) + '\n')

        self.assertMultiLineEqual(str(plain('').join(a)), str(expected))
        self.assertEquals(plain('').join(a), expected)

    @unittest.skipIf(py3, "runsource() accepts only unicode in Python 3")
    def test_runsource_bytes(self):
        i = interpreter.Interp(encoding=b'latin-1')

        i.runsource("a = b'\xfe'".encode('latin-1'), encode=False)
        self.assertIsInstance(i.locals['a'], str)
        self.assertEqual(i.locals['a'], b"\xfe")

        i.runsource("b = u'\xfe'".encode('latin-1'), encode=False)
        self.assertIsInstance(i.locals['b'], unicode)
        self.assertEqual(i.locals['b'], "\xfe")

    @unittest.skipUnless(py3, "Only a syntax error in Python 3")
    def test_runsource_bytes_over_128_syntax_error_py3(self):
        i = interpreter.Interp(encoding=b'latin-1')
        i.showsyntaxerror = mock.Mock(return_value=None)

        i.runsource("a = b'\xfe'")
        i.showsyntaxerror.assert_called_with(mock.ANY)

    @unittest.skipIf(py3, "encode is Python 2 only")
    def test_runsource_bytes_over_128_syntax_error_py2(self):
        i = interpreter.Interp(encoding=b'latin-1')

        i.runsource(b"a = b'\xfe'")
        self.assertIsInstance(i.locals['a'], type(b''))
        self.assertEqual(i.locals['a'], b"\xfe")

    @unittest.skipIf(py3, "encode is Python 2 only")
    def test_runsource_unicode(self):
        i = interpreter.Interp(encoding=b'latin-1')

        i.runsource("a = u'\xfe'")
        self.assertIsInstance(i.locals['a'], type(u''))
        self.assertEqual(i.locals['a'], u"\xfe")

    def test_getsource_works_on_interactively_defined_functions(self):
        source = 'def foo(x):\n    return x + 1\n'
        i = interpreter.Interp()
        i.runsource(source)
        import inspect
        inspected_source = inspect.getsource(i.locals['foo'])
        self.assertEquals(inspected_source, source)

    @unittest.skipIf(py3, "encode only does anything in Python 2")
    def test_runsource_unicode_autoencode_and_noencode(self):
        """error line numbers should be fixed"""

        # Since correct behavior for unicode is the same
        # for auto and False, run the same tests
        for encode in ['auto', False]:
            i, a = self.interp_errlog()
            i.runsource(u'[1 + 1,\nabcd]', encode=encode)
            self.assertEqual(self.err_lineno(a), 2)

            i, a = self.interp_errlog()
            i.runsource(u'[1 + 1,\nabcd]', encode=encode)
            self.assertEqual(self.err_lineno(a), 2)

            i, a = self.interp_errlog()
            i.runsource(u'#encoding: utf-8\nabcd', encode=encode)
            self.assertEqual(self.err_lineno(a), 2)

            i, a = self.interp_errlog()
            i.runsource(u'#encoding: utf-8\nabcd',
                        filename='x.py', encode=encode)
            self.assertIn('SyntaxError:',
                          ''.join(''.join(remove_ansi(x.__unicode__())
                                          for x in a)))

    @unittest.skipIf(py3, "encode only does anything in Python 2")
    def test_runsource_unicode_encode(self):
        i, _ = self.interp_errlog()
        with self.assertRaises(ValueError):
            i.runsource(u'1 + 1', encode=True)

        i, _ = self.interp_errlog()
        with self.assertRaises(ValueError):
            i.runsource(u'1 + 1', filename='x.py', encode=True)

    @unittest.skipIf(py3, "encode only does anything in Python 2")
    def test_runsource_bytestring_noencode(self):
        i, a = self.interp_errlog()
        i.runsource(b'[1 + 1,\nabcd]', encode=False)
        self.assertEqual(self.err_lineno(a), 2)

        i, a = self.interp_errlog()
        i.runsource(b'[1 + 1,\nabcd]', filename='x.py', encode=False)
        self.assertEqual(self.err_lineno(a), 2)

        i, a = self.interp_errlog()
        i.runsource(dedent(b'''\
                    #encoding: utf-8

                    ["%s",
                    abcd]''' % (u'åß∂ƒ'.encode('utf8'),)), encode=False)
        self.assertEqual(self.err_lineno(a), 4)

        i, a = self.interp_errlog()
        i.runsource(dedent(b'''\
                    #encoding: utf-8

                    ["%s",
                    abcd]''' % (u'åß∂ƒ'.encode('utf8'),)),
                    filename='x.py', encode=False)
        self.assertEqual(self.err_lineno(a), 4)

    @unittest.skipIf(py3, "encode only does anything in Python 2")
    def test_runsource_bytestring_encode(self):
        i, a = self.interp_errlog()
        i.runsource(b'[1 + 1,\nabcd]', encode=True)
        self.assertEqual(self.err_lineno(a), 2)

        i, a = self.interp_errlog()
        with self.assertRaises(ValueError):
            i.runsource(b'[1 + 1,\nabcd]', filename='x.py', encode=True)

        i, a = self.interp_errlog()
        i.runsource(dedent(b'''\
                    #encoding: utf-8

                    [u"%s",
                    abcd]''' % (u'åß∂ƒ'.encode('utf8'),)), encode=True)
        self.assertEqual(self.err_lineno(a), 4)

        i, a = self.interp_errlog()
        with self.assertRaises(ValueError):
            i.runsource(dedent(b'''\
                        #encoding: utf-8

                        [u"%s",
                        abcd]''' % (u'åß∂ƒ'.encode('utf8'),)),
                        filename='x.py',
                        encode=True)

    @unittest.skipIf(py3, "encode only does anything in Python 2")
    def test_runsource_bytestring_autoencode(self):
        i, a = self.interp_errlog()
        i.runsource(b'[1 + 1,\n abcd]')
        self.assertEqual(self.err_lineno(a), 2)

        i, a = self.interp_errlog()
        i.runsource(b'[1 + 1,\nabcd]', filename='x.py')
        self.assertEqual(self.err_lineno(a), 2)

        i, a = self.interp_errlog()
        i.runsource(dedent(b'''\
                    #encoding: utf-8

                    [u"%s",
                    abcd]''' % (u'åß∂ƒ'.encode('utf8'),)))
        self.assertEqual(self.err_lineno(a), 4)

        i, a = self.interp_errlog()
        i.runsource(dedent(b'''\
                    #encoding: utf-8

                    [u"%s",
                    abcd]''' % (u'åß∂ƒ'.encode('utf8'),)))
        self.assertEqual(self.err_lineno(a), 4)
