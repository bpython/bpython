# The MIT License
#
# Copyright (c) 2009 Andreas Stuehrk
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


import curses
import errno
import os
import subprocess
import sys


def get_pager_command():
    command = os.environ.get('PAGER')
    return command


def page_internal(data):
    """A more than dumb pager function."""
    sys.stdout.write(data)


def page(data, use_internal=False):
    command = get_pager_command()
    if not command or use_internal:
        page_internal(data)
    else:
        curses.endwin()
        popen = subprocess.Popen([command], stdin=subprocess.PIPE)
        try:
            popen.stdin.write(data)
            popen.stdin.close()
        except OSError, e:
            if e.errno != errno.EPIPE:
                raise
        popen.wait()
        curses.doupdate()
