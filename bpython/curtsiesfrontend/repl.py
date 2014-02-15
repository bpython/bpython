import sys
import os
import re
import logging
import code
import threading
import greenlet
import subprocess
import tempfile

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
from bpython.curtsiesfrontend.friendly import NotImplementedError
from bpython.curtsiesfrontend.coderunner import CodeRunner, FakeOutput

#TODO implement paste mode and figure out what the deal with config.paste_time is
#TODO figure out how config.auto_display_list=False behaves and implement it
#TODO figure out how config.list_win_visible behaves and implement it, or toss
#TODO other autocomplete modes (also fix in other bpython implementations)
#TODO figure out what config.flush_output is
#TODO figure out what options.quiet is
#TODO add buffering to stdout to speed up output.

from bpython.keys import cli_key_dispatch as key_dispatch

class FakeStdin(object):
    def __init__(self, coderunner, repl):
        self.coderunner = coderunner
        self.repl = repl
        self.has_focus = False
        self.current_line = ''
        self.cursor_offset_in_line = 0
        self.old_num_lines = 0
        self.readline_results = []

    def process_event(self, e):
        assert self.has_focus
        if e in rl_char_sequences:
            self.cursor_offset_in_line, self.current_line = rl_char_sequences[e](self.cursor_offset_in_line, self.current_line)
        elif isinstance(e, events.SigIntEvent):
            self.coderunner.sigint_happened = True
            self.has_focus = False
            self.current_line = ''
            self.cursor_offset_in_line = 0
            self.repl.run_code_and_maybe_finish()
        else: # add normal character
            logging.debug('adding normal char %r to current line', e)
            c = e if py3 else e.encode('utf8')
            self.current_line = (self.current_line[:self.cursor_offset_in_line] +
                                 c +
                                 self.current_line[self.cursor_offset_in_line:])
            self.cursor_offset_in_line += 1

        if self.current_line.endswith(("\n", "\r")):
            line = self.current_line
            self.repl.send_to_stdin(line)
            self.has_focus = False
            self.current_line = ''
            self.cursor_offset_in_line = 0
            #self.repl.coderunner.run_code(for_code=line)
            self.repl.run_code_and_maybe_finish(for_code=line)
        else:
            self.repl.send_to_stdin(self.current_line)

    def readline(self):
        self.has_focus = True
        self.repl.send_to_stdin(self.current_line)
        value = self.coderunner.wait_and_get_value()
        self.readline_results.append(value)
        return value

