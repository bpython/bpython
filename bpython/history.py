# encoding: utf-8

# The MIT License
#
# Copyright (c) 2009 the bpython authors.
# Copyright (c) 2012,2015 Sebastian Ramacher
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

from __future__ import unicode_literals, absolute_import
import io
import os
import stat
from itertools import islice
from six.moves import range

from .translations import _
from .filelock import FileLock


class History(object):
    """Stores readline-style history and current place in it"""

    def __init__(self, entries=None, duplicates=True, hist_size=100):
        if entries is None:
            self.entries = ['']
        else:
            self.entries = list(entries)
        # how many lines back in history is currently selected where 0 is the
        # saved typed line, 1 the prev entered line
        self.index = 0
        # what was on the prompt before using history
        self.saved_line = ''
        self.duplicates = duplicates
        self.hist_size = hist_size

    def append(self, line):
        self.append_to(self.entries, line)

    def append_to(self, entries, line):
        line = line.rstrip('\n')
        if line:
            if not self.duplicates:
                # remove duplicates
                try:
                    while True:
                        entries.remove(line)
                except ValueError:
                    pass
            entries.append(line)

    def first(self):
        """Move back to the beginning of the history."""
        if not self.is_at_end:
            self.index = len(self.entries)
        return self.entries[-self.index]

    def back(self, start=True, search=False, target=None,
             include_current=False):
        """Move one step back in the history."""
        if target is None:
            target = self.saved_line
        if not self.is_at_end:
            if search:
                self.index += self.find_partial_match_backward(target,
                                                               include_current)
            elif start:
                self.index += self.find_match_backward(target, include_current)
            else:
                self.index += 1
        return self.entry

    @property
    def entry(self):
        """The current entry, which may be the saved line"""
        return self.entries[-self.index] if self.index else self.saved_line

    @property
    def entries_by_index(self):
        return list(reversed(self.entries + [self.saved_line]))

    def find_match_backward(self, search_term, include_current=False):
        add = 0 if include_current else 1
        start = self.index + add
        for idx, val in enumerate(islice(self.entries_by_index, start, None)):
            if val.startswith(search_term):
                return idx + add
        return 0

    def find_partial_match_backward(self, search_term, include_current=False):
        add = 0 if include_current else 1
        start = self.index + add
        for idx, val in enumerate(islice(self.entries_by_index, start, None)):
            if search_term in val:
                return idx + add
        return 0

    def forward(self, start=True, search=False, target=None,
                include_current=False):
        """Move one step forward in the history."""
        if target is None:
            target = self.saved_line
        if self.index > 1:
            if search:
                self.index -= self.find_partial_match_forward(target,
                                                              include_current)
            elif start:
                self.index -= self.find_match_forward(target, include_current)
            else:
                self.index -= 1
            return self.entry
        else:
            self.index = 0
            return self.saved_line

    def find_match_forward(self, search_term, include_current=False):
        add = 0 if include_current else 1
        end = max(0, self.index - (1 - add))
        for idx in range(end):
            val = self.entries_by_index[end - 1 - idx]
            if val.startswith(search_term):
                return idx + (0 if include_current else 1)
        return self.index

    def find_partial_match_forward(self, search_term, include_current=False):
        add = 0 if include_current else 1
        end = max(0, self.index - (1 - add))
        for idx in range(end):
            val = self.entries_by_index[end - 1 - idx]
            if search_term in val:
                return idx + add
        return self.index

    def last(self):
        """Move forward to the end of the history."""
        if not self.is_at_start:
            self.index = 0
        return self.entries[0]

    @property
    def is_at_end(self):
        return self.index >= len(self.entries) or self.index == -1

    @property
    def is_at_start(self):
        return self.index == 0

    def enter(self, line):
        if self.index == 0:
            self.saved_line = line

    def reset(self):
        self.index = 0
        self.saved_line = ''

    def load(self, filename, encoding):
        with io.open(filename, 'r', encoding=encoding,
                     errors='ignore') as hfile:
            with FileLock(hfile):
                self.entries = self.load_from(hfile)

    def load_from(self, fd):
        entries = []
        for line in fd:
            self.append_to(entries, line)
        return entries if len(entries) else ['']

    def save(self, filename, encoding, lines=0):
        fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.TRUNC,
                     stat.S_IRUSR | stat.S_IWUSR)
        with io.open(fd, 'w', encoding=encoding,
                     errors='ignore') as hfile:
            with FileLock(hfile):
                self.save_to(hfile, self.entries, lines)

    def save_to(self, fd, entries=None, lines=0):
        if entries is None:
            entries = self.entries
        for line in entries[-lines:]:
            fd.write(line)
            fd.write('\n')

    def append_reload_and_write(self, s, filename, encoding):
        if not self.hist_size:
            return self.append(s)

        try:
            fd = os.open(filename, os.O_APPEND | os.O_RDWR | os.O_CREAT,
                         stat.S_IRUSR | stat.S_IWUSR)
            with io.open(fd, 'a+', encoding=encoding,
                         errors='ignore') as hfile:
                with FileLock(hfile):
                    # read entries
                    hfile.seek(0, os.SEEK_SET)
                    entries = self.load_from(hfile)
                    self.append_to(entries, s)

                    # write new entries
                    hfile.seek(0, os.SEEK_SET)
                    hfile.truncate()
                    self.save_to(hfile, entries, self.hist_size)

                    self.entries = entries
        except EnvironmentError as err:
            raise RuntimeError(
                _('Error occurred while writing to file %s (%s)')
                % (filename, err.strerror))
        else:
            if len(self.entries) == 0:
                # Make sure that entries contains at least one element. If the
                # file and s are empty, this can occur.
                self.entries = ['']
