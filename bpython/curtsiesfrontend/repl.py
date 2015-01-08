import code
import contextlib
import errno
import greenlet
import logging
import os
import re
import sys
import threading
import unicodedata

from bpython.autocomplete import Autocomplete, SIMPLE
from bpython.repl import Repl as BpythonRepl
from bpython.config import Struct, loadini, default_config_path
from bpython.formatter import BPythonFormatter
from pygments import format
from bpython import importcompletion
from bpython import translations
translations.init()
from bpython.translations import _
from bpython._py3compat import py3

from curtsies.fsarray import FSArray
from curtsies.fmtstr import fmtstr, FmtStr
from curtsies.bpythonparse import parse as bpythonparse
from curtsies.bpythonparse import func_for_letter, color_for_letter

from bpython.curtsiesfrontend.manual_readline import char_sequences as rl_char_sequences
from bpython.curtsiesfrontend.manual_readline import get_updated_char_sequences
from bpython.curtsiesfrontend.interaction import StatusBar
from bpython.curtsiesfrontend import sitefix; sitefix.monkeypatch_quit()
import bpython.curtsiesfrontend.replpainter as paint
import curtsies.events as events
from bpython.curtsiesfrontend.coderunner import CodeRunner, FakeOutput

#TODO figure out how config.list_win_visible behaves and implement it, or stop using it
#TODO other autocomplete modes (also fix in other bpython implementations)

from bpython.keys import cli_key_dispatch as key_dispatch

logger = logging.getLogger(__name__)

class FakeStdin(object):
    """Stdin object user code references so sys.stdin.read() asked user for interactive input"""
    def __init__(self, coderunner, repl):
        self.coderunner = coderunner
        self.repl = repl
        self.has_focus = False # whether FakeStdin receives keypress events
        self.current_line = ''
        self.cursor_offset_in_line = 0
        self.old_num_lines = 0
        self.readline_results = []

    def process_event(self, e):
        assert self.has_focus
        if isinstance(e, events.PasteEvent):
            for ee in e.events:
                if ee not in rl_char_sequences:
                    self.add_input_character(ee)
        elif e in rl_char_sequences:
            self.cursor_offset_in_line, self.current_line = rl_char_sequences[e](self.cursor_offset_in_line, self.current_line)
        elif isinstance(e, events.SigIntEvent):
            self.coderunner.sigint_happened_in_main_greenlet = True
            self.has_focus = False
            self.current_line = ''
            self.cursor_offset_in_line = 0
            self.repl.run_code_and_maybe_finish()
        elif e in ["\x1b"]: #ESC
            pass
        elif e in ["\n", "\r"]:
            line = self.current_line
            self.repl.send_to_stdin(line + '\n')
            self.has_focus = False
            self.current_line = ''
            self.cursor_offset_in_line = 0
            self.repl.run_code_and_maybe_finish(for_code=line)
        else: # add normal character
            self.add_input_character(e)

        if self.current_line.endswith(("\n", "\r")):
            pass
        else:
            self.repl.send_to_stdin(self.current_line)

    def add_input_character(self, e):
        assert len(e) == 1, 'added multiple characters: %r' % e
        logger.debug('adding normal char %r to current line', e)
        c = e if py3 else e.encode('utf8')
        self.current_line = (self.current_line[:self.cursor_offset_in_line] +
                             c +
                             self.current_line[self.cursor_offset_in_line:])
        self.cursor_offset_in_line += 1

    def readline(self):
        self.has_focus = True
        self.repl.send_to_stdin(self.current_line)
        value = self.coderunner.request_from_main_greenlet()
        self.readline_results.append(value)
        return value

    def readlines(self, size=-1):
        return list(iter(self.readline, ''))

    def __iter__(self):
        return iter(self.readlines())

    def isatty(self):
        return True

    def flush(self):
        """Flush the internal buffer. This is a no-op. Flushing stdin
        doesn't make any sense anyway."""

    def write(self, value):
        # XXX IPython expects sys.stdin.write to exist, there will no doubt be
        # others, so here's a hack to keep them happy
        raise IOError(errno.EBADF, "sys.stdin is read-only")

    @property
    def encoding(self):
        return 'UTF8'

    #TODO write a read() method

class ReevaluateFakeStdin(object):
    """Stdin mock used during reevaluation (undo) so raw_inputs don't have to be reentered"""
    def __init__(self, fakestdin, repl):
        self.fakestdin = fakestdin
        self.repl = repl
        self.readline_results = fakestdin.readline_results[:]
    def readline(self):
        if self.readline_results:
            value = self.readline_results.pop(0)
        else:
            value = 'no saved input available'
        self.repl.send_to_stdout(value)
        return value

