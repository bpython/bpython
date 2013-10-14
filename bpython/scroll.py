from fmtstr.terminal import Terminal
from fmtstr.terminalcontrol import TerminalController

from bpython.scrollfrontend.repl import Repl

import sys
if '-v' in sys.argv:
    import logging
    logging.basicConfig(filename='scroll.log', level=logging.DEBUG)

def main():
    with TerminalController() as tc:
        with Terminal(tc, keep_last_line=True, hide_cursor=False) as term:
            with Repl() as repl:
                rows, columns = tc.get_screen_size()
                repl.width = columns
                repl.height = rows
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
    main()
