from __future__ import absolute_import

import sys
import code
import logging
from optparse import Option

import curtsies
import curtsies.window
import curtsies.terminal
import curtsies.events
Window = curtsies.window.Window
Terminal = curtsies.terminal.Terminal

from bpython.curtsiesfrontend.repl import Repl
from bpython.curtsiesfrontend.coderunner import SystemExitFromCodeGreenlet
from bpython import args as bpargs
from bpython.translations import _
from bpython.importcompletion import find_iterator

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

    mainloop(config, locals_, banner, interp, paste)

def mainloop(config, locals_, banner, interp=None, paste=None):
    with Terminal(paste_mode=True) as tc:
        with Window(tc, keep_last_line=True, hide_cursor=False) as term:
            with Repl(config=config,
                      locals_=locals_,
                      request_refresh=tc.stuff_a_refresh_request,
                      banner=banner,
                      interp=interp) as repl:
                rows, columns = tc.get_screen_size()
                repl.width = columns
                repl.height = rows

                def process_event(e):
                    try:
                        repl.process_event(e)
                    except (SystemExitFromCodeGreenlet, SystemExit) as err:
                        array, cursor_pos = repl.paint(about_to_exit=True, user_quit=isinstance(err, SystemExitFromCodeGreenlet))
                        scrolled = term.render_to_terminal(array, cursor_pos)
                        repl.scroll_offset += scrolled
                        raise
                    else:
                        array, cursor_pos = repl.paint()
                        scrolled = term.render_to_terminal(array, cursor_pos)
                        repl.scroll_offset += scrolled

                if paste:
                    repl.process_event(term.get_annotated_event()) #first event will always be a window size set
                    process_event(paste)

                while True:
                    process_event(term.get_annotated_event(idle=find_iterator))

if __name__ == '__main__':
    sys.exit(main())
