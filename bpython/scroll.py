import sys
from optparse import Option

from fmtstr.terminal import Terminal
from fmtstr.terminalcontrol import TerminalController

from bpython.scrollfrontend.repl import Repl
from bpython import args as bpargs
from bpython.translations import _

def main(args=None, locals_=None, banner=None):
    config, options, exec_args = bpargs.parse(args, (
        'scroll options', None, [
            Option('--log', '-L', action='store_true',
                help=_("log debug messages to scroll.log")),
            ]))
    if options.log:
        import logging
        logging.basicConfig(filename='scroll.log', level=logging.DEBUG)

    with TerminalController() as tc:
        with Terminal(tc, keep_last_line=True, hide_cursor=False) as term:
            with Repl(config=config,
                      locals_=locals_,
                      stuff_a_refresh_request=tc.stuff_a_refresh_request,
                      banner=banner) as repl:
                rows, columns = tc.get_screen_size()
                repl.width = columns
                repl.height = rows

                exit_value = 0
                if exec_args:
                    assert options, "don't pass in exec_args without options"
                    try:
                        #TODO replace this so that stdout is properly harvested for display!
                        bpargs.exec_code(repl.interp, exec_args)
                    except SystemExit, e:
                        exit_value = e.args
                    if not options.interactive:
                        #TODO treat this properly: no prompt should ever display, but stdout should!
                        array, cursor_pos = repl.paint(about_to_exit=True)
                        term.render_to_terminal(array, cursor_pos)
                        raise SystemExit(exit_value)
                else:
                    sys.path.insert(0, '')

                while True:
                    try:
                        repl.process_event(tc.get_event())
                    except SystemExit:
                        array, cursor_pos = repl.paint(about_to_exit=True)
                        term.render_to_terminal(array, cursor_pos)
                        raise
                    else:
                        array, cursor_pos = repl.paint()
                        scrolled = term.render_to_terminal(array, cursor_pos)
                        repl.scroll_offset += scrolled

if __name__ == '__main__':
    sys.exit(main())
