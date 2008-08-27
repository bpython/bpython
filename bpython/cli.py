#!/usr/bin/env python
# bpython 0.7.1::fancy curses interface to the Python repl::Bob Farrell 2008
#
# The MIT License
# 
# Copyright (c) 2008 Bob Farrell
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# Requires at least Python 2.4, pygments and pyparsing
# Debian/Ubuntu: aptitude install python-pyments python-pyparsing
#

import os
import sys
import curses
import code
import traceback
import re
import time
import urllib
import rlcompleter
import inspect
import signal
import struct
import termios
import fcntl
import string
import shlex
import pydoc
import cStringIO

# These are used for syntax hilighting.
from pygments import highlight
from pygments.lexers import PythonLexer
from bpython.formatter import BPythonFormatter

# And these are used for argspec.
from pyparsing import Forward, Suppress, QuotedString, dblQuotedString, \
    Group, OneOrMore, ZeroOrMore, Literal, Optional, Word, \
    alphas, alphanums, printables, ParseException

class Struct( object ):
    pass  # When we inherit, a __dict__ is added (object uses slots)

class FakeStdin(object):
    """Provide a fake stdin type for things like raw_input() etc."""

    def __init__(self, interface):
        """Take the curses Repl on init and assume it provides a get_key method
        which, fortunately, it does."""

        self.interface = interface

    def readline(self):
        """I can't think of any reason why anything other than readline would
        be useful in the context of an interactive interpreter so this is the
        only one I've done anything with. The others are just there in case
        someone does something weird to stop it from blowing up."""

        buffer = ''
        while True:
            key = self.interface.get_key()
            sys.stdout.write(key)
# Include the \n in the buffer - raw_input() seems to deal with trailing
# linebreaks and will break if it gets an empty string.
            buffer += key
            if key == '\n':
                break

        return buffer

    def read(self, x):
        pass

    def readlines(self, x):
        pass

OPTS = Struct()
DO_RESIZE = False


# Set default values. (Overridden by loadrc())
OPTS.tab_length = 4
OPTS.auto_display_list = True
OPTS.syntax = True
OPTS.arg_spec = True
OPTS.hist_file = '~/.pythonhist'
OPTS.hist_length = 100

# TODO:
#
# C-l doesn't repaint the screen yet.
#
# Tab completion does not work if not at the end of the line.
#
# Triple-quoted strings over multiple lines are not colourised correctly.
#
# Numerous optimisations can be made but it seems to do all the lookup stuff
# fast enough on even my crappy server so I'm not too bothered about that
# at the moment.
#
# The popup window that displays the argspecs and completion suggestions
# needs to be an instance of a ListWin class or something so I can wrap
# the addstr stuff to a higher level.
#
def DEBUG(s):
    """This shouldn't ever be called in any release of bpython, so
    beat me up if you find anything calling it."""
    open('/home/bob/tmp/plonker','a').write( "%s\n" % str( s )  )

def make_colours():
    """Init all the colours in curses and bang them into a dictionary"""

    for i in range( 63 ):
        if i > 7: j = i / 8
        else: j = -1
        curses.init_pair( i+1, i % 8, j )

    c = {}
    # blacK, Red, Green, Yellow, Blue, Magenta, Cyan, White, Default:
    c["k"] = 0
    c["r"] = 1
    c["g"] = 2
    c["y"] = 3
    c["b"] = 4
    c["m"] = 5
    c["c"] = 6
    c["w"] = 7
    c["d"] = -1
    
    return c
    
class Interpreter( code.InteractiveInterpreter ):
    def showtraceback( self ):
        """This needs to override the default traceback thing
        so it can put it into a pretty colour and maybe other
        stuff, I don't know"""

        try:
            t, v, tb = sys.exc_info()
            sys.last_type = t
            sys.last_value = v
            sys.last_traceback = tb
            tblist = traceback.extract_tb( tb )
            del tblist[:1]

            l = traceback.format_list( tblist )
            if l:
                l.insert( 0, "Traceback (most recent call last):\n" )
            l[len(l):] = traceback.format_exception_only( t, v )
        finally:
            tblist = tb = None
        
        self.writetb( l )

    def writetb( self, l ):
        """This outputs the traceback and should be overridden for anything
        fancy."""
        map( self.write, [ "\x01y\x03%s" % i for i in l ] )


class Repl( object ):
    """Implements the necessary guff for a Python-repl-alike interface
    
    The execution of the code entered and all that stuff was taken from the
    Python code module, I had to copy it instead of inheriting it, I can't
    remember why. The rest of the stuff is basically what makes it fancy.

    It reads what you type, passes it to a lexer and highlighter which
    returns a formatted string. This then gets passed to echo() which
    parses that string and prints to the curses screen in appropriate
    colours and/or bold attribute.
    
    The Repl class also keeps two stacks of lines that the user has typed in:
    One to be used for the undo feature. I am not happy with the way this works.
    The only way I have been able to think of is to keep the code that's been
    typed in in memory and re-evaluate it in its entirety for each "undo"
    operation. Obviously this means some operations could be extremely slow.
    I'm not even by any means certain that this truly represents a genuine "undo"
    implementation, but it does seem to be generally pretty effective.

    If anyone has any suggestions for how this could be improved, I'd be happy
    to hear them and implement it/accept a patch. I researched a bit into
    the idea of keeping the entire Python state in memory, but this really
    seems very difficult (I believe it may actually be impossible to work)
    and has its own problems too. 

    The other stack is for keeping a history for pressing the up/down keys
    to go back and forth between lines.
    """#TODO: Split the class up a bit so the curses stuff isn't so integrated.
    """

    """

    def __init__( self, scr, interp, statusbar=None, idle=None):
        """Initialise the repl with, unfortunately, a curses screen passed to it.
        This needs to be split up so the curses crap isn't in here.

        interp is a Python code.InteractiveInterpreter instance

        The optional 'idle' parameter is a function that the repl call while
        it's blocking (waiting for keypresses). This, again, should be in a
        different class"""

        self.buffer = []
        self.scr = scr
        self.interp = interp
        self.match = False
        self.rl_hist = []
        self.stdout_hist = ''
        self.s_hist = []
        self.history = []
        self.h_i = 0
        self.in_hist = False
        self.evaluating = False
        self.do_exit = False
        self.cpos = 0
