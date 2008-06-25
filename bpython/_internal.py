import pydoc
import textwrap
import sys
import cStringIO

# window has to be a global so that the main bpython.py can load it and
# alter its state and share it with the interpreter being used for the
# actual user input, I couldn't think of another way of doing this.
window = None

def _help( obj ):
    """Wrapper for the regular help() function but with a ghetto
    PAGER since curses + less = :(
    As per the vanilla help(), this function special-cases for str,
    so you can do help('isinstance') or help(isinstance) and get the
    same result.
    """
    io = cStringIO.StringIO()
    doc = pydoc.TextDoc()
    helper = pydoc.Helper( None, io )

    rows, columns = window.getmaxyx()
    rows -= 3
    columns -= 1
    output = None

#   Copied and pasted from Lib/pydoc.py and fiddled with
#   so it works fine with bpython. As far as I can tell
#   the bpython help is no compliant with the vanilla help.
#   Please let me know if you find this to be untrue.
    if type(obj) is type(''):
        if obj == 'help': helper.intro()
        elif obj == 'keywords': helper.listkeywords()
        elif obj == 'topics': helper.listtopics()
        elif obj == 'modules': helper.listmodules()
        elif obj[:8] == 'modules ':
            helper.listmodules(split(obj)[1])
        elif obj in helper.keywords: helper.showtopic(obj)
        elif obj in helper.topics: helper.showtopic(obj)
        elif obj: output = doc.document( eval(obj) ) 
#######################

    else:
        output = doc.document( obj )
        if not output:
            output = "No help found for %s" % obj
            return

    if output is None:
        output = io.getvalue()
        io.close()

    if not output:
        return

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
