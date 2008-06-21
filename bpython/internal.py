import pydoc
import textwrap
import sys

window = None

def _help( query ):
    """Wrapper for the regular help() function but with a ghetto
    PAGER since curses + less = :(
    query : the actual search thing
    window : a curses window instance to use getch() on
            and for extrapolating the window size to work it all out"""

    rows, columns = window.getmaxyx()
    rows -= 3
    columns -= 1
    output = pydoc.getdoc( query )
    if '\n' in output:
        output = output.replace('\n\n', '\n')
        output = output.split('\n')
    else:
        output = [output]

    paragraphs = []
    for o in output:
        paragraphs.append( textwrap.wrap( o, columns ) )

    i = 0
    for j, paragraph in enumerate( paragraphs ):
        for line in paragraph:
            sys.stdout.write( line + '\n' )
            i += 1
            if not i % rows:
                wait_for_key( window )
        if j + 1 < len( paragraphs ):
            sys.stdout.write('\n ')

def wait_for_key( window ):
    """Block until a key is pressed for the ghetto paging."""

    window.addstr("Press any key...")
    while True:
        c = window.getch()
        if c:
            break

    y = window.getyx()[0]
    window.move(y-1, 0)
    window.clrtoeol()