# Use the interpreter's namespace only for the readline stuff:
        self.completer = rlcompleter.Completer( self.interp.locals )
        self.statusbar = statusbar
        self.list_win = curses.newwin( 1, 1, 1, 1 )
        self.idle = idle
        self.f_string = ''
        self.matches = []
        self.argspec = None
        self.s = ''
        self.list_win_visible = False
        self._C = {}
        sys.stdin = FakeStdin(self)

        if not OPTS.arg_spec:
            return

        pythonhist = os.path.expanduser('~/.pythonhist')
        if os.path.exists(pythonhist):
            self.rl_hist = open(pythonhist, 'r').readlines()

        pexp = Forward()
        chars = printables.replace('(', '')
        chars = chars.replace(')', '')
        pexpnest = Optional( Word( chars ) ) + Literal( "(" ) + Optional( Group( pexp ) ) + Optional( Literal( ")" ) )
        pexp << ( OneOrMore( Word( chars ) | pexpnest ) )
        self.pparser = pexp

    def cw( self ):
        """Return the current word, i.e. the (incomplete) word
        directly to the left of the cursor"""

        if self.cpos: # I don't know if autocomplete should be disabled
# if the cursor isn't at the end of the line, but that's what this does for now.
            return

        l = len( self.s )

        if not self.s or ( not self.s[ l-1 ].isalnum() and self.s[ l-1 ] not in ( '.', '_' ) ):
            return
    
        i = 1
        while i < l+1:
            if not self.s[ -i ].isalnum() and self.s[ -i ] not in ( '.', '_' ):
                break
            i += 1
        return self.s[ -i +1: ]


    def get_args( self ):
        """Check if an unclosed parenthesis exists, then attempt to get the argspec()
        for it. On success, update self.argspec and return True, otherwise set
        self.argspec to None and return False"""

        def getpydocspec( f, func ):
            try:
                argspec = pydoc.getdoc( f )
            except NameError:
                return None

            rx = re.compile( r'([a-zA-Z_][a-zA-Z0-9_]*?)\((.*?)\)' )
            s = rx.search( argspec )
            if s is None:
                return None

            if s.groups()[0] != func:
                return None
            
            args = [ i.strip() for i in s.groups()[1].split(',') ]
            return [func, (args, None, None, None)]#None, None, None]


        def getargspec( func ):
            try:
                if func in self.interp.locals:
                    f = self.interp.locals[ func ]
            except TypeError:
                return None

            else:
                try:
                    f = eval( func, self.interp.locals )
                except Exception: # Same deal with the exceptions :(
                    return None

            try:
                if inspect.isclass(f):
                    argspec = inspect.getargspec( f.__init__ )
                else:
                    argspec = inspect.getargspec( f )
                self.argspec = [func, argspec]#[0]]#"Args for %s: " + ", ".join( argspec[0] )
                #self.argspec = self.argspec % func
                return True

            except (NameError, TypeError, KeyError):
                t = getpydocspec( f, func )
                if t is None:
                    return None
                self.argspec = t
                return True
            except AttributeError: # no __init__
                return None

        def parse_parens( s ):
            """Run a string through the pyparsing pattern for paren
            counting."""

            try:
                parsed = self.pparser.parseString( s ).asList()
            except ParseException:
                return False

            return parsed

        def walk( seq ):
            """Walk a nested list and return the last list found that
            doesn't have a close paren in it (i.e. the active function)"""
            r = None
            if isinstance( seq, list ):
                if ")" not in seq and "(" in seq:
                    r = seq[ seq.index('(') - 1 ]
                for i in seq:
                    t = walk( i )
                    if t:
                        r = t
            return r

        if not OPTS.arg_spec:
            return False

        t = parse_parens( self.s )
        if not t:
            return False 

        func = walk( t )
        if not func:
            return False
        
        return getargspec( func )

    def complete( self, tab=False ):
        """Wrap the _complete method to determine the visibility of list_win
        since there can be several reasons why it won't be displayed; this
        makes it more manageable."""
        
        if self.list_win_visible and not OPTS.auto_display_list:
            self.scr.touchwin()
            self.list_win_visible = False
            return

        if OPTS.auto_display_list or tab:
            self.list_win_visible = self._complete( tab )
            return

    def _complete( self, unused_tab=False ):
        """Construct a full list of possible completions and construct and
        display them in a window. Also check if there's an available argspec
        (via the inspect module) and bang that on top of the completions too.
        The return value is whether the list_win is visible or not."""

        if not self.get_args():
            self.argspec = None

        cw = self.cw()
        if not (cw or self.argspec):
            self.scr.redrawwin()
            self.scr.refresh()
            return False

        if not cw:
            self.matches = []

        try:
            self.completer.complete( cw, 0 )
        except Exception: # This sucks, but it's either that or list all the
