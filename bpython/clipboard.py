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

from __future__ import absolute_import

import subprocess
import os
import platform
from locale import getpreferredencoding


class CopyFailed(Exception):
    pass


class XClipboard(object):
    """Manage clipboard with xclip."""

    def copy(self, content):
        process = subprocess.Popen(
            ["xclip", "-i", "-selection", "clipboard"], stdin=subprocess.PIPE
        )
        process.communicate(content.encode(getpreferredencoding()))
        if process.returncode != 0:
            raise CopyFailed()


class OSXClipboard(object):
    """Manage clipboard with pbcopy."""

    def copy(self, content):
        process = subprocess.Popen(["pbcopy", "w"], stdin=subprocess.PIPE)
        process.communicate(content.encode(getpreferredencoding()))
        if process.returncode != 0:
            raise CopyFailed()


def command_exists(command):
    process = subprocess.Popen(
        ["which", command], stderr=subprocess.STDOUT, stdout=subprocess.PIPE
    )
    process.communicate()

    return process.returncode == 0


def get_clipboard():
    """Get best clipboard handling implementation for current system."""

    if platform.system() == "Darwin":
        if command_exists("pbcopy"):
            return OSXClipboard()
    if (
        platform.system() in ("Linux", "FreeBSD", "OpenBSD")
        and os.getenv("DISPLAY") is not None
    ):
        if command_exists("xclip"):
            return XClipboard()

    return None
