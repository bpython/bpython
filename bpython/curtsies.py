from __future__ import absolute_import

import collections
import io
import logging
import sys
from optparse import Option

import curtsies
import curtsies.window
import curtsies.input
import curtsies.events

from bpython.curtsiesfrontend.repl import BaseRepl
from bpython.curtsiesfrontend.coderunner import SystemExitFromCodeGreenlet
from bpython.curtsiesfrontend.interpreter import Interp
from bpython import args as bpargs
from bpython import translations
from bpython.translations import _
from bpython.importcompletion import find_iterator
from bpython.curtsiesfrontend import events as bpythonevents
from bpython import inspection
from bpython.repl import extract_exit_value

logger = logging.getLogger(__name__)


repl = None  # global for `from bpython.curtsies import repl`
# WARNING Will be a problem if more than one repl is ever instantiated this way


class FullCurtsiesRepl(BaseRepl):
    def __init__(self, config, locals_, banner, interp=None,
                 paste=None):
        self.input_generator = curtsies.input.Input(
            keynames='curtsies',
            sigint_event=True,
            paste_threshold=None)
        self.window = curtsies.window.CursorAwareWindow(
            sys.stdout,
            sys.stdin,
            keep_last_line=True,
            hide_cursor=False,
            extra_bytes_callback=self.input_generator.unget_bytes)

        self._request_refresh = self.input_generator.event_trigger(
            bpythonevents.RefreshRequestEvent)
        self._schedule_refresh = self.input_generator.scheduled_event_trigger(
            bpythonevents.ScheduledRefreshRequestEvent)
        self._request_reload = self.input_generator.threadsafe_event_trigger(
            bpythonevents.ReloadEvent)
        self.interrupting_refresh = (self.input_generator
                                     .threadsafe_event_trigger(lambda: None))
        self.request_undo = self.input_generator.event_trigger(
            bpythonevents.UndoEvent)

        with self.input_generator:
            pass  # temp hack to get .original_stty

        BaseRepl.__init__(self,
                          locals_=locals_,
                          config=config,
                          banner=banner,
                          interp=interp,
                          orig_tcattrs=self.input_generator.original_stty)

    def get_term_hw(self):
        return self.window.get_term_hw()

    def get_cursor_vertical_diff(self):
        return self.window.get_cursor_vertical_diff()

    def get_top_usable_line(self):
        return self.window.top_usable_row

    def on_suspend(self):
        self.window.__exit__(None, None, None)
        self.input_generator.__exit__(None, None, None)

    def after_suspend(self):
        self.input_generator.__enter__()
        self.window.__enter__()
        self.interrupting_refresh()

    def process_event_and_paint(self, e):
        """If None is passed in, just paint the screen"""
        try:
            if e is not None:
                self.process_event(e)
        except (SystemExitFromCodeGreenlet, SystemExit) as err:
            array, cursor_pos = self.paint(
                about_to_exit=True,
                user_quit=isinstance(err,
                                     SystemExitFromCodeGreenlet))
            scrolled = self.window.render_to_terminal(array, cursor_pos)
            self.scroll_offset += scrolled
            raise
        else:
            array, cursor_pos = self.paint()
            scrolled = self.window.render_to_terminal(array, cursor_pos)
            self.scroll_offset += scrolled

    def mainloop(self, interactive=True, paste=None):
        if interactive:
            # Add custom help command
            # TODO: add methods to run the code
            self.initialize_interp()

            # run startup file
            self.process_event(bpythonevents.RunStartupFileEvent())

        # handle paste
        if paste:
            self.process_event(paste)

        # do a display before waiting for first event
        self.process_event_and_paint(None)
        inputs = combined_events(self.input_generator)
        for unused in find_iterator:
            e = inputs.send(0)
            if e is not None:
                self.process_event_and_paint(e)

        for e in inputs:
            self.process_event_and_paint(e)


def main(args=None, locals_=None, banner=None, welcome_message=None):
    """
    banner is displayed directly after the version information.
    welcome_message is passed on to Repl and displayed in the statusbar.
    """
    translations.init()

    config, options, exec_args = bpargs.parse(args, (
        'curtsies options', None, [
            Option('--log', '-L', action='count',
                   help=_("log debug messages to bpython.log")),
            Option('--paste', '-p', action='store_true',
                   help=_("start by pasting lines of a file into session")),
            ]))
    if options.log is None:
        options.log = 0
    logging_levels = [logging.ERROR, logging.INFO, logging.DEBUG]
    level = logging_levels[min(len(logging_levels) - 1, options.log)]
    logging.getLogger('curtsies').setLevel(level)
    logging.getLogger('bpython').setLevel(level)
    if options.log:
        handler = logging.FileHandler(filename='bpython.log')
        logging.getLogger('curtsies').addHandler(handler)
        logging.getLogger('curtsies').propagate = False
        logging.getLogger('bpython').addHandler(handler)
        logging.getLogger('bpython').propagate = False

    interp = None
    paste = None
    if exec_args:
        if not options:
            raise ValueError("don't pass in exec_args without options")
        exit_value = ()
        if options.paste:
            paste = curtsies.events.PasteEvent()
            encoding = inspection.get_encoding_file(exec_args[0])
            with io.open(exec_args[0], encoding=encoding) as f:
                sourcecode = f.read()
            paste.events.extend(sourcecode)
        else:
            try:
                interp = Interp(locals=locals_)
                bpargs.exec_code(interp, exec_args)
            except SystemExit as e:
                exit_value = e.args
            if not options.interactive:
                return extract_exit_value(exit_value)
    else:
        # expected for interactive sessions (vanilla python does it)
        sys.path.insert(0, '')

    if not options.quiet:
        print(bpargs.version_banner())
    if banner is not None:
        print(banner)
    global repl
    repl = FullCurtsiesRepl(config, locals_, welcome_message, interp, paste)
    try:
        with repl.input_generator:
            with repl.window as win:
                with repl:
                    repl.height, repl.width = win.t.height, win.t.width
                    exit_value = repl.mainloop()
    except (SystemExitFromCodeGreenlet, SystemExit) as e:
        exit_value = e.args
    return extract_exit_value(exit_value)


def _combined_events(event_provider, paste_threshold):
    """Combines consecutive keypress events into paste events."""
    timeout = yield 'nonsense_event'  # so send can be used immediately
    queue = collections.deque()
    while True:
        e = event_provider.send(timeout)
        if isinstance(e, curtsies.events.Event):
            timeout = yield e
            continue
        elif e is None:
            timeout = yield None
            continue
        else:
            queue.append(e)
        e = event_provider.send(0)
        while not (e is None or isinstance(e, curtsies.events.Event)):
            queue.append(e)
            e = event_provider.send(0)
        if len(queue) >= paste_threshold:
            paste = curtsies.events.PasteEvent()
            paste.events.extend(queue)
            queue.clear()
            timeout = yield paste
        else:
            while len(queue):
                timeout = yield queue.popleft()


def combined_events(event_provider, paste_threshold=3):
    g = _combined_events(event_provider, paste_threshold)
    next(g)
    return g


if __name__ == '__main__':
    sys.exit(main())