# exceptions that could possibly be raised here, so if anyone wants to do that,
# feel free to send me a patch.
            e = True
        else:
            e = False

        if (e or not self.completer.matches) and not self.argspec:
            self.scr.redrawwin()
            return False

        if not e and self.completer.matches:
            self.matches = sorted( set( self.completer.matches ) ) # remove duplicates and
# restore order

        if len( self.matches ) == 1 and not OPTS.auto_display_list:
            self.list_win_visible = True
            self.tab()
            return False

        self.show_list( self.matches, self.argspec )
        return True

    def show_list( self, items, topline=None ):
        shared = Struct()
        shared.cols = 0
        shared.rows = 0
        shared.wl = 0
        y, x = self.scr.getyx()
        h, w = self.scr.getmaxyx()
        down = (y < h / 2)
        if down:
            max_h = h - y 
        else:
            max_h = y+1
        max_w = int(w * 0.8)

        self.list_win.erase()
        if items and '.' in items[0]:
            items = [ x.rsplit('.')[-1] for x in items ]

        if topline:
            height_offset = self.mkargspec(topline, down) + 1
        else:
            height_offset = 0

        def lsize():
            wl = max( len(i) for i in v_items ) + 1 # longest word length (and a space)
            if not wl:
                wl = 1
            cols = ((max_w - 2) / wl) or 1 
            rows = len( v_items ) / cols

            if cols * rows < len( v_items ):
                rows += 1

            if rows + 2 >= max_h:
                rows = max_h - 2
                return False

            shared.rows = rows
            shared.cols = cols
            shared.wl = wl
            return True

        if items:
            v_items = [ items[0][:max_w-3] ] # visible items (we'll append until we can't fit any more in)
            lsize()
        else:
            v_items = []

        for i in items[1:]:
            v_items.append( i[:max_w-3] )
            if not lsize():
                del v_items[-1]
                v_items[-1] = '...'
                break

        rows = shared.rows
        if rows + height_offset < max_h:
            rows += height_offset
            display_rows = rows
        else:
            display_rows = rows + height_offset

        cols = shared.cols
        wl = shared.wl
        
        if topline and not v_items:
            w = max_w
        elif wl + 3 > max_w:
            w = max_w
        else:
            t = (cols + 1) * wl + 3
            if t > max_w:
                t = max_w
            w = t


        if height_offset and display_rows+5 >= max_h:
            del v_items[-(cols * (height_offset)):]

        self.list_win.resize( rows+2, w )#(cols + 1) * wl + 3 )

        if down:
            self.list_win.mvwin(y+1, 0)
        else:
            self.list_win.mvwin(y-rows-2, 0)

        if v_items:
            self.list_win.addstr( '\n ' )
         

        for ix, i in enumerate(v_items):
            padding = (wl - len(i)) * ' '
            self.list_win.addstr( i + padding, curses.color_pair( self._C["c"]+1 ) )
            if (cols == 1 or (ix and not (ix+1) % cols)) and ix + 1 < len(v_items):
                self.list_win.addstr( '\n ' )
        
# XXX: After all the trouble I had with sizing the list box (I'm not very good
# at that type of thing) I decided to do this bit of tidying up here just to make
# sure there's no unnececessary blank lines, it makes things look nicer. :)
        y = self.list_win.getyx()[0]
        self.list_win.resize(y + 2, w )

        self.statusbar.win.touchwin()
        self.statusbar.win.noutrefresh()
        self.list_win.border()
        self.scr.touchwin()
        self.scr.cursyncup()
        self.scr.noutrefresh()
