# encoding: utf-8

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


try:
    import fcntl
    has_fcntl = True
except ImportError:
    has_fcntl = False


class FileLock(object):
    """Simple file locking

    On platforms without fcntl, all operations in this class are no-ops.
    """

    def __init__(self, fd, mode=None):
        if has_fcntl and mode is None:
            mode = fcntl.LOCK_EX

        self.fd = fd
        self.mode = mode

    def __enter__(self):
        if has_fcntl:
            fcntl.flock(self.fd, self.mode)
        return self

    def __exit__(self, *args):
        if has_fcntl:
            fcntl.flock(self.fd, fcntl.LOCK_UN)

# vim: sw=4 ts=4 sts=4 ai et
