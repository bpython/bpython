import sys

from fmtstr.terminal import Terminal
from fmtstr.terminalcontrol import TerminalController

from bpython.scrollfrontend.repl import Repl
import bpython.args

if '-v' in sys.argv:
    import logging
    logging.basicConfig(filename='scroll.log', level=logging.DEBUG)
    sys.argv.remove('-v')

def cli():
    config, options, exec_args = bpython.args.parse(args=None)
    return main(config=config, options=options, exec_args=exec_args)

def main(locals_=None, config=None, exec_args=None, options=None):
    #TODO this is gross - passing in args and options means you can't
    # easily have that functionality without running it frmo the command line,
    # but it makes reusing bpython code easier

    with TerminalController() as tc:
        with Terminal(tc, keep_last_line=True, hide_cursor=False) as term:
            with Repl(config=config, locals_=locals_) as repl:
                rows, columns = tc.get_screen_size()
                repl.width = columns
                repl.height = rows

                exit_value = 0
                if exec_args:
                    assert options, "don't pass in exec_args without options"
                    try:
                        #TODO replace this so that stdout is properly harvested for display!
                        bpython.args.exec_code(repl.interp, exec_args)
                    except SystemExit:
                        pass
                    if not options.interactive:
                        #TODO treat this properly: no prompt should ever display, but stdout should!
                        array, cursor_pos = repl.paint(about_to_exit=True)
                        term.render_to_terminal(array, cursor_pos)
                        raise SystemExit(exit_value)

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
    sys.exit(cli())
