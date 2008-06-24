import pydoc
import textwrap
import sys

# window has to be a global so that the main bpython.py can load it and
# alter its state and share it with the interpreter being used for the
# actual user input, I couldn't think of another way of doing this.
window = None

def _help( query ):
    """Wrapper for the regular help() function but with a ghetto
    PAGER since curses + less = :(
    """
    doc = pydoc.TextDoc()
    rows, columns = window.getmaxyx()
    rows -= 3
    columns -= 1
    output = doc.document( query )
    if not output:
        output = "No help found for %s" % query

    output = output.replace('\t', '    ')

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
# This is a little unclear, but it just waits for a
# keypress when the a page worth of text has been
# displayed and returns if 'q' is pressed:
            if not i % rows and not wait_for_key():
                return

def wait_for_key():
    """Block until a key is pressed for the ghetto paging."""

    q = True
    window.addstr("Press any key, q to cancel.")
    while True:
        c = window.getch()
        if c and c == ord('q'):
            q = False
        if c:
            break
    clear_line()
    return q

def clear_line():
    y = window.getyx()[0]
    window.move(y, 0)
    window.clrtoeol()