class ReevaluateFakeStdin(object):
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
    """

    takes in:
     -terminal dimensions and change events
     -keystrokes
     -number of scroll downs necessary to render array
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
    def __init__(self, locals_=None, config=None, stuff_a_refresh_request=lambda: None, banner=None):
        logging.debug("starting init")

        if config is None:
            config = Struct()
            loadini(config, default_config_path())

        interp = code.InteractiveInterpreter(locals=locals_)

        if banner is None:
            banner = _('welcome to bpython')

        config.autocomplete_mode = SIMPLE # only one implemented currently

        if config.cli_suggestion_width <= 0 or config.cli_suggestion_width > 1:
            config.cli_suggestion_width = 1

        self.reevaluating = False
        self.fake_refresh_request = False
        def request_refresh():
            if self.reevaluating:
                self.fake_refresh_request = True
            else:
                stuff_a_refresh_request()
        self.stuff_a_refresh_request = request_refresh

        self.status_bar = StatusBar(banner if config.curtsies_fill_terminal else '', _(
            " <%s> Rewind  <%s> Save  <%s> Pastebin <%s> Editor"
            ) % (config.undo_key, config.save_key, config.pastebin_key, config.external_editor_key),
            stuff_a_refresh_request=self.stuff_a_refresh_request
            )
        self.rl_char_sequences = get_updated_char_sequences(key_dispatch, config)
        logging.debug("starting parent init")
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
        self.scroll_offset = 0
        self.cursor_offset_in_line = 0 # from the left, 0 means first char
        self.done = True

        self.coderunner = CodeRunner(self.interp, request_refresh)
        self.stdout = FakeOutput(self.coderunner, self.send_to_stdout)
        self.stderr = FakeOutput(self.coderunner, self.send_to_stderr)
        self.stdin = FakeStdin(self.coderunner, self)

        self.request_paint_to_clear_screen = False
        self.last_events = [None] * 50
        self.presentation_mode = False
        self.paste_events = None

        self.width = None  # will both be set by a window resize event
        self.height = None
        self.start_background_tasks()

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

    def start_background_tasks(self):
        t = threading.Thread(target=self.importcompletion_thread)
        t.daemon = True
        t.start()

    def importcompletion_thread(self):
        """task that should run on startup in the background"""
        #TODO use locks or something to avoid error on import completion right at startup
        while importcompletion.find_coroutine(): # returns None when fully initialized
            pass

    def clean_up_current_line_for_exit(self):
        """Called when trying to exit to prep for final paint"""
        logging.debug('unhighlighting paren for exit')
        self.cursor_offset_in_line = -1
        self.unhighlight_paren()

    def process_paste_events(self):
        for ee in self.paste_events:
            if isinstance(ee, events.Event):
                pass
            else:
                if ee in ("\n", "\r", "PAD_ENTER"):
                    self.on_enter()
                    break
                elif isinstance(ee, events.Event):
                    pass # ignore events in a paste
                else:
                    self.add_normal_character(ee if len(ee) == 1 else ee[-1]) #strip control seq
        else:
            self.self.paste_events = None
            self.update_completion()

    ## Event handling
    def process_event(self, e):
        """Returns True if shutting down, otherwise mutates state of Repl object"""
        # event names uses here are curses compatible, or the full names
        # for a full list of what should have pretty names, see curtsies.events.CURSES_TABLE

        if not isinstance(e, events.Event):
            self.last_events.append(e)
            self.last_events.pop(0)

        result = None
        logging.debug("processing event %r", e)
        if isinstance(e, events.RefreshRequestEvent):
            if self.paste_events:
                self.process_paste_events()
            elif self.status_bar.has_focus:
                self.status_bar.process_event(e)
            else:
                assert self.coderunner.code_is_waiting
                self.run_code_and_maybe_finish()
        elif isinstance(e, events.WindowChangeEvent):
            logging.debug('window change to %d %d', e.width, e.height)
            self.width, self.height = e.width, e.height
        elif self.status_bar.has_focus:
            result = self.status_bar.process_event(e)
        elif self.stdin.has_focus:
            result = self.stdin.process_event(e)

        elif isinstance(e, events.SigIntEvent):
            logging.debug('received sigint event')
            self.keyboard_interrupt()
            self.update_completion()
            return
        elif isinstance(e, events.PasteEvent):
            self.paste_events = (event for event in e.events)
            self.process_paste_events()

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
        elif e in key_dispatch[self.config.search_key]: #TODO
            raise NotImplementedError()
        #TODO add rest of history commands

        # Need to figure out what these are, but I think they belong in manual_realine
        # under slightly different names
        elif e in key_dispatch[self.config.cut_to_buffer_key]: #TODO
            raise NotImplementedError()
        elif e in key_dispatch[self.config.yank_from_buffer_key]: #TODO
            raise NotImplementedError()

        elif e in key_dispatch[self.config.clear_screen_key]:
            self.request_paint_to_clear_screen = True
        elif e in key_dispatch[self.config.last_output_key]: #TODO
            raise NotImplementedError()
        elif e in key_dispatch[self.config.show_source_key]: #TODO
            raise NotImplementedError()
        elif e in key_dispatch[self.config.suspend_key]:
            raise SystemExit()
        elif e in ("",) + key_dispatch[self.config.exit_key]:
            if self._current_line == '':
                raise SystemExit()
        elif e in ("\n", "\r", "PAD_ENTER"):
            self.on_enter()
            self.update_completion()
        elif e in ["\x00", "\x11"]:
            pass #dunno what these are, but they screw things up #TODO find out
            #TODO use a whitelist instead of a blacklist!
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
            self.send_to_external_editor()
        #TODO add PAD keys hack as in bpython.cli
        else:
            self.add_normal_character(e if len(e) == 1 else e[-1]) #strip control seq
            self.update_completion()

        return result

    def on_enter(self, insert_into_history=True):
        self.cursor_offset_in_line = -1 # so the cursor isn't touching a paren
        self.unhighlight_paren()        # in unhighlight_paren
        self.highlighted_paren = None

        self.rl_history.append(self._current_line)
        self.rl_history.last()
        self.history.append(self._current_line)
        line = self._current_line
        #self._current_line = ''
        self.push(line, insert_into_history=insert_into_history)

    def send_to_stdout(self, output):
        lines = output.split('\n')
        logging.debug('display_lines: %r', self.display_lines)
        if len(lines) and lines[0]:
            self.current_stdouterr_line += lines[0]
        if len(lines) > 1:
            self.display_lines.extend(paint.display_linize(self.current_stdouterr_line, self.width))
            self.display_lines.extend(sum([paint.display_linize(line, self.width) for line in lines[1:-1]], []))
            self.current_stdouterr_line = lines[-1]
        logging.debug('display_lines: %r', self.display_lines)

    def send_to_stderr(self, error):
        #self.send_to_stdout(error)
        self.display_lines.extend([func_for_letter(self.config.color_scheme['error'])(line)
                                   for line in sum([paint.display_linize(line, self.width)
                                                    for line in error.split('\n')], [])])

    def send_to_stdin(self, line):
        if line.endswith('\n'):
            self.display_lines.extend(paint.display_linize(self.current_output_line[:-1], self.width))
            self.current_output_line = ''
        #self.display_lines = self.display_lines[:len(self.display_lines) - self.stdin.old_num_lines]
        #lines = paint.display_linize(line, self.width)
        #self.stdin.old_num_lines = len(lines)
        #self.display_lines.extend(paint.display_linize(line, self.width))
        pass


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

        logging.debug('self.matches: %r', self.matches)
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

    ## Handler Helpers
    def add_normal_character(self, char):
        assert len(char) == 1, repr(char)
        self._current_line = (self._current_line[:self.cursor_offset_in_line] +
                             char +
                             self._current_line[self.cursor_offset_in_line:])
        self.cursor_offset_in_line += 1
        if self.config.cli_trim_prompts and self._current_line.startswith(">>> "):
            self._current_line = self._current_line[4:]
            self.cursor_offset_in_line = max(0, self.cursor_offset_in_line - 4)
        #TODO deal with characters that take up more than one space? do we care?

    def update_completion(self, tab=False):
        """Update autocomplete info; self.matches and self.argspec"""
        #TODO do we really have to do something this ugly? Can we rename it?
        # this method stolen from bpython.cli

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
        if insert_into_history:
            self.insert_into_history(line)
        self.buffer.append(line)
        indent = len(re.match(r'[ ]*', line).group())

        if line.endswith(':'):
            indent = max(0, indent + self.config.tab_length)
        elif line and line.count(' ') == len(line):
            indent = max(0, indent - self.config.tab_length)
        elif line and ':' not in line and line.strip().startswith(('return', 'pass', 'raise', 'yield')):
            indent = max(0, indent - self.config.tab_length)
        logging.debug('running %r in interpreter', self.buffer)
        code_to_run = '\n'.join(self.buffer)
        self.saved_indent = indent

        #current line not added to display buffer if quitting #TODO I don't understand this comment
        if self.config.syntax:
            self.display_buffer.append(bpythonparse(format(self.tokenize(line), self.formatter)))
        else:
            self.display_buffer.append(fmtstr(line))

        try:
            c = bool(code.compile_command('\n'.join(self.buffer)))
            self.saved_predicted_parse_error = False
        except (ValueError, SyntaxError, OverflowError):
            c = self.saved_predicted_parse_error = True
        if c:
            logging.debug('finished - buffer cleared')
            self.display_lines.extend(self.display_buffer_lines)
            self.display_buffer = []
            self.buffer = []
            self.cursor_offset_in_line = 0

        self.coderunner.load_code(code_to_run)
        self.run_code_and_maybe_finish()

    def run_code_and_maybe_finish(self, for_code=None):
        r = self.coderunner.run_code(for_code=for_code)
        if r:
            logging.debug("----- Running finish command stuff -----")
            logging.debug("saved_indent: %r", self.saved_indent)
            unfinished = r == 'unfinished'
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
            self.done = not unfinished

    def keyboard_interrupt(self):
        #TODO factor out the common cleanup from running a line
        #TODO make rewind work properly with ctrl-c'd infinite loops
        self.cursor_offset_in_line = -1
        self.unhighlight_paren()
        self.display_lines.extend(self.display_buffer_lines)
        self.display_lines.extend(paint.display_linize(self.current_cursor_line, self.width))
        self.display_lines.extend(paint.display_linize("KeyboardInterrupt", self.width))

        self.display_buffer = []
        self.buffer = []
        self.cursor_offset_in_line = 0
        self.saved_indent = 0
        self._current_line = ''
        self.cursor_offset_in_line = len(self._current_line)
        self.done = True

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
            logging.debug('trying to unhighlight a paren on line %r', lineno)
            logging.debug('with these tokens: %r', saved_tokens)
            new = bpythonparse(format(saved_tokens, self.formatter))
            self.display_buffer[lineno] = self.display_buffer[lineno].setslice(0, len(new), new)


    ## formatting, output
    @property
    def current_line_formatted(self):
        if self.config.syntax:
            fs = bpythonparse(format(self.tokenize(self._current_line), self.formatter))
        else:
            fs = fmtstr(self._current_line)
        if hasattr(self, 'old_fs') and str(fs) != str(self.old_fs):
            pass
            #logging.debug('calculating current formatted line: %r', repr(fs))
        self.old_fs = fs
        return fs

    @property
    def lines_for_display(self):
        return self.display_lines + self.display_buffer_lines

    @property
    def current_word(self):
        words = re.split(r'([\w_][\w0-9._]*[(]?)', self._current_line)
        chars = 0
        cw = None
        for word in words:
            chars += len(word)
            if chars == self.cursor_offset_in_line and word and word.count(' ') == 0:
                cw = word
        if cw and re.match(r'^[\w_][\w0-9._]*[(]?$', cw):
            return cw

    @current_word.setter
    def current_word(self, value):
        # current word means word cursor is at the end of, so delete from cursor back to [ ."']
        pos = self.cursor_offset_in_line - 1
        if pos > -1 and self._current_line[pos] not in tuple(' :)'):
            pos -= 1
        while pos > -1 and self._current_line[pos] not in tuple(' :()\'"'):
            pos -= 1
        start = pos + 1; del pos
        self._current_line = self._current_line[:start] + value + self._current_line[self.cursor_offset_in_line:]
        self.cursor_offset_in_line = start + len(value)

    @property
    def display_buffer_lines(self):
        """The lines build from the display buffer"""
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
        return (func_for_letter(self.config.color_scheme['prompt'])(self.ps1)
                if self.done else
                func_for_letter(self.config.color_scheme['prompt_more'])(self.ps2)) + self.current_line_formatted

    @property
    def current_cursor_line(self):
        value = (self.current_output_line +
                ('' if self.coderunner.running else self.display_line_with_prompt))
        logging.debug('current cursor line: %r', value)
        return value

    @property
    def current_output_line(self):
        return self.current_stdouterr_line + self.stdin.current_line

    @current_output_line.setter
    def current_output_line(self, value):
        self.current_stdouterr_line = ''
        self.stdin.current_line = '\n'

    def paint(self, about_to_exit=False):
        """Returns an array of min_height or more rows and width columns, plus cursor position

        Paints the entire screen - ideally the terminal display layer will take a diff and only
        write to the screen in portions that have changed, but the idea is that we don't need
        to worry about that here, instead every frame is completely redrawn because
        less state is cool!
        """

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
            #assert True, 'no room for current line: contiguity of history broken!'
            logging.debug('#<---History contiguity broken by rewind--->')
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
        if about_to_exit == 2: # hack for quit() in user code
            current_line_start_row = current_line_start_row - current_line.height
        logging.debug("---current line row slice %r, %r", current_line_start_row, current_line_start_row + current_line.height)
        logging.debug("---current line col slice %r, %r", 0, current_line.width)
        arr[current_line_start_row:current_line_start_row + current_line.height,
            0:current_line.width] = current_line

        if current_line.height > min_height:
            return arr, (0, 0) # short circuit, no room for infobox

        lines = paint.display_linize(self.current_cursor_line+'X', width)
                                       # extra character for space for the cursor
        cursor_row = current_line_start_row + len(lines) - 1
        if self.stdin.has_focus:
            cursor_column = (len(self.current_stdouterr_line) + self.stdin.cursor_offset_in_line) % width
            assert cursor_column >= 0, cursor_column
        elif self.coderunner.running:
            cursor_column = (len(self.current_cursor_line) + self.cursor_offset_in_line) % width
            assert cursor_column >= 0, (cursor_column, len(self.current_cursor_line), len(self._current_line), self.cursor_offset_in_line)
        else:
            cursor_column = (len(self.current_cursor_line) - len(self._current_line) + self.cursor_offset_in_line) % width
            assert cursor_column >= 0, (cursor_column, len(self.current_cursor_line), len(self._current_line), self.cursor_offset_in_line)

        if self.list_win_visible:
            logging.debug('infobox display code running')
            visible_space_above = history.height
            visible_space_below = min_height - cursor_row - 1

            info_max_rows = max(visible_space_above, visible_space_below)
            infobox = paint.paint_infobox(info_max_rows, int(width * self.config.cli_suggestion_width), self.matches, self.argspec, self.current_word, self.docstring, self.config)

            if visible_space_above >= infobox.height and self.config.curtsies_list_above:
                arr[current_line_start_row - infobox.height:current_line_start_row, 0:infobox.width] = infobox
            else:
                arr[cursor_row + 1:cursor_row + 1 + infobox.height, 0:infobox.width] = infobox
                logging.debug('slamming infobox of shape %r into arr of shape %r', infobox.shape, arr.shape)

        logging.debug('about to exit: %r', about_to_exit)
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
        logging.debug('returning arr of size %r', arr.shape)
        logging.debug('cursor pos: %r', (cursor_row, cursor_column))
        return arr, (cursor_row, cursor_column)

    ## Debugging shims
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
            my_print('X```'+(line if line else ' '*len(line))+'```X')
        logging.debug('line:')
        logging.debug(repr(line))
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
                c = '[19~'
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
        logging.debug("echo called with %r" % msg)
    def cw(self):
        """Returns the "current word", based on what's directly left of the cursor.
        examples inclue "socket.socket.metho" or "self.reco" or "yiel" """
        return self.current_word
    @property
    def cpos(self):
        "many WATs were had - it's the pos from the end of the line back"""
        return len(self._current_line) - self.cursor_offset_in_line
    def reprint_line(self, lineno, tokens):
        logging.debug("calling reprint line with %r %r", lineno, tokens)
        if self.config.syntax:
            self.display_buffer[lineno] = bpythonparse(format(tokens, self.formatter))
    def reevaluate(self, insert_into_history=False):
        """bpython.Repl.undo calls this"""
        old_logical_lines = self.history
        self.history = []
        self.display_lines = []

        self.done = True # this keeps the first prompt correct
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
            while self.fake_refresh_request:
                self.fake_refresh_request = False
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
    def send_to_external_editor(self, filename=None):
        editor = os.environ.get('VISUAL', os.environ.get('EDITOR', 'vim'))
        editor_args = editor.split()
        text = self.getstdout()
        with tempfile.NamedTemporaryFile(suffix='.py') as temp:
            temp.write('### current bpython session - file will be reevaluated, ### lines will not be run\n'.encode('utf8'))
            temp.write('\n'.join(line[4:] if line[:4] in ('... ', '>>> ') else '### '+line
                                 for line in text.split('\n')).encode('utf8'))
            temp.flush()
            subprocess.call(editor_args + [temp.name])
            lines = open(temp.name).read().split('\n')
            self.history = [line for line in lines
                                 if line[:4] != '### ']
        self.reevaluate(insert_into_history=True)
        self._current_line = lines[-1][4:]
        self.cursor_offset_in_line = len(self._current_line)

def simple_repl():
    refreshes = []
    def request_refresh():
        refreshes.append(1)
    with Repl(stuff_a_refresh_request=request_refresh) as r:
        r.width = 50
        r.height = 10
        while True:
            scrolled = r.dumb_print_output()
            r.scroll_offset += scrolled
            r.dumb_input(refreshes)

if __name__ == '__main__':
    simple_repl()
