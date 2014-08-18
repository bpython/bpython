import code
import traceback
import sys
from pygments.style import Style
from pygments.token import *
from pygments.formatter import Formatter
from curtsies.bpythonparse import parse
from codeop import CommandCompiler, compile_command
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name

default_colors = {
        Generic.Error:'R',
        Keyword:'d',
        Name:'c',
        Name.Builtin:'g',
        Comment:'b',
        String:'m',
        Error:'r',
        Literal:'d',
        Number:'M',
        Number.Integer:'d',
        Operator:'d',
        Punctuation:'d',
        Token:'d',
        Whitespace:'d',
        Token.Punctuation.Parenthesis:'R',
        Name.Function:'d',
        Name.Class:'d',
    }
 
 
class BPythonFormatter(Formatter):
    """This is subclassed from the custom formatter for bpython.
    Its format() method receives the tokensource
    and outfile params passed to it from the
    Pygments highlight() method and slops
    them into the appropriate format string
    as defined above, then writes to the outfile
    object the final formatted string.
 
    See the Pygments source for more info; it's pretty
    straightforward."""
 
    def __init__(self, color_scheme, **options):
        self.f_strings = {}
        for k, v in color_scheme.iteritems():
            self.f_strings[k] = '\x01%s' % (v,)
        Formatter.__init__(self, **options)
 
    def format(self, tokensource, outfile):
        o = ''

        for token, text in tokensource:
            while token not in self.f_strings:
                token = token.parent
            o += "%s\x03%s\x04" % (self.f_strings[token], text)
        outfile.write(str(parse(o.rstrip())))
 
class Interp(code.InteractiveInterpreter):
    def __init__(self, locals=None, outfile=sys.__stderr__):
        """Constructor.

        The optional 'locals' argument specifies the dictionary in
        which code will be executed; it defaults to a newly created
        dictionary with key "__name__" set to "__console__" and key
        "__doc__" set to None.

        We include an argument for the outfile to pass to the formatter for it to write to.

        """
        if locals is None:
            locals = {"__name__": "__console__", "__doc__": None}
        self.locals = locals
        self.compile = CommandCompiler()
        self.outfile = outfile

    def showsyntaxerror(self, filename=None):
        """Display the syntax error that just occurred.

        This doesn't display a stack trace because there isn't one.

        If a filename is given, it is stuffed in the exception instead
        of what was there before (because Python's parser always uses
        "<string>" when reading from a string).

        The output is written by self.write(), below.

        """
        type, value, sys.last_traceback = sys.exc_info()
        sys.last_type = type
        sys.last_value = value
        if filename and type is SyntaxError:
            # Work hard to stuff the correct filename in the exception
            try:
                msg, (dummy_filename, lineno, offset, line) = value
            except:
                # Not the format we expect; leave it alone
                pass
            else:
                # Stuff in the right filename
                value = SyntaxError(msg, (filename, lineno, offset, line))
                sys.last_value = value
        l = traceback.format_exception_only(type, value)
        tbtext = ''.join(l)
        lexer = get_lexer_by_name("pytb")
        traceback_informative_formatter = BPythonFormatter(default_colors)
        traceback_code_formatter = BPythonFormatter({Token: ('d')})
        tokens= list(lexer.get_tokens(tbtext))
        no_format_mode = False
        cur_line = []
        for token, text in tokens:
            if text.endswith('\n'):
                cur_line.append((token,text))
                if no_format_mode:
                    traceback_code_formatter.format(cur_line,self.outfile)
                    no_format_mode = False
                else:
                    traceback_informative_formatter.format(cur_line,self.outfile)
                cur_line = []
            elif text == '    ' and cur_line == []:
                no_format_mode = True
                cur_line.append((token,text))
            else:
                cur_line.append((token,text))
        assert cur_line == [], cur_line

    def showtraceback(self):
        """Display the exception that just occurred.

        We remove the first stack item because it is our own code.


        """
        type, value, tb = sys.exc_info()
        sys.last_type = type
        sys.last_value = value
        sys.last_traceback = tb
        tblist = traceback.extract_tb(tb)
        del tblist[:1]
        l = traceback.format_list(tblist)
        if l:
            l.insert(0, "Traceback (most recent call last):\n")
        l[len(l):] = traceback.format_exception_only(type, value)
        tbtext = ''.join(l)
        lexer = get_lexer_by_name("pytb", stripall=True)
        traceback_informative_formatter = BPythonFormatter(default_colors)
        traceback_code_formatter = BPythonFormatter({Token: ('d')})
        tokens= list(lexer.get_tokens(tbtext))

        no_format_mode = False
        cur_line = []
        for token, text in tokens:
            if text.endswith('\n'):
                cur_line.append((token,text))
                if no_format_mode:
                    traceback_code_formatter.format(cur_line,self.outfile)
                    no_format_mode = False
                else:
                    traceback_informative_formatter.format(cur_line,self.outfile)
                cur_line = []
            elif text == '    ' and cur_line == []:
                no_format_mode = True
                cur_line.append((token,text))
            else:
                cur_line.append((token,text))
        assert cur_line == []

