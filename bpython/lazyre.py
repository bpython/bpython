# The MIT License
#
# Copyright (c) 2015 Sebastian Ramacher
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

import re


class LazyReCompile(object):
    """Compile regular expressions on first use

    This class allows to store regular expressions and compiles them on first
    use."""

    def __init__(self, regex, flags=0):
        self.regex = regex
        self.flags = flags
        self.compiled = None

    def compile_regex(method):
        def _impl(self, *args, **kwargs):
            if self.compiled is None:
                self.compiled = re.compile(self.regex, self.flags)
            return method(self, *args, **kwargs)
        return _impl

    @compile_regex
    def finditer(self, *args, **kwargs):
        return self.compiled.finditer(*args, **kwargs)

    @compile_regex
    def search(self, *args, **kwargs):
        return self.compiled.search(*args, **kwargs)

    @compile_regex
    def match(self, *args, **kwargs):
        return self.compiled.match(*args, **kwargs)

    @compile_regex
    def sub(self, *args, **kwargs):
        return self.compiled.sub(*args, **kwargs)
