# The MIT License
#
# Copyright (c) 2015 the bpython authors.
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

import pydoc

import bpython._internal
from bpython._py3compat import py3
from bpython.repl import getpreferredencoding


class NopPydocPager(object):
    def __enter__(self):
        self._orig_pager = pydoc.pager
        pydoc.pager = self

    def __exit__(self, *args):
        pydoc.pager = self._orig_pager

    def __call__(self, text):
        return None


class _Helper(bpython._internal._Helper):

    def __init__(self, repl=None):
        self._repl = repl
        pydoc.pager = self.pager

        super(_Helper, self).__init__()

    def pager(self, output):
        if not py3 and isinstance(output, str):
            output = output.decode(getpreferredencoding())
        self._repl.pager(output)

    def __call__(self, *args, **kwargs):
        if self._repl.reevaluating:
            with NopPydocPager():
                return super(_Helper, self).__call__(*args, **kwargs)
        else:
            return super(_Helper, self).__call__(*args, **kwargs)

# vim: sw=4 ts=4 sts=4 ai et