# This looks a little odd, but I can't figure a better way to stick the cursor
# back where it belongs (refreshing the window hides the list_win)
        self.scr.move( *self.scr.getyx() )
        self.list_win.refresh()

    
    def mkargspec( self, topline, down ):
        """This figures out what to do with the argspec and puts it nicely into
        the list window. It returns the number of lines used to display the argspec.
        It's also kind of messy due to it having to call so many addstr() to get
        the colouring right, but it seems to be pretty sturdy."""

        r = 3
        fn = topline[0]
        args = topline[1][0]
        kwargs = topline[1][3]
        _args = topline[1][1]
        _kwargs = topline[1][2]
        max_w = int(self.scr.getmaxyx()[1] * 0.6)
        self.list_win.erase()
        self.list_win.resize( 3, max_w )
        h, w = self.list_win.getmaxyx()

        self.list_win.addstr( '\n  ')
        self.list_win.addstr( fn, curses.color_pair( self._C["b"]+1 ) | curses.A_BOLD )
        self.list_win.addstr( ': ( ', curses.color_pair( self._C["y"]+1 ) )
        maxh = self.scr.getmaxyx()[0]

        for k, i in enumerate( args ):
            y, x = self.list_win.getyx()
            ln = len( str(i) )
            kw = None
            if kwargs and k+1 > len(args) - len(kwargs):
                kw = '%s' % str(kwargs[ k - (len(args) - len(kwargs))])
                ln += len( kw ) + 1
        
            if ln + x >= w:
                ty = self.list_win.getbegyx()[0]
                if not down and ty > 0:
                    h +=1
                    self.list_win.mvwin( ty-1, 1 )
                    self.list_win.resize(h,w)
                elif down and h + r < maxh-ty:
                    h += 1
                    self.list_win.resize(h,w)
                else:
                    break
                r += 1
                self.list_win.addstr('\n\t')

            self.list_win.addstr( str(i), curses.color_pair( self._C["g"]+1 ) | curses.A_BOLD )
            if kw:
                self.list_win.addstr( '=', curses.color_pair( self._C["c"]+1 ) )
                self.list_win.addstr( kw, curses.color_pair( self._C["g"]+1) )
            if k != len(args) -1:
                self.list_win.addstr( ', ', curses.color_pair( self._C["g"]+1 ) )

        if _args:
            self.list_win.addstr( ', ', curses.color_pair( self._C["g"]+1 ) )
            self.list_win.addstr( '*%s' % _args, curses.color_pair( self._C["m"]+1 ) )
        if _kwargs:
            self.list_win.addstr( ', ', curses.color_pair( self._C["g"]+1 ) )
            self.list_win.addstr( '**%s' % _kwargs, curses.color_pair( self._C["m"]+1 ) )
        self.list_win.addstr( ' )', curses.color_pair( self._C["y"]+1 ) )

        return r

    def getstdout( self ):
        """This method returns the 'spoofed' stdout buffer, for writing to a file
        or sending to a pastebin or whatever."""

        return self.stdout_hist + '\n'

    def write2file( self ):
        """Prompt for a filename and write the current contents of the stdout buffer
        to disk."""
    
        fn = self.statusbar.prompt( 'Save to file: ' )

        if fn.startswith('~'):
            fn = os.path.expanduser( fn )

        s = self.getstdout()
        
        try:
            f = open( fn, 'w' )
            f.write( s )
            f.close()
        except IOError:
            self.statusbar.message("Disk write error for file '%s'." % fn )
        else:
            self.statusbar.message( 'Saved to %s' % fn )

    def pastebin( self ):
        """Upload to a pastebin and display the URL in the status bar."""
        
        s = self.getstdout()
        url = 'http://rafb.net/paste/paste.php'
        pdata = { 'lang' : 'Python',
            'cvt_tabs' : 'No',
            'text' : s }
        pdata = urllib.urlencode( pdata )

        self.statusbar.message( 'Posting data to pastebin...' )
        u = urllib.urlopen( url, data=pdata )
        d = u.read()

        rx = re.search( '(http://rafb.net/p/[0-9a-zA-Z]+\.html)', d )
        if not rx:
            self.statusbar.message( 'Error parsing pastebin URL! Please report a bug.' )
            return
    
        
        r_url = rx.groups()[ 0 ]
        self.statusbar.message( 'Pastebin URL: %s' % r_url, 10 )


    def make_list( self, items ):
        """Compile a list of items. At the moment this simply returns
        the list; it's here in case I decide to add any more functionality.
        I originally had this method return a list of items where each item
        was prepended with a number/letter so the user could choose an option
        but it doesn't seem appropriate for readline-like behaviour."""

        return items


    def push( self, s ):
        """Push a line of code onto the buffer so it can process it all
        at once when a code block ends"""
        s = s.rstrip('\n')
        self.buffer.append( s )

        more = self.interp.runsource( "\n".join( self.buffer ) )
        
        if not more:
            self.buffer = []

        return more

    def undo( self, n=1 ):
        """Go back in the undo history n steps and call reeavluate()
        Note that in the program this is called "Rewind" because I
        want it to be clear that this is by no means a true undo
        implementation, it is merely a convenience bonus.""" 
        if not self.history:
            return None

        if len( self.history ) < n:
            n = len( self.history )

        self.history = self.history[ : -n ]
        self.reevaluate()

    def enter_hist( self ):
        """Set flags for entering into the history by pressing up/down"""
        if not self.in_hist:
            self.in_hist = True
            self.ts = self.s

    def back( self ):
        """Replace the active line with previous line in history and
        increment the index to keep track"""

        if not self.rl_hist:
            return None
        
        self.cpos = 0
        self.enter_hist()

        if self.h_i < len( self.rl_hist ):
            self.h_i += 1
        
        self.s = self.rl_hist[ -self.h_i ].rstrip('\n')
        self.print_line( self.s, clr=True )
    
    def fwd( self ):
        """Same as back() but, well, forward"""

        self.enter_hist()

        self.cpos = 0

        if self.h_i > 1:
            self.h_i -= 1
            self.s = self.rl_hist[ -self.h_i ]
        else:
            self.h_i = 0
            self.s = self.ts
            self.ts = ''
            self.in_hist = False
        
        self.print_line( self.s, clr=True )
        
    def redraw( self ):
        """Redraw the screen."""
        self.scr.erase()
        for k, s in enumerate( self.s_hist ):
            if not s:
                continue
            self.iy, self.ix = self.scr.getyx()
            for i in s.split('\x04'):
                self.echo( i, redraw=False )
            if k < len( self.s_hist ) -1:
                self.scr.addstr( '\n' )
        self.iy, self.ix = self.scr.getyx()
        self.print_line( self.s )
        self.scr.refresh()
        self.statusbar.refresh()

    def reevaluate( self ):
        """Clear the buffer, redraw the screen and re-evaluate the history"""

        self.evaluating = True
        self.stdout_hist = ''
        self.f_string = ''
        self.buffer = []
        self.scr.erase()
        self.s_hist = []

        self.prompt( False )

        self.iy, self.ix = self.scr.getyx()
        for line in self.history:
            self.stdout_hist += line + '\n'
            self.print_line( line )
            self.s_hist[-1] += self.f_string
            self.scr.addstr( '\n' ) # I decided it was easier to just do this manually
