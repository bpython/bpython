import sys
import os
import re
import logging
import code
import threading
from cStringIO import StringIO

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
from fmtstr.bpythonparse import func_for_letter

from bpython.scrollfrontend.manual_readline import get_updated_char_sequences
from bpython.scrollfrontend.abbreviate import substitute_abbreviations
from bpython.scrollfrontend.interaction import StatusBar
from bpython.scrollfrontend import sitefix; sitefix.monkeypatch_quit()
import bpython.scrollfrontend.replpainter as paint
import fmtstr.events as events
from bpython.scrollfrontend.friendly import NotImplementedError

PROMPTCOLOR = 'cyan'
INFOBOX_ONLY_BELOW = True

#TODO implement paste mode and figure out what the deal with config.paste_time is
#TODO check config.auto_display_list
#TODO figure out how config.list_win_visible behaves and implement it
#TODO config.cli_trim_prompts
#TODO implement config.syntax
#TODO implement config.color_scheme['prompt'] and ['prompt_more]
#TODO other autocomplete modes even though I hate them
#TODO config.colors_scheme['error']
#TODO better status bar message - keybindings like bpython.cli.init_wins
#TODO figure out what config.flush_output is

#TODO options.interactive, .quiet
#TODO execute file if in args

logging.basicConfig(level=logging.DEBUG, filename='repl.log', datefmt='%M:%S')

from bpython.keys import cli_key_dispatch as key_dispatch

