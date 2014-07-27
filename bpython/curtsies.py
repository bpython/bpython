from __future__ import absolute_import

import sys
import code
import logging
from optparse import Option
from itertools import izip

import curtsies
import curtsies.window
import curtsies.input
import curtsies.events

from bpython.curtsiesfrontend.repl import Repl
from bpython.curtsiesfrontend.coderunner import SystemExitFromCodeGreenlet
from bpython import args as bpargs
from bpython.translations import _
from bpython.importcompletion import find_iterator

repl = None # global for `from bpython.curtsies import repl`
#WARNING Will be a problem if more than one repl is ever instantiated this way

def main(args=None, locals_=None, banner=None):
    config, options, exec_args = bpargs.parse(args, (
        'scroll options', None, [
            Option('--log', '-L', action='store_true',
                help=_("log debug messages to bpython.log")),
            Option('--type', '-t', action='store_true',
                help=_("enter lines of file as though interactively typed")),
            ]))
    if options.log:
        handler = logging.FileHandler(filename='bpython.log')
        logging.getLogger('curtsies').setLevel(logging.DEBUG)
        logging.getLogger('curtsies').addHandler(handler)
        logging.getLogger('curtsies').propagate = False
        logging.getLogger('bpython').setLevel(logging.DEBUG)
        logging.getLogger('bpython').addHandler(handler)
        logging.getLogger('bpython').propagate = False
    else:
        logging.getLogger('bpython').setLevel(logging.WARNING)

    interp = None
    paste = None
    if exec_args:
        assert options, "don't pass in exec_args without options"
        exit_value = 0
        if options.type:
            paste = curtsies.events.PasteEvent()
            sourcecode = open(exec_args[0]).read()
            paste.events.extend(sourcecode)
        else:
            try:
                interp = code.InteractiveInterpreter(locals=locals_)
                bpargs.exec_code(interp, exec_args)
            except SystemExit, e:
                exit_value = e.args
            if not options.interactive:
                raise SystemExit(exit_value)
    else:
        sys.path.insert(0, '') # expected for interactive sessions (vanilla python does it)


    mainloop(config, locals_, banner, interp, paste, interactive=(not exec_args))

def mainloop(config, locals_, banner, interp=None, paste=None, interactive=True):
    with curtsies.input.Input(keynames='curtsies', sigint_event=True) as input_generator:
        with curtsies.window.CursorAwareWindow(
                sys.stdout,
                sys.stdin,
                keep_last_line=True,
                hide_cursor=False,
                extra_bytes_callback=input_generator.unget_bytes) as window:

            refresh_requests = []
            def request_refresh():
                refresh_requests.append(curtsies.events.RefreshRequestEvent())
            def event_or_refresh(timeout=None):
                while True:
                    if refresh_requests:
                        yield refresh_requests.pop()
                    else:
                        yield input_generator.send(timeout)

            global repl # global for easy introspection `from bpython.curtsies import repl`
            with Repl(config=config,
                      locals_=locals_,
                      request_refresh=request_refresh,
                      get_term_hw=window.get_term_hw,
                      get_cursor_vertical_diff=window.get_cursor_vertical_diff,
                      banner=banner,
                      interp=interp,
                      interactive=interactive,
                      orig_tcattrs=input_generator.original_stty) as repl:
                repl.height, repl.width = window.t.height, window.t.width

                def process_event(e):
                    """If None is passed in, just paint the screen"""
                    try:
                        if e is not None:
                            repl.process_event(e)
                    except (SystemExitFromCodeGreenlet, SystemExit) as err:
                        array, cursor_pos = repl.paint(about_to_exit=True, user_quit=isinstance(err, SystemExitFromCodeGreenlet))
                        scrolled = window.render_to_terminal(array, cursor_pos)
                        repl.scroll_offset += scrolled
                        raise
                    else:
                        array, cursor_pos = repl.paint()
                        scrolled = window.render_to_terminal(array, cursor_pos)
                        repl.scroll_offset += scrolled

                if paste:
                    process_event(paste)

                process_event(None) #priming the pump (do a display before waiting for first event) 
                for _, e in izip(find_iterator, event_or_refresh(0)):
                    if e is not None:
                        process_event(e)
                for e in event_or_refresh():
                    process_event(e)

if __name__ == '__main__':
    sys.exit(main())