# than to make the print_line and history stuff more flexible.
            more = self.push( line )
            self.prompt( more )
            self.iy, self.ix = self.scr.getyx()
            
        self.s = ''
        self.scr.refresh()

        self.evaluating = False
        #map( self.push, self.history ) # <-- That's how simple this function was at first :(

    def prompt( self, more ):
        """Show the appropriate Python prompt"""
        if not more:
            self.echo( "\x01g\x03>>> " )
            self.stdout_hist += '>>> '
            self.s_hist.append( '\x01g\x03>>> \x04' )
        else:
            self.echo( "\x01r\x03... " )
            self.stdout_hist += '... '
            self.s_hist.append( '\x01r\x03... \x04' )

    def repl( self ):
        """Initialise the repl and jump into the loop. This method also
        has to keep a stack of lines entered for the horrible "undo"
        feature. It also tracks everything that would normally go to stdout
        in the normal Python interpreter so it can quickly write it to
        stdout on exit after curses.endwin(), as well as a history of lines
        entered for using up/down to go back and forth (which has to be separate
        to the evaluation history, which will be truncated when undoing."""
        
# This was a feature request to have the PYTHONSTARTUP
# file executed on startup - I personally don't use this
# feature so please notify me of any breakage.
        filename = os.environ.get('PYTHONSTARTUP')
        if filename and os.path.isfile(filename):
            f = open(filename, 'r')
            code_obj = compile(f.read(), filename, 'exec')
            f.close()
            self.interp.runcode(code_obj)

# The regular help() function uses PAGER to display the help, which
# screws with bpython.
        from bpython import _internal
        _internal.window = self.scr
        self.push('from bpython import _internal\n')
        self.push('help = _internal._help')

        self.iy, self.ix = self.scr.getyx()
        more = False
        while not self.do_exit:
            self.f_string = ''
            self.prompt( more )
            try:
                inp = self.get_line()
            except KeyboardInterrupt:
                self.statusbar.message('KeyboardInterrupt')
                self.scr.addstr('\n')
                self.scr.touchwin()
                self.scr.refresh()
                continue

            self.scr.redrawwin()
            if self.do_exit:
                return

            self.h_i = 0
            self.history.append( inp )
            self.s_hist[-1] += self.f_string
            self.stdout_hist += inp + '\n'
