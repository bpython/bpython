# encoding: utf-8

# The MIT License
#
# Copyright (c) 2015-2019 Sebastian Ramacher
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

from __future__ import absolute_import

try:
    import fcntl
    import errno

    has_fcntl = True
except ImportError:
    has_fcntl = False

try:
    import msvcrt
    import os

    has_msvcrt = True
except ImportError:
    has_msvcrt = False


class BaseLock(object):
    """Base class for file locking
    """

    def __init__(self, fileobj, mode=None, filename=None):
        self.fileobj = fileobj
        self.locked = False

    def acquire(self):
        pass

    def release(self):
        pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        if self.locked:
            self.release()

    def __del__(self):
        if self.locked:
            self.release()


class UnixFileLock(BaseLock):
    """Simple file locking for Unix using fcntl
    """

    def __init__(self, fileobj, mode=None, filename=None):
        super(UnixFileLock, self).__init__(fileobj)

        if mode is None:
            mode = fcntl.LOCK_EX
        self.mode = mode

    def acquire(self):
        try:
            fcntl.flock(self.fileobj, self.mode)
            self.locked = True
        except IOError as e:
            if e.errno != errno.ENOLCK:
                raise e

    def release(self):
        self.locked = False
        fcntl.flock(self.fileobj, fcntl.LOCK_UN)


class WindowsFileLock(BaseLock):
    """Simple file locking for Windows using msvcrt
    """

    def __init__(self, fileobj, mode=None, filename=None):
        super(WindowsFileLock, self).__init__(None)
        self.filename = "{}.lock".format(filename)

    def acquire(self):
        # create a lock file and lock it
        self.fileobj = os.open(
            self.filename, os.O_RDWR | os.O_CREAT | os.O_TRUNC
        )
        msvcrt.locking(self.fileobj, msvcrt.LK_NBLCK, 1)

        self.locked = True

    def release(self):
        self.locked = False

        # unlock lock file and remove it
        msvcrt.locking(self.fileobj, msvcrt.LK_UNLCK, 1)
        os.close(self.fileobj)
        self.fileobj = None

        try:
            os.remove(self.filename)
        except OSError:
            pass


if has_fcntl:
    FileLock = UnixFileLock
elif has_msvcrt:
    FileLock = WindowsFileLock
else:
    FileLock = BaseLock

# vim: sw=4 ts=4 sts=4 ai et
