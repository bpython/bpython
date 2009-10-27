#!/usr/bin/env python
#
# The MIT License
#
# Copyright (c) 2008 Simon de Vlieger
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import string


class KeyMap:

    def __init__(self):
        self.map = {}

    def __getitem__(self, key):
        if key in self.map:
            return self.map[key]
        else:
            raise Exception('Configured keymap (%s)\
does not exist in bpython.keys' % key)

    def __setitem__(self, key, value):
        self.map[key] = value

key_dispatch = KeyMap()

# fill dispatch with letters
for c in string.ascii_lowercase:
    key_dispatch['C-%s' % c] = (chr(string.ascii_lowercase.index(c) + 1),
                                '^%s' % c.upper())

# fill dispatch with cool characters
key_dispatch['C-['] = (chr(27), '^[')
key_dispatch['C-\\'] = (chr(28), '^\\')
key_dispatch['C-]'] = (chr(29), '^]')
key_dispatch['C-^'] = (chr(30), '^^')
key_dispatch['C-_'] = (chr(31), '^_')

# fill dispatch with function keys
for x in xrange(1, 13):
    key_dispatch['F%s' % str(x)] = ('KEY_F(%s)' % str(x),)