# Keep two copies so you can go up and down in the hist:
            if inp:
                self.rl_hist.append( inp + '\n' ) 
            more = self.push( inp )

    def size( self ):
        """Set instance attributes for x and y top left corner coordinates
        and width and heigth for the window."""
        h, w = stdscr.getmaxyx()
        self.y = 0 
        self.w = w
        self.h = h-1
        self.x = 0

    def resize( self ):
        """This method exists simply to keep it straight forward when initialising
        a window and resizing it."""
        self.size()
        self.scr.erase()
        self.scr.resize( self.h, self.w )
        self.scr.mvwin( self.y, self.x )
        self.redraw()

    def write( self, s ):
        """For overriding stdout defaults"""
        if s.rstrip() and '\x03' in s:
                t = s.split('\x03')[1]
        else:
            t = s

        if not self.stdout_hist:
            self.stdout_hist = t
        else:
            self.stdout_hist += t

        self.echo( s )
        self.s_hist.append( s.rstrip() )

    def flush( self ):
        """Olivier Grisel brought it to my attention that the logging
        module tries to call this method, since it makes assumptions
        about stdout that may not necessarily be true. The docs for
        sys.stdout say:
        
        "stdout and stderr needn't be built-in file objects: any
         object is acceptable as long as it has a write() method
         that takes a string argument."

        So I consider this to be a bug in logging, and this is a hack
        to fix it, unfortunately. I'm sure it's not the only module
        to do it.""" 
        pass

    def close( self ):
        """See the flush() method docstring."""
        pass

    def echo( self, s, redraw=True ):
        """Parse and echo a formatted string with appropriate attributes. It uses the
        formatting method as defined in formatter.py to parse the srings. It won't update
        the screen if it's reevaluating the code (as it does with undo)."""

        a = curses.color_pair( 0 )
        if '\x01' in s:
            rx = re.search( '\x01([a-z])([a-z]?)', s )
            if rx:
                p = self._C[ rx.groups()[ 0 ] ]
                if rx.groups()[ 1 ]:
                    p *= self._C[ rx.groups()[ 1 ] ]
                
                a = curses.color_pair( int( p ) + 1 )
                s = re.sub( '\x01[a-z][a-z]?', '', s )

        if '\x02' in s:
            a = a | curses.A_BOLD
            s = s.replace( '\x02', '' )
        s = s.replace( '\x03', '' )
        s = s.replace( '\x01', '' )

        
        self.scr.addstr( s, a )    

        if redraw and not self.evaluating:
            self.scr.refresh()

    def mvc( self, i, refresh=True ):
        """This method moves the cursor relatively from the current
        position, where:
            0 == (right) end of current line
            length of current line len(self.s) == beginning of current line
        and:
            current cursor position + i
            for positive values of i the cursor will move towards the beginning
            of the line, negative values the opposite."""
        y, x = self.scr.getyx()

        if self.cpos == 0 and i < 0:
            return False

        if x == self.ix and y == self.iy and i >= 1:
            return False

        h, w = gethw()
        if x - i < 0:
            y -= 1
            x = w 

        if x - i >= w:
            y += 1
            x = 0 + i

        self.cpos += i
        self.scr.move( y, x - i )
        if refresh:
            self.scr.refresh()

        return True

    def bs( self, delete_tabs=True ):
        """Process a backspace"""

        y, x = self.scr.getyx()

        if not self.s:
            return

        if x == self.ix and y == self.iy:
            return

        n = 1

        if x == 0:
            y -= 1
            x = gethw()[1]

        if not self.cpos: # I know the nested if blocks look nasty. :(
            if self.atbol() and delete_tabs:
                n = len(self.s) % OPTS.tab_length
                if not n:
                    n = OPTS.tab_length

            self.s = self.s[ : -n ]
        else:
            self.s = self.s[ : -self.cpos-1 ] + self.s[ -self.cpos : ]

        for _ in range(n):
            self.scr.delch( y, x - n )

        return n

    def bs_word(self):
        pos = len(self.s) - self.cpos - 1
        # First we delete any space to the left of the cursor.
        while pos >= 0 and self.s[pos] == ' ':
            pos -= self.bs()
        # Then we delete a full word.
        while pos >= 0 and self.s[pos] != ' ':
            pos -= self.bs()

    def delete( self ):
        """Process a del"""
        if self.s: 
            return

        if self.mvc(-1):
            self.bs(False)

    def clrtobol( self ):
        """Clear from cursor to beginning of line; usual C-u behaviour"""
        if not self.cpos:
            self.s = ''
        else:
            self.s = self.s[ self.cpos : ]
        
        self.print_line( self.s, clr=True )
        self.scr.redrawwin()
        self.scr.refresh()

    def p_key( self ):
        """Process a keypress"""

        if self.c is None:
            return ''

        if self.c == chr(8): # C-Backspace (on my computer anyway!)
            self.clrtobol()
            self.c = '\n'
            # Don't return; let it get handled
        if self.c == chr( 27 ):
            return ''

        if self.c in ( chr(127), 'KEY_BACKSPACE' ):
            self.bs()
            self.complete()
            return ''

        elif self.c == 'KEY_DC': # Del
            self.delete()
            self.complete()
            return ''

        elif self.c == chr(18): # C-r
            self.undo()
            return ''

        elif self.c == 'KEY_UP': # Cursor Up
            self.back()
            return ''

        elif self.c == 'KEY_DOWN': # Cursor Down
            self.fwd()
            return ''

        elif self.c == 'KEY_LEFT': # Cursor Left
            self.mvc( 1 )
        
        elif self.c == 'KEY_RIGHT': # Cursor Right
            self.mvc( -1 )

        elif self.c == "KEY_HOME":
            self.mvc(len(self.s) - self.cpos)

        elif self.c == "KEY_END":
            self.mvc(-self.cpos)

        elif self.c in ('^W', chr(23)): # C-w
            self.bs_word()
            self.complete()
            return ''

        elif self.c in ('^U', chr(21) ): # C-u
            self.clrtobol()
            return ''

        elif self.c in ('^L', chr(12) ): # C-l
            self.redraw()
            return ''

        elif self.c in ( chr(4), '^D' ): # C-d
            if not self.s:
                self.do_exit = True
                return None
            else:
                return ''

        elif self.c == 'KEY_F(2)':
            self.write2file()
            return ''

        elif self.c == 'KEY_F(8)':
            self.pastebin()
            return ''

        elif self.c == '\n':
            self.lf()
            return None
        
        elif self.c == '\t':
            return self.tab()

        elif len( self.c ) == 1 and self.c in string.printable:
            self.addstr( self.c )
            self.print_line( self.s )

        else:
            return ''


        return True

    def tab( self ):
        """Process the tab key being hit. If there's only whitespace
        in the line or the line is blank then process a normal tab,
        otherwise attempt to autocomplete to the best match of possible
        choices in the match list."""
        
        if self.atbol():
            x_pos = len(self.s) - self.cpos
            num_spaces = x_pos % OPTS.tab_length
            if not num_spaces:
                num_spaces = OPTS.tab_length

            self.addstr( ' ' * num_spaces)
            self.print_line( self.s )
            return True

        if not OPTS.auto_display_list and not self.list_win_visible:
            self.complete( tab=True )
            return True

        cw = self.cw()
        if not cw:
            return True

        b = self.strbase( self.matches )
        if b:
            self.s += b[ len( cw ) : ]
            self.print_line( self.s )
            if len( self.matches ) == 1 and OPTS.auto_display_list:
                self.scr.touchwin()
        return True

    def strbase( self, l ):
        """Probably not the best way of doing it but this function returns
        a common base string in a list of strings (for tab completion)."""

        if len( l ) == 1:
            return l[0]
        
        sl = sorted( l, key=str.__len__ )
        for i, c in enumerate( l[-1] ):
