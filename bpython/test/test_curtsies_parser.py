import unittest

from bpython.curtsiesfrontend import parse
from curtsies.fmtfuncs import yellow, cyan, green, bold

class TestExecArgs(unittest.TestCase):

    def test_parse(self):
        self.assertEquals(parse.parse(u'\x01y\x03print\x04'),
                          yellow(u'print'))

        self.assertEquals(parse.parse(u'\x01y\x03print\x04\x01c\x03 \x04\x01g\x031\x04\x01c\x03 \x04\x01Y\x03+\x04\x01c\x03 \x04\x01g\x032\x04'),
                          yellow(u'print')+cyan(u' ')+green(u'1')+cyan(u' ')+bold(yellow(u'+'))+cyan(' ')+green(u'2'))

    def test_peal_off_string(self):
        self.assertEquals(parse.peel_off_string('\x01RI\x03]\x04asdf'),
                          ({'bg': 'I', 'string': ']', 'fg': 'R', 'colormarker':
                            '\x01RI', 'bold': ''}, 'asdf'))