class Repl(BpythonRepl):
    """Python Repl

    Reacts to events like
     -terminal dimensions and change events
     -keystrokes
    Behavior altered by
     -number of scroll downs that were necessary to render array after each display
     -initial cursor position
    outputs:
     -2D array to be rendered

    Repl is mostly view-independent state of Repl - but self.width and self.height
    are important for figuring out how to wrap lines for example.
    Usually self.width and self.height should be set by receiving a window resize event,
    not manually set to anything - as long as the first event received is a window
    resize event, this works fine.
    """

    ## initialization, cleanup
    def __init__(self, locals_=None, config=None, request_refresh=lambda: None, banner=None, interp=None):
        """
        locals_ is a mapping of locals to pass into the interpreter
        config is a bpython config.Struct with config attributes
        request_refresh is a function that will be called when the Repl
            wants to refresh the display, but wants control returned to it afterwards
        banner is a string to display briefly in the status bar
        interp is an interpreter to use
        """

        logger.debug("starting init")

        if config is None:
            config = Struct()
            loadini(config, default_config_path())

        self.weak_rewind = bool(locals_ or interp) # If creating a new interpreter on undo
                                                   # would be unsafe because initial
                                                   # state was passed in
        if interp is None:
            interp = code.InteractiveInterpreter(locals=locals_)
        if banner is None:
            banner = _('welcome to bpython')
        config.autocomplete_mode = SIMPLE # only one implemented currently
        if config.cli_suggestion_width <= 0 or config.cli_suggestion_width > 1:
            config.cli_suggestion_width = 1

        self.reevaluating = False
        self.fake_refresh_requested = False
        def smarter_request_refresh():
            if self.reevaluating or self.paste_mode:
                self.fake_refresh_requested = True
            else:
                request_refresh()
        self.request_refresh = smarter_request_refresh

        self.status_bar = StatusBar(banner if config.curtsies_fill_terminal else '', _(
            " <%s> Rewind  <%s> Save  <%s> Pastebin <%s> Editor"
            ) % (config.undo_key, config.save_key, config.pastebin_key, config.external_editor_key),
            refresh_request=self.request_refresh
            )
        self.rl_char_sequences = get_updated_char_sequences(key_dispatch, config)
        logger.debug("starting parent init")
        super(Repl, self).__init__(interp, config)
        self.formatter = BPythonFormatter(config.color_scheme)
        self.interact = self.status_bar # overwriting what bpython.Repl put there
                                        # interact is called to interact with the status bar,
                                        # so we're just using the same object
        self._current_line = '' # line currently being edited, without '>>> '
        self.current_stdouterr_line = '' # current line of output - stdout and stdin go here
        self.display_lines = [] # lines separated whenever logical line
                                # length goes over what the terminal width
                                # was at the time of original output
        self.history = [] # this is every line that's been executed;
                          # it gets smaller on rewind
        self.display_buffer = [] # formatted version of lines in the buffer
                                 # kept around so we can unhighlight parens
                                 # using self.reprint_line as called by
                                 # bpython.Repl
        self.scroll_offset = 0 # how many times display has been scrolled down
                               # because there wasn't room to display everything
        self.cursor_offset_in_line = 0 # from the left, 0 means first char

        self.coderunner = CodeRunner(self.interp, self.request_refresh)
        self.stdout = FakeOutput(self.coderunner, self.send_to_stdout)
        self.stderr = FakeOutput(self.coderunner, self.send_to_stderr)
        self.stdin = FakeStdin(self.coderunner, self)

        self.request_paint_to_clear_screen = False # next paint should clear screen
        self.last_events = [None] * 50
        self.presentation_mode = False
        self.paste_mode = False

        self.width = None  # will both be set by a window resize event
        self.height = None

    def __enter__(self):
        self.orig_stdout = sys.stdout
        self.orig_stderr = sys.stderr
        self.orig_stdin = sys.stdin
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        sys.stdin = self.stdin
        return self

    def __exit__(self, *args):
        sys.stdin = self.orig_stdin
        sys.stdout = self.orig_stdout
        sys.stderr = self.orig_stderr

    def clean_up_current_line_for_exit(self):
        """Called when trying to exit to prep for final paint"""
        logger.debug('unhighlighting paren for exit')
        self.cursor_offset_in_line = -1
        self.unhighlight_paren()

    ## Event handling
    def process_event(self, e):
        """Returns True if shutting down, otherwise returns None.
        Mostly mutates state of Repl object"""
        # event names uses here are curses compatible, or the full names
        # for a full list of what should have pretty names, see curtsies.events.CURSES_TABLE

        if not isinstance(e, events.Event):
            self.last_events.append(e)
            self.last_events.pop(0)

        logger.debug("processing event %r", e)
        if isinstance(e, events.RefreshRequestEvent):
            if self.status_bar.has_focus:
                self.status_bar.process_event(e)
            else:
                assert self.coderunner.code_is_waiting
                self.run_code_and_maybe_finish()
        elif isinstance(e, events.WindowChangeEvent):
            logger.debug('window change to %d %d', e.width, e.height)
            self.scroll_offset -= e.cursor_dy
            self.width, self.height = e.width, e.height

        elif self.status_bar.has_focus:
            return self.status_bar.process_event(e)

        # handles paste events for both stdin and repl
        elif isinstance(e, events.PasteEvent):
            ctrl_char = compress_paste_event(e)
            if ctrl_char is not None:
                return self.process_event(ctrl_char)
            with self.in_paste_mode():
                for ee in e.events:
                    if self.stdin.has_focus:
                        self.stdin.process_event(ee)
                    else:
                        self.process_simple_event(ee)
            self.update_completion()

        elif self.stdin.has_focus:
            return self.stdin.process_event(e)

        elif isinstance(e, events.SigIntEvent):
            logger.debug('received sigint event')
            self.keyboard_interrupt()
            self.update_completion()
            return

        elif e in self.rl_char_sequences:
            self.cursor_offset_in_line, self._current_line = self.rl_char_sequences[e](self.cursor_offset_in_line, self._current_line)
            self.update_completion()

        # readline history commands
        elif e in ("KEY_UP",) + key_dispatch[self.config.up_one_line_key]:
            self.rl_history.enter(self._current_line)
            self._current_line = self.rl_history.back(False)
            self.cursor_offset_in_line = len(self._current_line)
            self.update_completion()
        elif e in ("KEY_DOWN",) + key_dispatch[self.config.down_one_line_key]:
            self.rl_history.enter(self._current_line)
            self._current_line = self.rl_history.forward(False)
            self.cursor_offset_in_line = len(self._current_line)
            self.update_completion()
        elif e in key_dispatch[self.config.search_key]: #TODO Not Implemented
            pass
        #TODO add rest of history commands

        # Need to figure out what these are, but I think they belong in manual_realine
        # under slightly different names
        elif e in key_dispatch[self.config.cut_to_buffer_key]: #TODO Not Implemented
            pass
        elif e in key_dispatch[self.config.yank_from_buffer_key]: #TODO Not Implemented
            pass

        elif e in key_dispatch[self.config.clear_screen_key]:
            self.request_paint_to_clear_screen = True
        elif e in key_dispatch[self.config.last_output_key]: #TODO Not Implemented
            pass
        elif e in key_dispatch[self.config.show_source_key]: #TODO Not Implemented
            pass
        elif e in key_dispatch[self.config.suspend_key]:
            raise SystemExit()
        elif e in ("",) + key_dispatch[self.config.exit_key]:
            if self._current_line == '':
                raise SystemExit()
        elif e in ("\n", "\r", "PAD_ENTER"):
            self.on_enter()
            self.update_completion()
        elif e == '\t': # tab
            self.on_tab()
        elif e in ("KEY_BTAB",): # shift-tab
            self.on_tab(back=True)
        elif e in key_dispatch[self.config.undo_key]: #ctrl-r for undo
            self.undo()
            self.update_completion()
        elif e in key_dispatch[self.config.save_key]: # ctrl-s for save
            g = greenlet.greenlet(self.write2file)
            g.switch()
        # F8 for pastebin
        elif e in key_dispatch[self.config.pastebin_key]:
            g = greenlet.greenlet(self.pastebin)
            g.switch()
        elif e in key_dispatch[self.config.external_editor_key]:
            self.send_session_to_external_editor()
        #TODO add PAD keys hack as in bpython.cli
        elif e in ["\x18"]:
            self.send_current_block_to_external_editor()
        elif e in ["\x1b"]: #ESC
            pass
        else:
            self.add_normal_character(e)
            self.update_completion()

    def on_enter(self, insert_into_history=True):
        self.cursor_offset_in_line = -1 # so the cursor isn't touching a paren
        self.unhighlight_paren()        # in unhighlight_paren
        self.highlighted_paren = None

        self.rl_history.append(self._current_line)
        self.rl_history.reset()
        self.history.append(self._current_line)
        line = self._current_line
        #self._current_line = ''
        self.push(line, insert_into_history=insert_into_history)

    def on_tab(self, back=False):
        """Do something on tab key
        taken from bpython.cli

        Does one of the following:
        1) add space to move up to the next %4==0 column
        2) complete the current word with characters common to all completions and
        3) select the first or last match
        4) select the next or previous match if already have a match
        """

        def only_whitespace_left_of_cursor():
            """returns true if all characters on current line before cursor are whitespace"""
            return self._current_line[:self.cursor_offset_in_line].strip()

        logger.debug('self.matches: %r', self.matches)
        if not only_whitespace_left_of_cursor():
            front_white = (len(self._current_line[:self.cursor_offset_in_line]) -
                len(self._current_line[:self.cursor_offset_in_line].lstrip()))
            to_add = 4 - (front_white % self.config.tab_length)
            for _ in range(to_add):
                self.add_normal_character(' ')
            return

        #TODO I'm not sure what's going on in the next 10 lines, particularly list_win_visible
        # get the (manually typed or common-sequence completed from manually typed) current word
        if self.matches_iter:
            cw = self.matches_iter.current_word
        else:
            self.complete(tab=True) #TODO why do we call this here?
            if not self.config.auto_display_list and not self.list_win_visible:
                return True #TODO why?
            cw = self.current_string() or self.current_word
            logger.debug('current string: %r', self.current_string())
            logger.debug('current word: %r', self.current_word)
            if not cw:
                return

        # check to see if we can expand the current word
        cseq = os.path.commonprefix(self.matches)
        expanded_string = cseq[len(cw):]
        if expanded_string:
            self.current_word = cw + expanded_string #asdf
            self.matches_iter.update(cseq, self.matches)
            return

        if self.matches:
            self.current_word = (self.matches_iter.previous()
                                 if back else self.matches_iter.next())

    def process_simple_event(self, e):
        if e in ("\n", "\r", "PAD_ENTER"):
            self.on_enter()
            while self.fake_refresh_requested:
                self.fake_refresh_requested = False
                self.process_event(events.RefreshRequestEvent())
        elif isinstance(e, events.Event):
            pass # ignore events
        else:
            self.add_normal_character(e)

    def send_current_block_to_external_editor(self, filename=None):
        text = self.send_to_external_editor(self.get_current_block())
        lines = [line for line in text.split('\n')]
        while lines and not lines[-1].split():
            lines.pop()
        events = '\n'.join(lines + ([''] if len(lines) == 1 else ['', '']))
        self.clear_current_block()
        with self.in_paste_mode():
            for e in events:
                self.process_simple_event(e)
        self._current_line = ''
        self.cursor_offset_in_line = len(self._current_line)

    def send_session_to_external_editor(self, filename=None):
        for_editor = '### current bpython session - file will be reevaluated, ### lines will not be run\n'.encode('utf8')
        for_editor += ('\n'.join(line[4:] if line[:4] in ('... ', '>>> ') else '### '+line
                       for line in self.getstdout().split('\n')).encode('utf8'))
        text = self.send_to_external_editor(for_editor)
        lines = text.split('\n')
        self.history = [line for line in lines if line[:4] != '### ']
        self.reevaluate(insert_into_history=True)
        self._current_line = lines[-1][4:]
        self.cursor_offset_in_line = len(self._current_line)

    ## Handler Helpers
    def add_normal_character(self, char):
        if len(char) > 1 or is_nop(char):
            return
        self._current_line = (self._current_line[:self.cursor_offset_in_line] +
                             char +
                             self._current_line[self.cursor_offset_in_line:])
        self.cursor_offset_in_line += 1
        if self.config.cli_trim_prompts and self._current_line.startswith(">>> "):
            self._current_line = self._current_line[4:]
            self.cursor_offset_in_line = max(0, self.cursor_offset_in_line - 4)

    def update_completion(self, tab=False):
        """Update autocomplete info; self.matches and self.argspec"""

        if self.list_win_visible and not self.config.auto_display_list:
            self.list_win_visible = False
            self.matches_iter.update(self.current_word)
            return

        if self.config.auto_display_list or tab:
            self.list_win_visible = BpythonRepl.complete(self, tab)

    def push(self, line, insert_into_history=True):
        """Push a line of code onto the buffer, start running the buffer

        If the interpreter successfully runs the code, clear the buffer
        """
        if self.paste_mode:
            self.saved_indent = 0
        else:
            indent = len(re.match(r'[ ]*', line).group())
            if line.endswith(':'):
                indent = max(0, indent + self.config.tab_length)
            elif line and line.count(' ') == len(line):
                indent = max(0, indent - self.config.tab_length)
            elif line and ':' not in line and line.strip().startswith(('return', 'pass', 'raise', 'yield')):
                indent = max(0, indent - self.config.tab_length)
            self.saved_indent = indent

        #current line not added to display buffer if quitting #TODO I don't understand this comment
        if self.config.syntax:
            display_line = bpythonparse(format(self.tokenize(line), self.formatter))
            # careful: self.tokenize requires that the line not be in self.buffer yet!

            logger.debug('display line being pushed to buffer: %r -> %r', line, display_line)
            self.display_buffer.append(display_line)
        else:
            self.display_buffer.append(fmtstr(line))

        if insert_into_history:
            self.insert_into_history(line)
        self.buffer.append(line)

        code_to_run = '\n'.join(self.buffer)

        logger.debug('running %r in interpreter', self.buffer)
        try:
            c = bool(code.compile_command('\n'.join(self.buffer)))
            self.saved_predicted_parse_error = False
        except (ValueError, SyntaxError, OverflowError):
            c = self.saved_predicted_parse_error = True
        if c:
            logger.debug('finished - buffer cleared')
            self.display_lines.extend(self.display_buffer_lines)
            self.display_buffer = []
            self.buffer = []
            self.cursor_offset_in_line = 0

        self.coderunner.load_code(code_to_run)
        self.run_code_and_maybe_finish()

    def run_code_and_maybe_finish(self, for_code=None):
        r = self.coderunner.run_code(for_code=for_code)
        if r:
            logger.debug("----- Running finish command stuff -----")
            logger.debug("saved_indent: %r", self.saved_indent)
            err = self.saved_predicted_parse_error
            self.saved_predicted_parse_error = False

            indent = self.saved_indent
            if err:
                indent = 0

            #TODO This should be printed ABOVE the error that just happened instead
            # or maybe just thrown away and not shown
            if self.current_stdouterr_line:
                self.display_lines.extend(paint.display_linize(self.current_stdouterr_line, self.width))
                self.current_stdouterr_line = ''

            self._current_line = ' '*indent
            self.cursor_offset_in_line = len(self._current_line)

    def keyboard_interrupt(self):
        #TODO factor out the common cleanup from running a line
        self.cursor_offset_in_line = -1
        self.unhighlight_paren()
        self.display_lines.extend(self.display_buffer_lines)
        self.display_lines.extend(paint.display_linize(self.current_cursor_line, self.width))
        self.display_lines.extend(paint.display_linize("KeyboardInterrupt", self.width))
        self.clear_current_block(remove_from_history=False)

    def unhighlight_paren(self):
        """modify line in self.display_buffer to unhighlight a paren if possible

        self.highlighted_paren should be a line in ?
        """
        if self.highlighted_paren is not None and self.config.syntax:
            lineno, saved_tokens = self.highlighted_paren
            if lineno == len(self.display_buffer):
                # then this is the current line, so don't worry about it
                return
            self.highlighted_paren = None
            logger.debug('trying to unhighlight a paren on line %r', lineno)
            logger.debug('with these tokens: %r', saved_tokens)
            new = bpythonparse(format(saved_tokens, self.formatter))
            self.display_buffer[lineno] = self.display_buffer[lineno].setslice_with_length(0, len(new), new, len(self.display_buffer[lineno]))

    def clear_current_block(self, remove_from_history=True):
        self.display_buffer = []
        if remove_from_history:
            [self.history.pop() for _ in self.buffer]
        self.buffer = []
        self.cursor_offset_in_line = 0
        self.saved_indent = 0
        self._current_line = ''
        self.cursor_offset_in_line = len(self._current_line)

    def get_current_block(self):
        return '\n'.join(self.buffer + [self._current_line])

    def send_to_stdout(self, output):
        lines = output.split('\n')
        logger.debug('display_lines: %r', self.display_lines)
        self.current_stdouterr_line += lines[0]
        if len(lines) > 1:
            self.display_lines.extend(paint.display_linize(self.current_stdouterr_line, self.width, blank_line=True))
            self.display_lines.extend(sum([paint.display_linize(line, self.width, blank_line=True) for line in lines[1:-1]], []))
            self.current_stdouterr_line = lines[-1]
        logger.debug('display_lines: %r', self.display_lines)

    def send_to_stderr(self, error):
        #self.send_to_stdout(error)
        self.display_lines.extend([func_for_letter(self.config.color_scheme['error'])(line)
                                   for line in sum([paint.display_linize(line, self.width)
                                                    for line in error.split('\n')], [])])

    def send_to_stdin(self, line):
        if line.endswith('\n'):
            self.display_lines.extend(paint.display_linize(self.current_output_line, self.width))
            self.current_output_line = ''
        #self.display_lines = self.display_lines[:len(self.display_lines) - self.stdin.old_num_lines]
        #lines = paint.display_linize(line, self.width)
        #self.stdin.old_num_lines = len(lines)
        #self.display_lines.extend(paint.display_linize(line, self.width))
        pass


    ## formatting, output
    @property
    def done(self):
        """Whether the last block is complete - which prompt to use, ps1 or ps2"""
        return not self.buffer

    @property
    def current_line_formatted(self):
        """The colored current line (no prompt, not wrapped)"""
        if self.config.syntax:
            fs = bpythonparse(format(self.tokenize(self._current_line), self.formatter))
            logger.debug('Display line %r -> %r', self._current_line, fs)
        else:
            fs = fmtstr(self._current_line)
        if hasattr(self, 'old_fs') and str(fs) != str(self.old_fs):
            pass
        self.old_fs = fs
        return fs

    @property
    def lines_for_display(self):
        """All display lines (wrapped, colored, with prompts)"""
        return self.display_lines + self.display_buffer_lines

    @property
    def current_word(self):
        """Returns the "current word", based on what's directly left of the cursor.
        examples inclue "socket.socket.metho" or "self.reco" or "yiel"

        cw() is currently an alias, but cw() is used by bpyton.repl.Repl
        so must match its definition of current word - changing how it behaves
        has many repercussions.
        """

        start, end, word = self._get_current_word()
        return word

    def _get_current_word(self):
        pos = self.cursor_offset_in_line

        matches = list(re.finditer(r'[\w_][\w0-9._]*[(]?', self._current_line))
        start = pos
        end = pos
        word = None
        for m in matches:
            if m.start() < pos and m.end() >= pos:
                start = m.start()
                end = m.end()
                word = m.group()
        return (start, end, word)

    @current_word.setter
    def current_word(self, value):
        # current word means word cursor is at the end of
        start, end, word = self._get_current_word()

        self._current_line = self._current_line[:start] + value + self._current_line[end:]
        self.cursor_offset_in_line = start + len(value)

    @property
    def display_buffer_lines(self):
        """The display lines (wrapped, colored, with prompts) for the current buffer"""
        lines = []
        for display_line in self.display_buffer:
            display_line = (func_for_letter(self.config.color_scheme['prompt_more'])(self.ps2)
                           if lines else
                           func_for_letter(self.config.color_scheme['prompt'])(self.ps1)) + display_line
            for line in paint.display_linize(display_line, self.width):
                lines.append(line)
        return lines

    @property
    def display_line_with_prompt(self):
        """colored line with prompt"""
        return (func_for_letter(self.config.color_scheme['prompt'])(self.ps1)
                if self.done else
                func_for_letter(self.config.color_scheme['prompt_more'])(self.ps2)) + self.current_line_formatted

    @property
    def current_cursor_line(self):
        """Current line, either output/input or Python prompt + code"""
        value = (self.current_output_line +
                ('' if self.coderunner.running else self.display_line_with_prompt))
        logger.debug('current cursor line: %r', value)
        return value

    @property
    def current_output_line(self):
        """line of output currently being written, and stdin typed"""
        return self.current_stdouterr_line + self.stdin.current_line

    @current_output_line.setter
    def current_output_line(self, value):
        self.current_stdouterr_line = ''
        self.stdin.current_line = '\n'

    def paint(self, about_to_exit=False, user_quit=False):
        """Returns an array of min_height or more rows and width columns, plus cursor position

        Paints the entire screen - ideally the terminal display layer will take a diff and only
        write to the screen in portions that have changed, but the idea is that we don't need
        to worry about that here, instead every frame is completely redrawn because
        less state is cool!
        """
        # The hairiest function in the curtsies - a cleanup would be great.

        if about_to_exit:
            self.clean_up_current_line_for_exit() # exception to not changing state!

        width, min_height = self.width, self.height
        show_status_bar = bool(self.status_bar._message) or (self.config.curtsies_fill_terminal or self.status_bar.has_focus)
        if show_status_bar:
            min_height -= 1

        current_line_start_row = len(self.lines_for_display) - max(0, self.scroll_offset)
        if self.request_paint_to_clear_screen: # or show_status_bar and about_to_exit ?
            self.request_paint_to_clear_screen = False
            if self.config.curtsies_fill_terminal: #TODO clean up this logic - really necessary check?
                arr = FSArray(self.height - 1 + current_line_start_row, width)
            else:
                arr = FSArray(self.height + current_line_start_row, width)
        else:
            arr = FSArray(0, width)
        #TODO test case of current line filling up the whole screen (there aren't enough rows to show it)

        if current_line_start_row < 0: #if current line trying to be drawn off the top of the screen
            logger.debug('#<---History contiguity broken by rewind--->')
            msg = "#<---History contiguity broken by rewind--->"
            arr[0, 0:min(len(msg), width)] = [msg[:width]]

            # move screen back up a screen minus a line
            while current_line_start_row < 0:
                self.scroll_offset = self.scroll_offset - self.height
                current_line_start_row = len(self.lines_for_display) - max(-1, self.scroll_offset)

            history = paint.paint_history(max(0, current_line_start_row - 1), width, self.lines_for_display)
            arr[1:history.height+1,:history.width] = history

            if arr.height <= min_height:
                arr[min_height, 0] = ' ' # force scroll down to hide broken history message
        else:
            history = paint.paint_history(current_line_start_row, width, self.lines_for_display)
            arr[:history.height,:history.width] = history

        current_line = paint.paint_current_line(min_height, width, self.current_cursor_line)
        if user_quit: # quit() or exit() in interp
            current_line_start_row = current_line_start_row - current_line.height
        logger.debug("---current line row slice %r, %r", current_line_start_row, current_line_start_row + current_line.height)
        logger.debug("---current line col slice %r, %r", 0, current_line.width)
        arr[current_line_start_row:current_line_start_row + current_line.height,
            0:current_line.width] = current_line

        if current_line.height > min_height:
            return arr, (0, 0) # short circuit, no room for infobox

        lines = paint.display_linize(self.current_cursor_line+'X', width)
                                       # extra character for space for the cursor
        current_line_end_row = current_line_start_row + len(lines) - 1

        if self.stdin.has_focus:
            cursor_row, cursor_column = divmod(len(self.current_stdouterr_line) + self.stdin.cursor_offset_in_line, width)
            assert cursor_column >= 0, cursor_column
        elif self.coderunner.running: #TODO does this ever happen?
            cursor_row, cursor_column = divmod(len(self.current_cursor_line) + self.cursor_offset_in_line, width)
            assert cursor_column >= 0, (cursor_column, len(self.current_cursor_line), len(self._current_line), self.cursor_offset_in_line)
        else:
            cursor_row, cursor_column = divmod(len(self.current_cursor_line) - len(self._current_line) + self.cursor_offset_in_line, width)
            assert cursor_column >= 0, (cursor_column, len(self.current_cursor_line), len(self._current_line), self.cursor_offset_in_line)
        cursor_row += current_line_start_row

        if self.list_win_visible:
            logger.debug('infobox display code running')
            visible_space_above = history.height
            visible_space_below = min_height - current_line_end_row - 1

            info_max_rows = max(visible_space_above, visible_space_below)
            infobox = paint.paint_infobox(info_max_rows, int(width * self.config.cli_suggestion_width), self.matches, self.argspec, self.current_word, self.docstring, self.config)

            if visible_space_above >= infobox.height and self.config.curtsies_list_above:
                arr[current_line_start_row - infobox.height:current_line_start_row, 0:infobox.width] = infobox
            else:
                arr[current_line_end_row + 1:current_line_end_row + 1 + infobox.height, 0:infobox.width] = infobox
                logger.debug('slamming infobox of shape %r into arr of shape %r', infobox.shape, arr.shape)

        logger.debug('about to exit: %r', about_to_exit)
        if show_status_bar:
            if self.config.curtsies_fill_terminal:
                if about_to_exit:
                    arr[max(arr.height, min_height), :] = FSArray(1, width)
                else:
                    arr[max(arr.height, min_height), :] = paint.paint_statusbar(1, width, self.status_bar.current_line, self.config)

                    if self.presentation_mode:
                        rows = arr.height
                        columns = arr.width
                        last_key_box = paint.paint_last_events(rows, columns, [events.pp_event(x) for x in self.last_events if x])
                        arr[arr.height-last_key_box.height:arr.height, arr.width-last_key_box.width:arr.width] = last_key_box
            else:
                statusbar_row = min_height + 1 if arr.height == min_height else arr.height
                if about_to_exit:
                    arr[statusbar_row, :] = FSArray(1, width)
                else:
                    arr[statusbar_row, :] = paint.paint_statusbar(1, width, self.status_bar.current_line, self.config)

        if self.config.color_scheme['background'] not in ('d', 'D'):
            for r in range(arr.height):
                arr[r] = fmtstr(arr[r], bg=color_for_letter(self.config.color_scheme['background']))
        logger.debug('returning arr of size %r', arr.shape)
        logger.debug('cursor pos: %r', (cursor_row, cursor_column))
        return arr, (cursor_row, cursor_column)

    @contextlib.contextmanager
    def in_paste_mode(self):
        orig_value = self.paste_mode
        self.paste_mode = True
        yield
        self.paste_mode = orig_value

    ## Debugging shims, good example of embedding a Repl in other code
    def dumb_print_output(self):
        arr, cpos = self.paint()
        arr[cpos[0]:cpos[0]+1, cpos[1]:cpos[1]+1] = ['~']
        def my_print(msg):
            self.orig_stdout.write(str(msg)+'\n')
        my_print('X'*(self.width+8))
        my_print(' use "/" for enter '.center(self.width+8, 'X'))
        my_print(' use "\\" for rewind '.center(self.width+8, 'X'))
        my_print(' use "|" to raise an error '.center(self.width+8, 'X'))
        my_print(' use "$" to pastebin '.center(self.width+8, 'X'))
        my_print(' "~" is the cursor '.center(self.width+8, 'X'))
        my_print('X'*(self.width+8))
        my_print('X``'+('`'*(self.width+2))+'``X')
        for line in arr:
            my_print('X```'+line.ljust(self.width)+'```X')
        logger.debug('line:')
        logger.debug(repr(line))
        my_print('X``'+('`'*(self.width+2))+'``X')
        my_print('X'*(self.width+8))
        return max(len(arr) - self.height, 0)

    def dumb_input(self, requested_refreshes=[]):
        chars = list(self.orig_stdin.readline()[:-1])
        while chars or requested_refreshes:
            if requested_refreshes:
                requested_refreshes.pop()
                self.process_event(events.RefreshRequestEvent())
                continue
            c = chars.pop(0)
            if c in '/':
                c = '\n'
            elif c in '\\':
                c = ''
            elif c in '|':
                def r(): raise Exception('errors in other threads should look like this')
                t = threading.Thread(target=r)
                t.daemon = True
                t.start()
            elif c in '$':
                c = key_dispatch[self.config.pastebin_key][0]
            self.process_event(c)

    def __repr__(self):
        s = ''
        s += '<Repl\n'
        s += " cursor_offset_in_line:" + repr(self.cursor_offset_in_line) + '\n'
        s += " num display lines:" + repr(len(self.display_lines)) + '\n'
        s += " lines scrolled down:" + repr(self.scroll_offset) + '\n'
        s += '>'
        return s

    ## Provided for bpython.repl.Repl
    def current_line(self):
        """Returns the current line"""
        return self._current_line
    def echo(self, msg, redraw=True):
        """
        Notification that redrawing the current line is necessary (we don't
        care, since we always redraw the whole screen)

        Supposed to parse and echo a formatted string with appropriate attributes.
        It's not supposed to update the screen if it's reevaluating the code (as it
        does with undo)."""
        logger.debug("echo called with %r" % msg)
    def cw(self):
        """Returns the "current word", based on what's directly left of the cursor.
        examples inclue "socket.socket.metho" or "self.reco" or "yiel" """
        return self.current_word
    @property
    def cpos(self):
        "many WATs were had - it's the pos from the end of the line back"""
        return len(self._current_line) - self.cursor_offset_in_line
    def reprint_line(self, lineno, tokens):
        logger.debug("calling reprint line with %r %r", lineno, tokens)
        if self.config.syntax:
            self.display_buffer[lineno] = bpythonparse(format(tokens, self.formatter))
    def reevaluate(self, insert_into_history=False):
        """bpython.Repl.undo calls this"""
        old_logical_lines = self.history
        self.history = []
        self.display_lines = []

        if not self.weak_rewind:
            self.interp = code.InteractiveInterpreter()
            self.coderunner.interp = self.interp
            self.completer = Autocomplete(self.interp.locals, self.config)
            self.completer.autocomplete_mode = 'simple'

        self.buffer = []
        self.display_buffer = []
        self.highlighted_paren = None

        self.reevaluating = True
        sys.stdin = ReevaluateFakeStdin(self.stdin, self)
        for line in old_logical_lines:
            self._current_line = line
            self.on_enter(insert_into_history=insert_into_history)
            while self.fake_refresh_requested:
                self.fake_refresh_requested = False
                self.process_event(events.RefreshRequestEvent())
        sys.stdin = self.stdin
        self.reevaluating = False

        self.cursor_offset_in_line = 0
        self._current_line = ''

    def getstdout(self):
        lines = self.lines_for_display + [self.current_line_formatted]
        s = '\n'.join([x.s if isinstance(x, FmtStr) else x for x in lines]
                     ) if lines else ''
        return s

def is_nop(char):
    return unicodedata.category(unicode(char)) == 'Cc'

def compress_paste_event(paste_event):
    """If all events in a paste event are identical and not simple characters, returns one of them

    Useful for when the UI is running so slowly that repeated keypresses end up in a paste event.
    If we value not getting delayed and assume the user is holding down a key to produce such frequent
    key events, it makes sense to drop some of the events.
    """
    if not all(paste_event.events[0] == e for e in paste_event.events):
        return None
    event = paste_event.events[0]
    if len(event) > 1:# basically "is there a special curses names for this key?"
        return event
    elif ord(event) < 0x20:
        return event
    elif event == '\x7f':
        return event
    else:
        return None

def simple_repl():
    refreshes = []
    def request_refresh():
        refreshes.append(1)
    with Repl(request_refresh=request_refresh) as r:
        r.width = 50
        r.height = 10
        while True:
            [_ for _ in importcompletion.find_iterator]
            r.dumb_print_output()
            r.dumb_input(refreshes)

if __name__ == '__main__':
    simple_repl()
