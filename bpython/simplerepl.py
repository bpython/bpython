# encoding: utf-8

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
"""An example bpython repl without a nice UI for testing and to demonstrate
the methods of bpython.curtsiesrepl.repl.BaseRepl that must be overridden.
"""

from __future__ import unicode_literals, print_function, absolute_import

import time
import logging

from bpython.curtsiesfrontend.repl import BaseRepl
from bpython.curtsiesfrontend import events as bpythonevents
from bpython import translations
from bpython import importcompletion

from curtsies.configfile_keynames import keymap as key_dispatch


logger = logging.getLogger(__name__)


class SimpleRepl(BaseRepl):
    def __init__(self):
        self.requested_events = []
        BaseRepl.__init__(self)

    def _request_refresh(self):
        self.requested_events.append(bpythonevents.RefreshRequestEvent())

    def _schedule_refresh(self, when='now'):
        if when == 'now':
            self.request_refresh()
        else:
            dt = round(when - time.time(), 1)
            self.out('please refresh in {} seconds'.format(dt))

    def _request_reload(self, files_modified=('?',)):
        e = bpythonevents.ReloadEvent()
        e.files_modified = files_modified
        self.requested_events.append(e)
        self.out('please hit enter to trigger a refresh')

    def request_undo(self, n=1):
        self.requested_events.append(bpythonevents.UndoEvent(n=n))

    def out(self, msg):
        if hasattr(self, 'orig_stdout'):
            self.orig_stdout.write((msg + '\n').encode('utf8'))
            self.orig_stdout.flush()
        else:
            print(msg)

    def on_suspend(self):
        pass

    def after_suspend(self):
        self.out('please hit enter to trigger a refresh')

    def print_output(self):
        arr, cpos = self.paint()
        arr[cpos[0]:cpos[0] + 1, cpos[1]:cpos[1] + 1] = ['~']

        def print_padded(s):
            return self.out(s.center(self.width + 8, 'X'))

        print_padded('')
        print_padded(' enter -> "/", rewind -> "\\", ')
        print_padded(' reload -> "|", pastebin -> "$", ')
        print_padded(' "~" is the cursor ')
        print_padded('')
        self.out('X``' + ('`' * (self.width + 2)) + '``X')
        for line in arr:
            self.out('X```' + unicode(line.ljust(self.width)) + '```X')
        logger.debug('line:')
        logger.debug(repr(line))
        self.out('X``' + ('`' * (self.width + 2)) + '``X')
        self.out('X' * (self.width + 8))
        return max(len(arr) - self.height, 0)

    def get_input(self):
        chars = list(self.orig_stdin.readline()[:-1])
        while chars or self.requested_events:
            if self.requested_events:
                self.process_event(self.requested_events.pop())
                continue
            c = chars.pop(0)
            if c in '/':
                c = '\n'
            elif c in '\\':
                c = key_dispatch[self.config.undo_key][0]
            elif c in '$':
                c = key_dispatch[self.config.pastebin_key][0]
            elif c in '|':
                c = key_dispatch[self.config.reimport_key][0]
            self.process_event(c)


def main(args=None, locals_=None, banner=None):
    translations.init()
    while importcompletion.find_coroutine():
        pass
    with SimpleRepl() as r:
        r.width = 50
        r.height = 10
        while True:
            r.print_output()
            r.get_input()


if __name__ == '__main__':
    main()