# I hate myself. Please email seamusmb@gmail.com to call him an dickhead for
# insisting that I make bpython 2.4-compatible. I couldn't be bothered
# refactoring, so ghetto all() it is:
            if not reduce( lambda x, y: (x and y) or False,
                            ( k.startswith( l[-1][:i] ) for k in sl ),
                            True ):
                break

        return l[-1][:i-1]

    def atbol( self ):
        """Return True or False accordingly if the cursor is at the beginning
        of the line (whitespace is ignored). This exists so that p_key() knows
        how to handle the tab key being pressed - if there is nothing but white
        space before the cursor then process it as a normal tab otherwise attempt
        tab completion."""
        
        if not self.s.lstrip():
            return True

    def lf( self ):
        """Process a linefeed character; it only needs to check the
        cursor position and move appropriately so it doesn't clear
        the current line after the cursor."""
        if self.cpos:
            for _ in range( self.cpos ):
                self.mvc( -1 )

        self.echo( "\n" )

    def addstr( self, s ):
        """Add a string to the current input line and figure out
        where it should go, depending on the cursor position."""
        if not self.cpos:
            self.s += s
        else:
            l = len( self.s ) 
            self.s = self.s[ : l - self.cpos ] + s + self.s[ l - self.cpos : ]

        self.complete()

    def print_line( self, s, clr=False ):
        """Chuck a line of text through the highlighter, move the cursor
        to the beginning of the line and output it to the screen."""

        if not s:
            clr = True

        if OPTS.syntax:
            o = highlight( s, PythonLexer(), BPythonFormatter() )
        else:
            o = s

        self.f_string = o
        self.scr.move( self.iy, self.ix )

        if clr:
            self.scr.clrtoeol()

        if clr and not s:
            self.scr.refresh()
            
        if o:
            for t in o.split('\x04'):
                self.echo( t.rstrip('\n') )

        if self.cpos:
            t = self.cpos
            for _ in range( self.cpos ):
                self.mvc( 1 )
            self.cpos = t

    def get_line( self ):
        """Get a line of text and return it
        This function initialises an empty string and gets the 
        curses cursor position on the screen and stores it
        for the echo() function to use later (I think).
        Then it waits for key presses and passes them to p_key(),
        which returns None if Enter is pressed (that means "Return",
        idiot)."""

        self.ts = ''
        n_indent = re.split( '[^\t]', self.s, 1 )[0].count('\t')        
        indent = self.s.endswith(':')
        self.s = ''
        self.iy, self.ix = self.scr.getyx()

        for _ in range(n_indent):
            self.c = '\t'
            self.p_key()

        if indent:
            self.c = '\t'
            self.p_key()

        self.c = None
        self.cpos = 0

        while True:
            self.c = self.get_key()
            if self.p_key() is None:
                return self.s

    def get_key(self):
        while True:
            if self.idle:
                self.idle( self )
            try:
                key = self.scr.getkey()
            except curses.error: # I'm quite annoyed with the ambiguity of
# this exception handler. I previously caught "curses.error, x" and accessed
# x.message and checked that it was "no input", which seemed a crappy way of
# doing it. But then I ran it on a different computer and the exception
# seems to have entirely different attributes. So let's hope getkey() doesn't
# raise any other crazy curses exceptions. :)
                    continue
            else:
                return key

        
class Statusbar( object ):
    """This class provides the status bar at the bottom of the screen.
    It has message() and prompt() methods for user interactivity, as
    well as settext() and clear() methods for changing its appearance.

    The check() method needs to be called repeatedly if the statusbar is
    going to be aware of when it should update its display after a message()
    has been called (it'll display for a couple of seconds and then disappear).

    It should be called as:
        foo = Statusbar( stdscr, scr, 'Initial text to display' )
    or, for a blank statusbar:
        foo = Statusbar( stdscr, scr )

    It can also receive the argument 'c' which will be an integer referring
    to a curses colour pair, e.g.:
        foo = Statusbar( stdscr, 'Hello', c=4 )

    stdscr should be a curses window object in which to put the status bar.
    pwin should be the parent window. To be honest, this is only really here
    so the cursor can be returned to the window properly.
    
    """

    def __init__( self, scr, pwin, s=None, c=None ):
        """Initialise the statusbar and display the initial (text if there is any)"""
        self.size()
        self.win = curses.newwin( self.h, self.w, self.y, self.x )

        self.s = s or ''    
        self._s = self.s
        self.c = c
        self.timer = 0
        self.pwin = pwin
        self.settext( s, c )
        
    def size( self ):
        """Set instance attributes for x and y top left corner coordinates
        and width and heigth for the window."""
        h, w = gethw()
        self.y = h-1
        self.w = w
        self.h = 1
        self.x = 0

    def resize( self ):
        """This method exists simply to keep it straight forward when initialising
        a window and resizing it."""
        self.size()
        self.win.mvwin( self.y, self.x )
        self.win.resize( self.h, self.w )
        self.refresh()
    
    def refresh( self ):
        """This is here to make sure the status bar text is redraw properly
        after a resize."""
        self.settext( self._s )

    def check( self ):
        """This is the method that should be called every half second or so
        to see if the status bar needs updating."""
        if not self.timer:
            return
        
        if time.time() < self.timer:
            return
        
        self.settext( self._s )
        

    def message( self, s, n=3 ):
        """Display a message for a short n seconds on the statusbar and return
        it to its original state."""
        self.timer = time.time() + n
        self.settext( s )
        

    def prompt( self, s='' ):
        """Prompt the user for some input (with the optional prompt 's') and
        return the input text, then restore the statusbar to its original value."""
        
        self.settext( s or '? ', p=True )
        iy, ix = self.win.getyx()
        
        def bs( s ):
            y, x = self.win.getyx()
            if x == ix:
                return s
            s = s[:-1]
            self.win.delch(y,x-1)
            self.win.move(y,x-1)
            return s

        o = ''
        while True:
            c = self.win.getch()

            if c == 127:
                o = bs( o )
                continue

            if not c or c > 127:
                continue
            c = chr( c )

            if c == '\n':
                break

            self.win.addstr( c )
            o += c
        
        self.settext( self._s )
        return o

    def settext( self, s, c=None, p=False ):
        """Set the text on the status bar to a new permanent value; this is the value
        that will be set after a prompt or message. c is the optional curses colour
        pair to use (if not specified the last specified colour pair will be used).
        p is True if the cursor is expected to stay in the status window (e.g. when
        prompting)."""
        
        self.win.erase()
        if len( s ) >= self.w:
            s = s[ : self.w-1 ]

        self.s = s
        if c:
            self.c = c

        if s:
            if self.c:
                self.win.addstr( s, curses.color_pair( self.c ) )
            else:
                self.win.addstr( s )

        if not p:
            self.win.noutrefresh()
            self.pwin.refresh()
        else:
            self.win.refresh()

    def clear( self ):
        """Clear the status bar."""
        self.win.clear()

