from __future__ import unicode_literals, print_function, absolute_import
"""An example bpython repl without a nice UI for testing and to demonstrate
the methods of bpython.curtsiesrepl.repl.BaseRepl that must be overridden.
"""

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
            self.my_print('please refresh in '+str(round(when - time.time(), 1))+' seconds')

    def _request_reload(self, files_modified=('?',)):
        e = bpythonevents.ReloadEvent()
        e.files_modified = files_modified
        self.requested_events.append(e)
        self.my_print('please hit enter to trigger a refresh')

    def request_undo(self, n=1):
        self.requested_events.append(bpythonevents.UndoEvent(n=n))

    def my_print(self, msg):
        if hasattr(self, 'orig_stdout'):
            self.orig_stdout.write((msg+'\n').encode('utf8'))
            self.orig_stdout.flush()
        else:
            print(msg)

    def on_suspend(self):
        pass

    def after_suspend(self):
        self.my_print('please hit enter to trigger a refresh')

    def print_output(self):
        arr, cpos = self.paint()
        arr[cpos[0]:cpos[0]+1, cpos[1]:cpos[1]+1] = ['~']

        self.my_print('X'*(self.width+8))
        self.my_print(' enter -> "/", rewind -> "\\", '.center(self.width+8, 'X'))
        self.my_print(' reload -> "|", pastebin -> "$", '.center(self.width+8, 'X'))
        self.my_print(' "~" is the cursor '.center(self.width+8, 'X'))
        self.my_print('X'*(self.width+8))
        self.my_print('X``'+('`'*(self.width+2))+'``X')
        for line in arr:
            self.my_print('X```'+unicode(line.ljust(self.width))+'```X')
        logger.debug('line:')
        logger.debug(repr(line))
        self.my_print('X``'+('`'*(self.width+2))+'``X')
        self.my_print('X'*(self.width+8))
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
