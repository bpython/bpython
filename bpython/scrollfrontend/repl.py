import sys
import os
import re
import logging
import code
import threading
import Queue
from cStringIO import StringIO
import traceback
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

from fmtstr.fsarray import FSArray
from fmtstr.fmtstr import fmtstr, FmtStr
from fmtstr.bpythonparse import parse as bpythonparse
from fmtstr.bpythonparse import func_for_letter, color_for_letter
from fmtstr.events import pp_event

from bpython.scrollfrontend.manual_readline import char_sequences as rl_char_sequences
from bpython.scrollfrontend.manual_readline import get_updated_char_sequences
from bpython.scrollfrontend.abbreviate import substitute_abbreviations
from bpython.scrollfrontend.interaction import StatusBar
from bpython.scrollfrontend import sitefix; sitefix.monkeypatch_quit()
import bpython.scrollfrontend.replpainter as paint
import fmtstr.events as events
from bpython.scrollfrontend.friendly import NotImplementedError
from bpython.scrollfrontend.coderunner import CodeRunner, FakeOutput

#TODO implement paste mode and figure out what the deal with config.paste_time is
#TODO figure out how config.auto_display_list=False behaves and implement it
#TODO figure out how config.list_win_visible behaves and implement it
#TODO other autocomplete modes
#TODO figure out what config.flush_output is
#TODO figure out what options.quiet is
#TODO execute file if in args
#TODO proper raw_input (currently input isn't visible while typing, includes \r, and comes in as unicode in Python 2
#TODO use events instead of length-one queues for interthread communication

from bpython.keys import cli_key_dispatch as key_dispatch