class Repl(BpythonRepl):
    """

    takes in:
     -terminal dimensions and change events
     -keystrokes
     -number of scroll downs necessary to render array
     -initial cursor position
    outputs:
     -2D array to be rendered

    Repl is mostly view-indepented state of Repl - but self.width and self.height
    are important for figuring out how to wrap lines for example.
    Usually self.width and self.height should be set by receiving a window resize event,
    not manually set to anything - as long as the first event received is a window
    resize event, this works fine.
    """

    def __init__(self):
        logging.debug("starting init")
        interp = code.InteractiveInterpreter()

        config = Struct()
        loadini(config, default_config_path())
        config.autocomplete_mode = SIMPLE # only one implemented currently

        #TODO determine if this is supposed to use this, or if it should be
        # frontend specific.
        if config.cli_suggestion_width <= 0 or config.cli_suggestion_width > 1:
            config.cli_suggestion_width = 1

        self.status_bar = StatusBar(_('welcome to bpython'))
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

        self.paste_mode = False

        self.width = None  # will both be set by a window resize event
        self.height = None
        self.start_background_tasks()

    ## Required by bpython.repl.Repl
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
        self.display_buffer[lineno] = bpythonparse(format(tokens, self.formatter))
    def reevaluate(self):
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
            self.on_enter()
        self.cursor_offset_in_line = 0
        self._current_line = ''
    def getstdout(self):
        lines = self.lines_for_display + [self.current_formatted_line]
        s = '\n'.join([x.s if isinstance(x, FmtStr) else x
                       for x in lines]) if lines else ''
        return s


    ## Our own functions

    @property
    def current_formatted_line(self):
        fs = bpythonparse(format(self.tokenize(self._current_line), self.formatter))
        logging.debug('calculating current formatted line: %r', repr(fs))
        return fs

    def unhighlight_paren(self):
        """modify line in self.display_buffer to unhighlight a paren if possible"""
        if self.highlighted_paren is not None:
            lineno, saved_tokens = self.highlighted_paren
            if lineno == len(self.display_buffer):
                # then this is the current line, so don't worry about it
                return
            self.highlighted_paren = None
            logging.debug('trying to unhighlight a paren on line %r', lineno)
            logging.debug('with these tokens: %r', saved_tokens)
            new = bpythonparse(format(saved_tokens, self.formatter))
            self.display_buffer[lineno][:len(new)] = new

    @property
    def lines_for_display(self):
        return self.display_lines + self.display_buffer_lines

    @property
    def display_buffer_lines(self):
        lines = []
        for display_line in self.display_buffer:
            display_line = fmtstr(self.ps2 if lines else self.ps1, PROMPTCOLOR) + display_line
            for line in paint.display_linize(display_line, self.width):
                lines.append(line)
        return lines

    def __enter__(self):
        self.orig_stdout = sys.stdout
        self.orig_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()
        return self

    def __exit__(self, *args):
        sys.stderr.seek(0)
        s = sys.stderr.read()
        self.orig_stderr.write(s)
        sys.stdout = self.orig_stdout
        sys.stderr = self.orig_stderr

    @property
    def display_line_with_prompt(self):
        return fmtstr(self.ps1 if self.done else self.ps2, PROMPTCOLOR) + self.current_formatted_line

    def start_background_tasks(self):
        t = threading.Thread(target=self.importcompletion_thread)
        t.daemon = True
        t.start()

    def importcompletion_thread(self):
        """quick tasks we want to do bits of during downtime"""
        while importcompletion.find_coroutine(): # returns None when fully initialized
            pass

    def on_enter(self):
        self.cursor_offset_in_line = -1 # so the cursor isn't touching a paren
        self.unhighlight_paren()        # in unhighlight_paren

        self.rl_history.append(self._current_line)
        self.rl_history.last()
        self.history.append(self._current_line)
        output, err, self.done, indent = self.push(self._current_line)
        if output:
            self.display_lines.extend(sum([paint.display_linize(line, self.width) for line in output.split('\n')], []))
        if err:
            self.display_lines.extend([fmtstr(line, 'red') for line in sum([paint.display_linize(line, self.width) for line in err.split('\n')], [])])
        self._current_line = ' '*indent
        self.cursor_offset_in_line = len(self._current_line)

    def only_whitespace_left_of_cursor(self):
        """returns true if all characters on current line before cursor are whitespace"""
        return self._current_line[:self.cursor_offset_in_line].strip()

    def on_tab(self, back=False):
        """Do something on tab key
        taken from bpython.cli

        Does one of the following:
        1) add space to move up to the next %4==0 column
        2) complete the current word with characters common to all completions and
        3) select the first or last match
        4) select the next or previous match if already have a match
        """
        logging.debug('self.matches: %r', self.matches)
        if not self.only_whitespace_left_of_cursor():
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

    def add_normal_character(self, char):
        assert len(char) == 1, repr(char)
        self._current_line = (self._current_line[:self.cursor_offset_in_line] +
                             char +
                             self._current_line[self.cursor_offset_in_line:])
        self.cursor_offset_in_line += 1
        self.cursor_offset_in_line, self._current_line = substitute_abbreviations(self.cursor_offset_in_line, self._current_line)
        #TODO deal with characters that take up more than one space? do we care?

    def process_event(self, e):
        """Returns True if shutting down, otherwise mutates state of Repl object"""

        #logging.debug("processing event %r", e)
        if isinstance(e, events.WindowChangeEvent):
            logging.debug('window change to %d %d', e.width, e.height)
            self.width, self.height = e.width, e.height
            return
        if self.status_bar.has_focus:
            return self.status_bar.process_event(e)

        if e in self.rl_char_sequences:
            self.cursor_offset_in_line, self._current_line = self.rl_char_sequences[e](self.cursor_offset_in_line, self._current_line)
            self.set_completion()

        # readline history commands
        elif e in ("[A", "KEY_UP") + key_dispatch[self.config.up_one_line_key]:
            self.rl_history.enter(self._current_line)
            self._current_line = self.rl_history.back(False)
            self.cursor_offset_in_line = len(self._current_line)
            self.set_completion()
        elif e in ("[B", "KEY_DOWN") + key_dispatch[self.config.down_one_line_key]:
            self.rl_history.enter(self._current_line)
            self._current_line = self.rl_history.forward(False)
            self.cursor_offset_in_line = len(self._current_line)
            self.set_completion()
        elif e in key_dispatch[self.config.search_key]:
            raise NotImplementedError()
        #TODO add rest of history commands

        # Need to figure out what these are, but I think they belong in manual_realine
        # under slightly different names
        elif e in key_dispatch[self.config.cut_to_buffer_key]:
            raise NotImplementedError()
        elif e in key_dispatch[self.config.yank_from_buffer_key]:
            raise NotImplementedError()

        elif e in key_dispatch[self.config.clear_screen_key]:
            raise NotImplementedError()
        elif e in key_dispatch[self.config.last_output_key]:
            raise NotImplementedError()
        elif e in key_dispatch[self.config.show_source_key]:
            raise NotImplementedError()
        elif e in key_dispatch[self.config.suspend_key]:
            raise SystemExit()
        elif e == "":
            raise KeyboardInterrupt()
        elif e in ("",) + key_dispatch[self.config.exit_key]:
            raise SystemExit()
        elif e in ("\n", "\r", "PAD_ENTER"):
            self.on_enter()
            self.set_completion()
        elif e in ["", "", "\x00", "\x11"]:
            pass #dunno what these are, but they screw things up #TODO find out
            #TODO use a whitelist instead of a blacklist!
        elif e == '\t': # tab
            self.on_tab()
        elif e in ('[Z', "KEY_BTAB"): # shift-tab
            self.on_tab(back=True)
        elif e in ('',) + key_dispatch[self.config.undo_key]:
            self.undo()
            self.set_completion()
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
        #TODO add PAD keys hack as in bpython.cli
        else:
            self.add_normal_character(e)
            self.set_completion()

    def clean_up_current_line_for_exit(self):
        """Called when trying to exit to prep for final paint"""
        logging.debug('unhighlighting paren for exit')
        self.cursor_offset_in_line = -1
        self.unhighlight_paren()

    def set_completion(self, tab=False):
        """Update autocomplete info; self.matches and self.argspec"""
        # this method stolen from bpython.cli
        if self.paste_mode:
            return

        if self.list_win_visible and not self.config.auto_display_list:
            self.list_win_visible = False
            self.matches_iter.update(self.current_word)
            return

        if self.config.auto_display_list or tab:
            self.list_win_visible = BpythonRepl.complete(self, tab)

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

    def push(self, line):
        """Push a line of code onto the buffer, run the buffer

        If the interpreter successfully runs the code, clear the buffer
        Return ("for stdout", "for_stderr", finished?)
        """
        self.buffer.append(line)
        indent = len(re.match(r'[ ]*', line).group())

        if line.endswith(':'):
            indent = max(0, indent + self.config.tab_length)
        elif line and line.count(' ') == len(self._current_line):
            indent = max(0, indent - self.config.tab_length)
        elif line and ':' not in line and line.strip().startswith(('return', 'pass', 'raise', 'yield')):
            indent = max(0, indent - self.config.tab_length)
        out_spot = sys.stdout.tell()
        err_spot = sys.stderr.tell()
        #logging.debug('running %r in interpreter', self.buffer)
        unfinished = self.interp.runsource('\n'.join(self.buffer))
        self.display_buffer.append(bpythonparse(format(self.tokenize(line), self.formatter))) #current line not added to display buffer if quitting
        sys.stdout.seek(out_spot)
        sys.stderr.seek(err_spot)
        out = sys.stdout.read()
        err = sys.stderr.read()

        # easier debugging: save only errors that aren't from this interpreter
        oldstderr = sys.stderr
        sys.stderr = StringIO()
        oldstderr.seek(0)
        sys.stderr.write(oldstderr.read(err_spot))

        if unfinished and not err:
            logging.debug('unfinished - line added to buffer')
            return (None, None, False, indent)
        else:
            logging.debug('finished - buffer cleared')
            self.display_lines.extend(self.display_buffer_lines)
            self.display_buffer = []
            self.buffer = []
            if err:
                indent = 0
            return (out[:-1], err[:-1], True, indent)

    def paint(self, about_to_exit=False):
        """Returns an array of min_height or more rows and width columns, plus cursor position

        Paints the entire screen - ideally the terminal display layer will take a diff and only
        write to the screen in portions that have changed, but the idea is that we don't need
        to worry about that here, instead every frame is completely redrawn because
        less state is cool!
        """

        #TODO allow custom background colors? I'm not sure about this
        # use fmtstr.bpythonparse.color_for_letter(config.background) -> "black"

        if about_to_exit:
            self.clean_up_current_line_for_exit()

        width, min_height = self.width, self.height
        show_status_bar = bool(self.status_bar.current_line)
        if show_status_bar:
            min_height -= 1
        arr = FSArray(0, width)
        current_line_start_row = len(self.lines_for_display) - max(0, self.scroll_offset)

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
            logging.debug('infobox display code running')
            visible_space_above = history.height
            visible_space_below = min_height - cursor_row
            info_max_rows = max(visible_space_above, visible_space_below)

            infobox = paint.paint_infobox(info_max_rows, int(width * self.config.cli_suggestion_width), self.matches, self.argspec, self.current_word, self.docstring, self.config)

            if visible_space_above >= infobox.height and not INFOBOX_ONLY_BELOW:
                arr[current_line_start_row - infobox.height:current_line_start_row, 0:infobox.width] = infobox
            else:
                arr[cursor_row + 1:cursor_row + 1 + infobox.height, 0:infobox.width] = infobox
                logging.debug('slamming infobox of shape %r into arr', infobox.shape)

        if show_status_bar and not about_to_exit:
            arr[max(arr.height, min_height), :] = paint.paint_statusbar(1, width, self.status_bar.current_line)
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
        my_print('X..'+('.'*(self.width+2))+'..X')
        for line in arr:
            my_print('X...'+(line if line else ' '*len(line))+'...X')
        logging.debug('line:')
        logging.debug(repr(line))
        my_print('X..'+('.'*(self.width+2))+'..X')
        my_print('X'*(self.width+8))
        return max(len(arr) - self.height, 0)

    def dumb_input(self):
        for c in raw_input('>'):
            if c in '/':
                c = '\n'
            elif c in '\\':
                c = ''
            elif c in '|':
                def r(): raise Exception('real errors should look like this')
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

def test():
    with Repl() as r:
        r.width = 50
        r.height = 10
        while True:
            scrolled = r.dumb_print_output()
            r.scroll_offset += scrolled
            r.dumb_input()

if __name__ == '__main__':
    test()
