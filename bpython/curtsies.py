from __future__ import absolute_import

import sys
import os
from optparse import Option

import curtsies
import curtsies.window
import curtsies.terminal
import curtsies.events
Window = curtsies.window.Window
Terminal = curtsies.terminal.Terminal

from bpython.curtsiesfrontend.repl import Repl
from bpython.curtsiesfrontend.coderunner import SystemExitFromCodeThread
from bpython import args as bpargs
from bpython.translations import _

def main(args=None, locals_=None, banner=None):
    config, options, exec_args = bpargs.parse(args, (
        'scroll options', None, [
            Option('--log', '-L', action='store_true',
                help=_("log debug messages to scroll.log")),
            Option('--type', '-t', action='store_true',
                help=_("enter lines of file as though interactively typed")),
            ]))
    if options.log:
        import logging
        logging.basicConfig(filename='scroll.log', level=logging.DEBUG)

    # do parsing before doing any frontend stuff
    with Terminal(paste_mode=True) as tc:
        with Window(tc, keep_last_line=True, hide_cursor=False) as term:
            #TODO why need to make repl first
            with Repl(config=config,
                      locals_=locals_,
                      stuff_a_refresh_request=tc.stuff_a_refresh_request,
                      banner=banner) as repl:
                rows, columns = tc.get_screen_size()
                repl.width = columns
                repl.height = rows

                def process_event(e):
                    try:
                        repl.process_event(e)
                    except SystemExitFromCodeThread:
                        #Get rid of nasty constant
                        array, cursor_pos = repl.paint(about_to_exit=2)
                        term.render_to_terminal(array, cursor_pos)
                        raise
                    except SystemExit:
                        array, cursor_pos = repl.paint(about_to_exit=True)
                        term.render_to_terminal(array, cursor_pos)
                        raise
                    else:
                        array, cursor_pos = repl.paint()
                        scrolled = term.render_to_terminal(array, cursor_pos)
                        repl.scroll_offset += scrolled
                        # Could this be calculated in the repl, avoiding this
                        # two-way communication?

                exit_value = 0
                if exec_args:
                    assert options, "don't pass in exec_args without options"
                    if options.type:
                        repl.process_event(tc.get_event()) #first event will always be a window size set
                        paste = curtsies.events.PasteEvent()
                        old_argv, sys.argv = sys.argv, exec_args
                        paste.events.extend(open(exec_args[0]).read())
                        sys.path.insert(0, os.path.abspath(os.path.dirname(exec_args[0])))
                        process_event(paste)
                    else:
                        try:
                            # THIS IS NORMAL PYTHON
                            #TODO replace this so that stdout is properly harvested for display and rewind works
                            bpargs.exec_code(repl.interp, exec_args)
                        except SystemExit, e:
                            exit_value = e.args
                        if not options.interactive:
                            #TODO treat this properly: no prompt should ever display, but stdout should!
                            array, cursor_pos = repl.paint(about_to_exit=True)
                            term.render_to_terminal(array, cursor_pos)
                            raise SystemExit(exit_value)
                else:
                    sys.path.insert(0, '') # expected for interactive sessions (python does it)

                while True:
                    process_event(tc.get_event())


if __name__ == '__main__':
    sys.exit(main())