def init_wins( scr, cols ):
    """Initialise the two windows (the main repl interface and the
    little status bar at the bottom with some stuff in it)"""
#TODO: Document better what stuff is on the status bar.

    h, w = gethw()

    main_win = curses.newwin( h-1, w, 0, 0 )
    main_win.scrollok( True )
    main_win.keypad(1) # Thanks to Angus Gibson for pointing out
# this missing line which was causing problems that needed dirty
# hackery to fix. :)

    statusbar = Statusbar( scr, main_win, ".:: <C-d> Exit  <C-r> Rewind  <F2> Save  <F8> Pastebin ::.", (cols["g"]) *cols["y"] +1 )

    return main_win, statusbar

def sigwinch( unused_scr ):
    global DO_RESIZE
    DO_RESIZE = True

def gethw():
    """I found this code on a usenet post, and snipped out the bit I needed,
    so thanks to whoever wrote that, sorry I forgot your name, I'm sure you're
    a great guy.
    
    It's unfortunately necessary (unless someone has any better ideas) in order 
    to allow curses and readline to work together. I looked at the code for
    libreadline and noticed this comment:

        /* This is the stuff that is hard for me.  I never seem to write good
           display routines in C.  Let's see how I do this time. */

    So I'm not going to ask any questions.
    
    """
    h, w = struct.unpack(
        "hhhh", fcntl.ioctl(sys.__stdout__, termios.TIOCGWINSZ, "\000"*8))[0:2]
    return h, w

def idle( caller ):
    """This is called once every iteration through the getkey()
    loop (currently in the Repl class, see the get_line() method).
    The statusbar check needs to go here to take care of timed 
    messages and the resize handlers need to be here to make
    sure it happens conveniently."""

    global stdscr

    caller.statusbar.check()

    if DO_RESIZE:
        do_resize( caller )

def do_resize( caller ):
    """This needs to hack around readline and curses not playing
    nicely together. See also gethw() above."""
    global DO_RESIZE
    h, w = gethw()
    if not h: 
        return # Hopefully this shouldn't happen. :) 

    curses.endwin()
    os.environ["LINES"] = str( h )
    os.environ["COLUMNS"] = str( w )
    curses.doupdate()
    DO_RESIZE = False

    caller.resize()
    caller.statusbar.resize()
    # The list win resizes itself every time it appears so no need to do it here.

def loadrc():
    """Use the shlex module to make a simple lexer for the settings,
    it also attempts to convert any integers to Python ints, otherwise
    leaves them as strings and handles hopefully all the sane ways of
    representing a boolean."""

    if len(sys.argv) > 2:
        path = sys.argv[2]
    else:
        path = os.path.expanduser( '~/.bpythonrc' )

    if not os.path.isfile( path ):
        return

    f = open( path )
    parser = shlex.shlex( f )
    
    bools = {
        'true': True,
        'yes': True,
        'on': True,
        'false': False,
        'no': False,
        'off': False
    }

    config = {}
    while True:
        k = parser.get_token()
        v = None

        if not k:
            break

        k = k.lower()

        if parser.get_token() == '=':
            v = parser.get_token() or None

        if v is not None:
            try:
                v = int(v)
            except ValueError:
                if v.lower() in bools:
                    v = bools[v.lower()]

            config[k] = v 
    f.close()
        
    for k, v in config.iteritems():
        if hasattr( OPTS, k ):
            setattr( OPTS, k, v )


stdscr = None

def main_curses( scr ):
    """main function for the curses convenience wrapper

    Initialise the two main objects: the interpreter
    and the repl. The repl does what a repl does and lots
    of other cool stuff like syntax highlighting and stuff.
    I've tried to keep it well factored but it needs some
    tidying up, especially in separating the curses stuff
    from the rest of the repl.
    """
    global stdscr
    global DO_RESIZE
    DO_RESIZE = False
    signal.signal( signal.SIGWINCH, lambda *_: sigwinch(scr) )
    loadrc()
    stdscr = scr
    curses.start_color()
    curses.use_default_colors()
    cols = make_colours() 

    scr.timeout( 300 )

    main_win, statusbar = init_wins( scr, cols )


    interpreter = Interpreter()

    repl = Repl( main_win, interpreter, statusbar, idle )
    repl._C = cols

    sys.stdout = repl
    sys.stderr = repl


    repl.repl()
    if OPTS.hist_length:
        f = open(os.path.expanduser('~/.pythonhist'), 'w')
        f.writelines(repl.rl_hist[-OPTS.hist_length:])
        f.close()

    return repl.getstdout()

def main():
    tb = None
    try:
        o = curses.wrapper( main_curses )
    except:
        tb = traceback.format_exc()
    # I don't know why this is necessary; without it the wrapper doesn't always
    # do its job.
        if stdscr is not None:
            stdscr.keypad(0)
        curses.echo()
        curses.nocbreak()
        curses.endwin()

    sys.stdout = sys.__stdout__
    if tb:
        print tb
        sys.exit(1)

    sys.stdout.write( o ) # Fake stdout data so everything's still visible after exiting
    sys.stdout.flush()

if __name__ == '__main__':
    main()
