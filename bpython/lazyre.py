# The MIT License
#
# Copyright (c) 2015-2021 Sebastian Ramacher
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
import sys
from collections.abc import Callable, Iterator
from functools import cached_property
from re import Match, Pattern


class LazyReCompile:
    """Compile regular expressions on first use

    This class allows one to store regular expressions and compiles them on
    first use."""

    def __init__(self, regex: str, flags: int = 0) -> None:
        self.regex = regex
        self.flags = flags

    @cached_property
    def compiled(self) -> Pattern[str]:
        return re.compile(self.regex, self.flags)

    def finditer(
        self, string: str, pos: int = 0, endpos: int = sys.maxsize
    ) -> Iterator[Match[str]]:
        return self.compiled.finditer(string, pos, endpos)

    def search(
        self, string: str, pos: int = 0, endpos: int = sys.maxsize
    ) -> Match[str] | None:
        return self.compiled.search(string, pos, endpos)

    def match(
        self, string: str, pos: int = 0, endpos: int = sys.maxsize
    ) -> Match[str] | None:
        return self.compiled.match(string, pos, endpos)

    def sub(
        self,
        repl: str | Callable[[Match[str]], str],
        string: str,
        count: int = 0,
    ) -> str:
        return self.compiled.sub(repl, string, count)