class FakeStdin(object):
    def __init__(self, coderunner, repl):
        self.coderunner = coderunner
        self.repl = repl
        self.has_focus = False
        self.current_line = ''
        self.cursor_offset_in_line = 0
        self.old_num_lines = 0

    def process_event(self, e):
        assert self.has_focus
        if e in rl_char_sequences:
            self.cursor_offset_in_line, self.current_line = rl_char_sequences[e](self.cursor_offset_in_line, self._current_line)
            #TODO EOF on ctrl-d
        else: # add normal character
            logging.debug('adding normal char %r to current line', e)
            self.current_line = (self.current_line[:self.cursor_offset_in_line] +
                                 e +
                                 self.current_line[self.cursor_offset_in_line:])
            self.cursor_offset_in_line += 1

        if self.current_line.endswith(("\n", "\r")):
            self.has_focus = False
            line = self.current_line
            self.current_line = ''
            self.cursor_offset_in_line = 0
            self.repl.coderunner.run_code(input=line)
        else:
            self.repl.send_to_stdin(self.current_line)

    def readline(self):
        self.has_focus = True
        self.repl.send_to_stdin(self.current_line)
        return self.coderunner._blocking_wait_for(None)


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
    def __init__(self, locals_=None, config=None, stuff_a_refresh_request=None):
        logging.debug("starting init")
        interp = code.InteractiveInterpreter(locals=locals_)

        if config is None:
            config = Struct()
            loadini(config, default_config_path())

        config.autocomplete_mode = SIMPLE # only one implemented currently

        if config.cli_suggestion_width <= 0 or config.cli_suggestion_width > 1:
            config.cli_suggestion_width = 1

        self.status_bar = StatusBar(_('welcome to bpython'), _(
            " <%s> Rewind  <%s> Save  <%s> Pastebin <%s> Editor"
            ) % (config.undo_key, config.save_key, config.pastebin_key, config.external_editor_key))
        self.rl_char_sequences = get_updated_char_sequences(key_dispatch, config)
        logging.debug("starting parent init")
        super(Repl, self).__init__(interp, config)
        self.formatter = BPythonFormatter(config.color_scheme)
        self.interact = self.status_bar # overwriting what bpython.Repl put there
                                        # interact is called to interact with the status bar,
                                        # so we're just using the same object
        self._current_line = '' # line currently being edited, without '>>> '
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

        self.coderunner = CodeRunner(self.interp, stuff_a_refresh_request)
        self.stdout = FakeOutput(self.coderunner, self.send_to_stdout)
        self.stdin = FakeStdin(self.coderunner, self)

        self.paste_mode = False
        self.request_paint_to_clear_screen = False
        self.last_events = [None] * 50
        self.presentation_mode = False

        self.width = None  # will both be set by a window resize event
        self.height = None
        self.start_background_tasks()

    def __enter__(self):
        self.orig_stdout = sys.stdout
        self.orig_stderr = sys.stderr
        self.orig_stdin = sys.stdin
        sys.stdout = self.stdout
        sys.stderr = StringIO()
        sys.stdin = self.stdin
        return self

    def __exit__(self, *args):
        sys.stderr.seek(0)
        s = sys.stderr.read()
        self.orig_stderr.write(s)
        sys.stdout = self.orig_stdout
        sys.stderr = self.orig_stderr

    def start_background_tasks(self):
        t = threading.Thread(target=self.importcompletion_thread)
        t.daemon = True
        t.start()

    def importcompletion_thread(self):
        """quick tasks we want to do bits of during downtime"""
        while importcompletion.find_coroutine(): # returns None when fully initialized
            pass

    def clean_up_current_line_for_exit(self):
        """Called when trying to exit to prep for final paint"""
        logging.debug('unhighlighting paren for exit')
        self.cursor_offset_in_line = -1
        self.unhighlight_paren()

    ## Event handling
    def process_event(self, e):
        """Returns True if shutting down, otherwise mutates state of Repl object"""

        logging.debug("processing event %r", e)
        if isinstance(e, events.RefreshRequestEvent):
            self.run_runsource_part_2_when_finished()
            return
        self.last_events.append(e)
        self.last_events.pop(0)
        if isinstance(e, events.WindowChangeEvent):
            logging.debug('window change to %d %d', e.width, e.height)
            self.width, self.height = e.width, e.height
            return
        if self.status_bar.has_focus:
            return self.status_bar.process_event(e)
        if self.stdin.has_focus:
            return self.stdin.process_event(e)

        if e in self.rl_char_sequences:
            self.cursor_offset_in_line, self._current_line = self.rl_char_sequences[e](self.cursor_offset_in_line, self._current_line)
            self.update_completion()

        # readline history commands
        elif e in ("[A", "KEY_UP") + key_dispatch[self.config.up_one_line_key]:
            self.rl_history.enter(self._current_line)
            self._current_line = self.rl_history.back(False)
            self.cursor_offset_in_line = len(self._current_line)
            self.update_completion()
        elif e in ("[B", "KEY_DOWN") + key_dispatch[self.config.down_one_line_key]:
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
        elif e in key_dispatch[self.config.suspend_key]: #TODO
            raise SystemExit()
        elif e == "":
            raise KeyboardInterrupt()
        elif e in ("",) + key_dispatch[self.config.exit_key]:
            raise SystemExit()
        elif e in ("\n", "\r", "PAD_ENTER"):
            self.on_enter()
            self.update_completion()
        elif e in ["\x00", "\x11"]:
            pass #dunno what these are, but they screw things up #TODO find out
            #TODO use a whitelist instead of a blacklist!
        elif e == '\t': # tab
            self.on_tab()
        elif e in ('[Z', "KEY_BTAB"): # shift-tab
            self.on_tab(back=True)
        elif e in ('',) + key_dispatch[self.config.undo_key]:
            self.undo()
            self.update_completion()
        elif e in ('\x13',) + key_dispatch[self.config.save_key]: # ctrl-s for save
            t = threading.Thread(target=self.write2file)
            t.daemon = True
            logging.debug('starting write2file thread')
            t.start()
            self.interact.wait_for_request_or_notify()
        # F8 for pastebin
        elif e in ('\x1b[19~',) + key_dispatch[self.config.pastebin_key]:
            t = threading.Thread(target=self.pastebin)
            t.daemon = True
            logging.debug('starting pastebin thread')
            t.start()
            self.interact.wait_for_request_or_notify()
        elif e in key_dispatch[self.config.external_editor_key]:
            self.send_to_external_editor()
        #TODO add PAD keys hack as in bpython.cli
        else:
            self.add_normal_character(e if len(e) == 1 else e[-1]) #strip control seq
            self.update_completion()

    def on_enter(self, insert_into_history=True):
        self.cursor_offset_in_line = -1 # so the cursor isn't touching a paren
        self.unhighlight_paren()        # in unhighlight_paren
        self.highlighted_paren = None

        self.rl_history.append(self._current_line)
        self.rl_history.last()
        self.history.append(self._current_line)
        self.push(self._current_line, insert_into_history=insert_into_history)

    def send_to_stdout(self, output):
        self.display_lines.extend(sum([paint.display_linize(line, self.width) for line in output.split('\n')], []))

    def send_to_stdin(self, line):
        self.display_lines = self.display_lines[:len(self.display_lines) - self.stdin.old_num_lines]
        lines = paint.display_linize(line, self.width)
        self.stdin.old_num_lines = len(lines)
        self.display_lines.extend(paint.display_linize(line, self.width))


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
        self.cursor_offset_in_line, self._current_line = substitute_abbreviations(self.cursor_offset_in_line, self._current_line)
        #TODO deal with characters that take up more than one space? do we care?

    def update_completion(self, tab=False):
        """Update autocomplete info; self.matches and self.argspec"""
        #TODO do we really have to do something this ugly? Can we rename it?
        # this method stolen from bpython.cli
        if self.paste_mode:
            return

        if self.list_win_visible and not self.config.auto_display_list:
            self.list_win_visible = False
            self.matches_iter.update(self.current_word)
            return

        if self.config.auto_display_list or tab:
            self.list_win_visible = BpythonRepl.complete(self, tab)

    def push(self, line, insert_into_history=True):
        """Push a line of code onto the buffer, run the buffer

        If the interpreter successfully runs the code, clear the buffer
        """
        if insert_into_history:
            self.insert_into_history(line)
        self.runsource(line)

    def runsource(self, line):
        """Push a line of code on to the buffer, run the buffer, clean up

        Makes requests for input and announces being done as necessary via threadsafe queue
        sends messages:
            * request for readline
            * (stdoutput, error, done?, amount_to_indent_next_line)
        """
        self.buffer.append(line)
        indent = len(re.match(r'[ ]*', line).group())

        if line.endswith(':'):
            indent = max(0, indent + self.config.tab_length)
        elif line and line.count(' ') == len(self._current_line):
            indent = max(0, indent - self.config.tab_length)
        elif line and ':' not in line and line.strip().startswith(('return', 'pass', 'raise', 'yield')):
            indent = max(0, indent - self.config.tab_length)
        err_spot = sys.stderr.tell()
        logging.debug('running %r in interpreter', self.buffer)
        self.coderunner.load_code('\n'.join(self.buffer))
        self.saved_err_spot = err_spot
        self.saved_indent = indent
        self.saved_line = line

        #current line not added to display buffer if quitting
        if self.config.syntax:
            self.display_buffer.append(bpythonparse(format(self.tokenize(line), self.formatter)))
        else:
            self.display_buffer.append(fmtstr(line))

        try:
            c = code.compile_command('\n'.join(self.buffer))
        except (ValueError, SyntaxError, ValueError):
            c = error = True
        if c:
            logging.debug('finished - buffer cleared')
            self.display_lines.extend(self.display_buffer_lines)
            self.display_buffer = []
            self.buffer = []

        self.run_runsource_part_2_when_finished()

    def run_runsource_part_2_when_finished(self):
        r = self.coderunner.run_code()
        if r:
            unfinished = r == 'unfinished'
            self.runsource_part_2(self.saved_line, self.saved_err_spot, unfinished, self.saved_indent)

    def runsource_part_2(self, line, err_spot, unfinished, indent):
        sys.stderr.seek(err_spot)
        err = sys.stderr.read()

        # easier debugging: save only errors that aren't from this interpreter
        oldstderr = sys.stderr
        sys.stderr = StringIO()
        oldstderr.seek(0)
        sys.stderr.write(oldstderr.read(err_spot))

        if unfinished and not err:
            logging.debug('unfinished - line added to buffer')
            output, error, done = None, None, False
        else:
            if err:
                indent = 0
            logging.debug('sending output info')
            output, error, done = None, err[:-1], True
            logging.debug('sent output info')

        if error:
            self.display_lines.extend([func_for_letter(self.config.color_scheme['error'])(line)
                                      for line in sum([paint.display_linize(line, self.width)
                                                      for line in error.split('\n')], [])])
        self._current_line = ' '*indent
        self.cursor_offset_in_line = len(self._current_line)
        self.done = done

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
            self.display_buffer[lineno][:len(new)] = new


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
        show_status_bar = bool(self.status_bar.current_line) and (self.config.scroll_fill_terminal or self.status_bar.has_focus)
        if show_status_bar:
            min_height -= 1

        current_line_start_row = len(self.lines_for_display) - max(0, self.scroll_offset)
        if self.request_paint_to_clear_screen: # or show_status_bar and about_to_exit ?
            self.request_paint_to_clear_screen = False
            arr = FSArray(self.height - 1 + current_line_start_row, width)
        else:
            arr = FSArray(0, width)
        #TODO test case of current line filling up the whole screen (there aren't enough rows to show it)

        if current_line_start_row < 0: #if current line trying to be drawn off the top of the screen
            #assert True, 'no room for current line: contiguity of history broken!'
            msg = "#<---History contiguity broken by rewind--->"
            arr[0, 0:min(len(msg), width)] = [msg[:width]]

            # move screen back up a screen minus a line
            self.scroll_offset = self.scroll_offset - self.height

            current_line_start_row = len(self.lines_for_display) - max(-1, self.scroll_offset)

            history = paint.paint_history(current_line_start_row - 1, width, self.lines_for_display)
            arr[1:history.height+1,:history.width] = history

            if arr.height <= min_height:
                arr[min_height, 0] = ' ' # force scroll down to hide broken history message
        else:
            history = paint.paint_history(current_line_start_row, width, self.lines_for_display)
            arr[:history.height,:history.width] = history

        current_line = paint.paint_current_line(min_height, width, self.display_line_with_prompt)
        arr[current_line_start_row:current_line_start_row + current_line.height,
            0:current_line.width] = current_line

        if current_line.height > min_height:
            return arr, (0, 0) # short circuit, no room for infobox

        lines = paint.display_linize(self.display_line_with_prompt+'X', width)
                                       # extra character for space for the cursor
        cursor_row = current_line_start_row + len(lines) - 1
        cursor_column = (self.cursor_offset_in_line + len(self.display_line_with_prompt) - len(self._current_line)) % width

        if self.list_win_visible:
            #infobox not properly expanding window! try reduce( docs about halfway down a 80x24 terminal
            #TODO what's the desired behavior here? Currently uses only the space already on screen,
            # scrolling down only if there would have been more space above the current line, but being forced to put below
            #TODO above description is not accurate - sometimes screen scrolls for docstring message
            logging.debug('infobox display code running')
            visible_space_above = history.height
            visible_space_below = min_height - cursor_row - 1

            info_max_rows = max(visible_space_above, visible_space_below)
            infobox = paint.paint_infobox(info_max_rows, int(width * self.config.cli_suggestion_width), self.matches, self.argspec, self.current_word, self.docstring, self.config)

            if visible_space_above >= infobox.height and self.config.scroll_list_above:
                arr[current_line_start_row - infobox.height:current_line_start_row, 0:infobox.width] = infobox
            else:
                arr[cursor_row + 1:cursor_row + 1 + infobox.height, 0:infobox.width] = infobox
                logging.debug('slamming infobox of shape %r into arr of shape %r', infobox.shape, arr.shape)

        logging.debug('about to exit: %r', about_to_exit)
        if show_status_bar:
            if self.config.scroll_fill_terminal:
                if about_to_exit:
                    arr[max(arr.height, min_height), :] = FSArray(1, width)
                else:
                    arr[max(arr.height, min_height), :] = paint.paint_statusbar(1, width, self.status_bar.current_line, self.config)

                    if self.presentation_mode:
                        rows = arr.height
                        columns = arr.width
                        last_key_box = paint.paint_last_events(rows, columns, [pp_event(x) for x in self.last_events if x])
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
        return arr, (cursor_row, cursor_column)

    ## Debugging shims
    def dumb_print_output(self):
        arr, cpos = self.paint()
        arr[cpos[0], cpos[1]] = '~'
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

    def dumb_input(self):
        for c in self.orig_stdin.readline()[:-1]:
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
        #TODO other implementations have a enter no-history method, could do
        # that instead of clearing history and getting it rewritten
        old_logical_lines = self.history
        self.history = []
        self.display_lines = []

        self.done = True # this keeps the first prompt correct
        self.interp = code.InteractiveInterpreter()
        self.completer = Autocomplete(self.interp.locals, self.config)
        self.completer.autocomplete_mode = 'simple'
        self.buffer = []
        self.display_buffer = []
        self.highlighted_paren = None

        for line in old_logical_lines:
            self._current_line = line
            self.on_enter(insert_into_history=insert_into_history)
        self.cursor_offset_in_line = 0
        self._current_line = ''
    def getstdout(self):
        lines = self.lines_for_display + [self.current_line_formatted]
        s = '\n'.join([x.s if isinstance(x, FmtStr) else x
                       for x in lines]) if lines else ''
        return s
    def send_to_external_editor(self, filename=None):
        editor = os.environ.get('VISUAL', os.environ.get('EDITOR', 'vim'))
        text = self.getstdout()
        with tempfile.NamedTemporaryFile(suffix='.py') as temp:
            temp.write('### current bpython session - file will be reevaluated, ### lines will not be run\n'.encode('utf8'))
            temp.write('\n'.join(line[4:] if line[:4] in ('... ', '>>> ') else '### '+line
                                 for line in text.split('\n')).encode('utf8'))
            temp.flush()
            subprocess.call([editor, temp.name])
            self.history = [line for line in open(temp.name).read().split('\n')
                                 if line[:4] != '### ']
        self.reevaluate(insert_into_history=True)

def simple_repl():
    with Repl() as r:
        r.width = 50
        r.height = 10
        while True:
            scrolled = r.dumb_print_output()
            r.scroll_offset += scrolled
            r.dumb_input()

if __name__ == '__main__':
    simple_repl()
