from __future__ import absolute_import

import sys
import code
from optparse import Option

import curtsies
import curtsies.window
import curtsies.input
import curtsies.terminal
import curtsies.events

from bpython.curtsiesfrontend.repl import Repl
from bpython.curtsiesfrontend.coderunner import SystemExitFromCodeGreenlet
from bpython import args as bpargs
from bpython.translations import _
from bpython.importcompletion import find_iterator

def main(args=None, locals_=None, banner=None):
    config, options, exec_args = bpargs.parse(args, (
        'scroll options', None, [
            Option('--log', '-L', action='store_true',
                help=_("log debug messages to bpython-curtsies.log")),
            Option('--type', '-t', action='store_true',
                help=_("enter lines of file as though interactively typed")),
            ]))
    if options.log:
        import logging
        logging.basicConfig(filename='scroll.log', level=logging.DEBUG)

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

    mainloop(config, locals_, banner, interp, paste)

def mainloop(config, locals_, banner, interp=None, paste=None):
    with curtsies.input.Input(keynames='curses') as input_generator:
        with curtsies.window.CursorAwareWindow(
                sys.stdout,
                sys.stdin,
                keep_last_line=True,
                hide_cursor=False) as window:

            refresh_requests = []
            def request_refresh():
                refresh_requests.append(curtsies.events.RefreshRequestEvent())
            def event_or_refresh():
                while True:
                    if refresh_requests:
                        yield refresh_requests.pop()
                    else:
                        yield input_generator.next()

            with Repl(config=config,
                      locals_=locals_,
                      request_refresh=request_refresh,
                      get_term_wh=window.get_term_wh,
                      get_cursor_vertical_diff=window.get_cursor_vertical_diff,
                      banner=banner,
                      interp=interp) as repl:
                repl.height, repl.width = window.t.height, window.t.width

                def process_event(e):
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

                [None for _ in find_iterator] #TODO get idle events working (instead of this)
                refresh_requests.append(None) #priming the pump (do a display before waiting for first event) 
                for e in event_or_refresh():
                    process_event(e)

if __name__ == '__main__':
    sys.exit(main())
