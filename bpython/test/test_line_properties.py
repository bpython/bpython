import unittest
import re

from bpython.curtsiesfrontend.line import current_word, current_dict_key, current_dict, current_string, current_object, current_object_attribute


def cursor(s):
    """'ab|c' -> (2, 'abc')"""
    cursor_offset = s.index('|')
    line = s[:cursor_offset] + s[cursor_offset+1:]
    return cursor_offset, line

def decode(s):
    """'a<bd|c>d' -> ((3, 'abcd'), (1, 3, 'bdc'))"""

    if not ((s.count('<') == s.count('>') == 1 or s.count('<') == s.count('>') == 0)
            and s.count('|') == 1):
        raise ValueError('match helper needs <, and > to occur just once')
    matches = list(re.finditer(r'[<>|]', s))
    assert len(matches) in [1, 3], [m.group() for m in matches]
    d = {}
    for i, m in enumerate(matches):
        d[m.group(0)] = m.start() - i
        s = s[:m.start() - i] + s[m.end() - i:]
    assert len(d) in [1,3], 'need all the parts just once! %r' % d

    if '<' in d:
        return (d['|'], s), (d['<'], d['>'], s[d['<']:d['>']])
    else:
        return (d['|'], s), None

class LineTestCase(unittest.TestCase):
    def assertAccess(self, s):
        r"""Asserts that self.func matches as described
        by s, which uses a little language to describe matches:

        abcd<efg>hijklmnopqrstuvwx|yz
           /|\ /|\               /|\
            |   |                 |
         the function should   the current cursor position
         match this "efg"      is between the x and y
        """
        (cursor_offset, line), match =  decode(s)
        self.assertEqual(self.func(cursor_offset, line), match)

class TestHelpers(LineTestCase):
    def test_I(self):
        self.assertEqual(cursor('asd|fgh'), (3, 'asdfgh'))

    def test_decode(self):
        self.assertEqual(decode('a<bd|c>d'), ((3, 'abdcd'), (1, 4, 'bdc')))
        self.assertEqual(decode('a|<bdc>d'), ((1, 'abdcd'), (1, 4, 'bdc')))
        self.assertEqual(decode('a<bdc>d|'), ((5, 'abdcd'), (1, 4, 'bdc')))

    def test_assert_access(self):
        def dumb_func(cursor_offset, line):
            return (0, 2, 'ab')
        self.func = dumb_func
        self.assertAccess('<a|b>d')

class TestCurrentWord(LineTestCase):
    def setUp(self):
        self.func = current_word

    def test_simple(self):
        self.assertAccess('|')
        self.assertAccess('|asdf')
        self.assertAccess('<a|sdf>')
        self.assertAccess('<asdf|>')
        self.assertAccess('<asdfg|>')
        self.assertAccess('asdf + <asdfg|>')
        self.assertAccess('<asdfg|> + asdf')

    def test_inside(self):
        self.assertAccess('<asd|>')
        self.assertAccess('<asd|fg>')

    def test_dots(self):
        self.assertAccess('<Object.attr1|>')
        self.assertAccess('<Object.attr1.attr2|>')
        self.assertAccess('<Object.att|r1.attr2>')
        self.assertAccess('stuff[stuff] + {123: 456} + <Object.attr1.attr2|>')
        self.assertAccess('stuff[<asd|fg>]')
        self.assertAccess('stuff[asdf[<asd|fg>]')

class TestCurrentDictKey(LineTestCase):
    def setUp(self):
        self.func = current_dict_key
    def test_simple(self):
        self.assertAccess('asdf|')
        self.assertAccess('asdf|')
        self.assertAccess('asdf[<>|')
        self.assertAccess('asdf[<>|]')
        self.assertAccess('object.dict[<abc|>')
        self.assertAccess('asdf|')
        self.assertAccess('asdf[<(>|]')
        self.assertAccess('asdf[<(1>|]')
        self.assertAccess('asdf[<(1,>|]')
        self.assertAccess('asdf[<(1, >|]')
        self.assertAccess('asdf[<(1, 2)>|]')

class TestCurrentDict(LineTestCase):
    def setUp(self):
        self.func = current_dict
    def test_simple(self):
        self.assertAccess('asdf|')
        self.assertAccess('asdf|')
        self.assertAccess('<asdf>[|')
        self.assertAccess('<asdf>[|]')
        self.assertAccess('<object.dict>[abc|')
        self.assertAccess('asdf|')

class TestCurrentString(LineTestCase):
    def setUp(self):
        self.func = current_string
    def test_simple(self):
        self.assertAccess('"<as|df>"')
        self.assertAccess('"<asdf|>"')
        self.assertAccess('"<|asdf>"')
        self.assertAccess("'<asdf|>'")
        self.assertAccess("'<|asdf>'")
        self.assertAccess("'''<asdf|>'''")
        self.assertAccess('"""<asdf|>"""')
        self.assertAccess('asdf.afd("a") + "<asdf|>"')

class TestCurrentObject(LineTestCase):
    def setUp(self):
        self.func = current_object
    def test_simple(self):
        self.assertAccess('<Object>.attr1|')
        self.assertAccess('<Object>.|')
        self.assertAccess('Object|')
        self.assertAccess('Object|.')
        self.assertAccess('<Object>.|')
        self.assertAccess('<Object.attr1>.attr2|')
        self.assertAccess('<Object>.att|r1.attr2')
        self.assertAccess('stuff[stuff] + {123: 456} + <Object.attr1>.attr2|')
        self.assertAccess('stuff[asd|fg]')
        self.assertAccess('stuff[asdf[asd|fg]')

class TestCurrentAttribute(LineTestCase):
    def setUp(self):
        self.func = current_object_attribute
    def test_simple(self):
        self.assertAccess('Object.<attr1|>')
        self.assertAccess('Object.attr1.<attr2|>')
        self.assertAccess('Object.<att|r1>.attr2')
        self.assertAccess('stuff[stuff] + {123: 456} + Object.attr1.<attr2|>')
        self.assertAccess('stuff[asd|fg]')
        self.assertAccess('stuff[asdf[asd|fg]')
        self.assertAccess('Object.attr1.<|attr2>')
        self.assertAccess('Object.<attr1|>.attr2')

if __name__ == '__main__':
    unittest.main()
