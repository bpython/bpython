import code
import contextlib
import errno
import functools
import greenlet
import logging
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata

from pygments import format
from pygments.lexers import PythonLexer
from pygments.formatters import TerminalFormatter
from interpreter import Interp

import blessings

import curtsies
from curtsies import FSArray, fmtstr, FmtStr, Termmode
from curtsies.bpythonparse import parse as bpythonparse
from curtsies.bpythonparse import func_for_letter, color_for_letter
from curtsies import fmtfuncs
from curtsies import events

import bpython
from bpython.repl import Repl as BpythonRepl
from bpython.config import Struct, loadini, default_config_path
from bpython.formatter import BPythonFormatter
from bpython import autocomplete, importcompletion
from bpython import translations; translations.init()
from bpython.translations import _
from bpython._py3compat import py3

from bpython.curtsiesfrontend import replpainter as paint
from bpython.curtsiesfrontend import sitefix; sitefix.monkeypatch_quit()
from bpython.curtsiesfrontend.coderunner import CodeRunner, FakeOutput
from bpython.curtsiesfrontend.filewatch import ModuleChangedEventHandler
from bpython.curtsiesfrontend.interaction import StatusBar
from bpython.curtsiesfrontend.manual_readline import edit_keys

#TODO other autocomplete modes (also fix in other bpython implementations)


from curtsies.configfile_keynames import keymap as key_dispatch

logger = logging.getLogger(__name__)

HELP_MESSAGE = """
Thanks for using bpython!

See http://bpython-interpreter.org/ for info, http://docs.bpython-interpreter.org/ for docs, and https://github.com/bpython/bpython for source.
Please report issues at https://github.com/bpython/bpython/issues

Try using undo ({config.undo_key})!
Edit the current line ({config.edit_current_block_key}) or the entire session ({config.external_editor_key}) in an external editor! (currently {config.editor})
Save sessions ({config.save_key}) or post them to pastebins ({config.pastebin_key})! Current pastebin helper: {config.pastebin_helper}
Re-execute the current session and reload all modules ({config.reimport_key}) to test out changes to a module!
Toggle auto-reload mode ({config.toggle_file_watch_key}) to re-execute the current session when a module you've imported is modified!

Use bpython-curtsies -i your_script.py to run a file in interactive mode (interpreter in namespace of script).
Use bpython-curtsies -t your_script.py to paste in the contents of a file, as though you typed them.

Use a config file at {config_file_location} to customize keys and behavior of bpython.
You can customize which pastebin helper to use and which external editor to use.
See {example_config_url} for an example config file.
"""

class FakeStdin(object):
    """Stdin object user code references so sys.stdin.read() asked user for interactive input"""
    def __init__(self, coderunner, repl, configured_edit_keys=None):
        self.coderunner = coderunner
        self.repl = repl
        self.has_focus = False # whether FakeStdin receives keypress events
        self.current_line = ''
        self.cursor_offset = 0
        self.old_num_lines = 0
        self.readline_results = []
        if configured_edit_keys:
            self.rl_char_sequences = configured_edit_keys
        else:
            self.rl_char_sequences = edit_keys

    def process_event(self, e):
        assert self.has_focus

        logger.debug('fake input processing event %r', e)
        if isinstance(e, events.PasteEvent):
            for ee in e.events:
                if ee not in self.rl_char_sequences:
                    self.add_input_character(ee)
        elif e in self.rl_char_sequences:
            self.cursor_offset, self.current_line = self.rl_char_sequences[e](self.cursor_offset, self.current_line)
        elif isinstance(e, events.SigIntEvent):
            self.coderunner.sigint_happened_in_main_greenlet = True
            self.has_focus = False
            self.current_line = ''
            self.cursor_offset = 0
            self.repl.run_code_and_maybe_finish()
        elif e in ("<Esc+.>",):
            self.get_last_word()

        elif e in ["<ESC>"]:
            pass
        elif e in ['<Ctrl-d>']:
            if self.current_line == '':
                self.repl.send_to_stdin('\n')
                self.has_focus = False
                self.current_line = ''
                self.cursor_offset = 0
                self.repl.run_code_and_maybe_finish(for_code='')
            else:
                pass
        elif e in ["\n", "\r", "<Ctrl-j>", "<Ctrl-m>"]:
            line = self.current_line
            self.repl.send_to_stdin(line + '\n')
            self.has_focus = False
            self.current_line = ''
            self.cursor_offset = 0
            self.repl.run_code_and_maybe_finish(for_code=line+'\n')
        else: # add normal character
            self.add_input_character(e)

        if self.current_line.endswith(("\n", "\r")):
            pass
        else:
            self.repl.send_to_stdin(self.current_line)

    def add_input_character(self, e):
        if e == '<SPACE>': e = ' '
        if e.startswith('<') and e.endswith('>'): return
        assert len(e) == 1, 'added multiple characters: %r' % e
        logger.debug('adding normal char %r to current line', e)

        c = e if py3 else e.encode('utf8')
        self.current_line = (self.current_line[:self.cursor_offset] +
                             c +
                             self.current_line[self.cursor_offset:])
        self.cursor_offset += 1

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
    def __init__(self,
                 locals_=None,
                 config=None,
                 request_refresh=lambda when='now': None,
                 request_reload=lambda desc: None, get_term_hw=lambda:(50, 10),
                 get_cursor_vertical_diff=lambda: 0,
                 banner=None,
                 interp=None,
                 interactive=True,
                 orig_tcattrs=None):
        """
        locals_ is a mapping of locals to pass into the interpreter
        config is a bpython config.Struct with config attributes
        request_refresh is a function that will be called when the Repl
            wants to refresh the display, but wants control returned to it afterwards
            Takes as a kwarg when= which is when to fire
        get_term_hw is a function that returns the current width and height
            of the terminal
        get_cursor_vertical_diff is a function that returns how the cursor moved
            due to a window size change
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
            interp = Interp(locals=locals_)
            interp.writetb = self.send_to_stderr
        if banner is None:
            if config.help_key:
                banner = _('Welcome to bpython!') + ' ' + (_('Press <%s> for help.') % config.help_key)
            else:
                banner = None
        config.autocomplete_mode = autocomplete.SIMPLE # only one implemented currently
        if config.cli_suggestion_width <= 0 or config.cli_suggestion_width > 1:
            config.cli_suggestion_width = 1

        self.reevaluating = False
        self.fake_refresh_requested = False
        def smarter_request_refresh(when='now'):
            if self.reevaluating or self.paste_mode:
                self.fake_refresh_requested = True
            else:
                request_refresh(when=when)
        self.request_refresh = smarter_request_refresh
        def smarter_request_reload(desc):
            if self.watching_files:
                request_reload(desc)
            else:
                pass
        self.request_reload = smarter_request_reload
        self.get_term_hw = get_term_hw
        self.get_cursor_vertical_diff = get_cursor_vertical_diff

        self.status_bar = StatusBar(
            (_(" <%s> Rewind  <%s> Save  <%s> Pastebin <%s> Editor")
             % (config.undo_key, config.save_key, config.pastebin_key, config.external_editor_key)
             if config.curtsies_fill_terminal else ''),
            refresh_request=self.request_refresh
            )
        self.edit_keys = edit_keys.mapping_with_config(config, key_dispatch)
        logger.debug("starting parent init")
        super(Repl, self).__init__(interp, config)
        #TODO bring together all interactive stuff - including current directory in path?
        if interactive:
            self.startup()
        self.formatter = BPythonFormatter(config.color_scheme)
        self.interact = self.status_bar # overwriting what bpython.Repl put there
                                        # interact is called to interact with the status bar,
                                        # so we're just using the same object
        self._current_line = '' # line currently being edited, without ps1 (usually '>>> ')
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
        self._cursor_offset = 0 # from the left, 0 means first char
        self.orig_tcattrs = orig_tcattrs # useful for shelling out with normal terminal

        self.coderunner = CodeRunner(self.interp, self.request_refresh)
        self.stdout = FakeOutput(self.coderunner, self.send_to_stdout)
        self.stderr = FakeOutput(self.coderunner, self.send_to_stderr)
        self.stdin = FakeStdin(self.coderunner, self, self.edit_keys)

        self.request_paint_to_clear_screen = False # next paint should clear screen
        self.inconsistent_history = False # offscreen command yields different result from history
        self.last_events = [None] * 50 # some commands act differently based on the prev event
                                       # this list doesn't include instances of event.Event,
                                       # only keypress-type events (no refresh screen events etc.)
        self.presentation_mode = False # displays prev events in a column on the right hand side
        self.paste_mode = False        # currently processing a paste event
        self.current_match = None      # currently tab-selected autocompletion suggestion
        self.list_win_visible = False  # whether the infobox (suggestions, docstring) is visible
        self.watching_files = False    # auto reloading turned on
        self.special_mode = None       # 'reverse_incremental_search' and 'incremental_search'
        self.incremental_search_target = ''

        self.original_modules = sys.modules.keys()

        self.width = None
        self.height = None

        self.status_bar.message(banner)

        self.watcher = ModuleChangedEventHandler([], smarter_request_reload)

    def __enter__(self):
        self.orig_stdout = sys.stdout
        self.orig_stderr = sys.stderr
        self.orig_stdin = sys.stdin
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        sys.stdin = self.stdin
        self.orig_sigwinch_handler = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, self.sigwinch_handler)

        self.orig_import = __builtins__['__import__']
        if self.watcher:
            old_module_locations = {} # for readding modules if they fail to load
            @functools.wraps(self.orig_import)
            def new_import(name, globals={}, locals={}, fromlist=[], level=-1):
                try:
                    m = self.orig_import(name, globals=globals, locals=locals, fromlist=fromlist)
                except:
                    if name in old_module_locations:
                        loc = old_module_locations[name]
                        if self.watching_files:
                            self.watcher.add_module(old_module_locations[name])
                        else:
                            self.watcher.add_module_later(old_module_locations[name])
                    raise
                else:
                    if hasattr(m, "__file__"):
                        old_module_locations[name] = m.__file__
                        if self.watching_files:
                            self.watcher.add_module(m.__file__)
                        else:
                            self.watcher.add_module_later(m.__file__)
                return m
            __builtins__['__import__'] = new_import

        return self

    def __exit__(self, *args):
        sys.stdin = self.orig_stdin
        sys.stdout = self.orig_stdout
        sys.stderr = self.orig_stderr
        signal.signal(signal.SIGWINCH, self.orig_sigwinch_handler)
        __builtins__['__import__'] = self.orig_import

    def sigwinch_handler(self, signum, frame):
        old_rows, old_columns = self.height, self.width
        self.height, self.width = self.get_term_hw()
        cursor_dy = self.get_cursor_vertical_diff()
        self.scroll_offset -= cursor_dy
        logger.info('sigwinch! Changed from %r to %r', (old_rows, old_columns), (self.height, self.width))
        logger.info('decreasing scroll offset by %d to %d', cursor_dy, self.scroll_offset)

    def startup(self):
        """
        Execute PYTHONSTARTUP file if it exits. Call this after front
        end-specific initialisation.
        """
        filename = os.environ.get('PYTHONSTARTUP')
        if filename:
            if os.path.isfile(filename):
                with open(filename, 'r') as f:
                    if py3:
                        #TODO runsource has a new signature in PY3
                        self.interp.runsource(f.read(), filename, 'exec')
                    else:
                        self.interp.runsource(f.read(), filename, 'exec')
            else:
                raise IOError("Python startup file (PYTHONSTARTUP) not found at %s" % filename)

    def clean_up_current_line_for_exit(self):
        """Called when trying to exit to prep for final paint"""
        logger.debug('unhighlighting paren for exit')
        self.cursor_offset = -1
        self.unhighlight_paren()

    ## Event handling
    def process_event(self, e):
        """Returns True if shutting down, otherwise returns None.
        Mostly mutates state of Repl object"""

        logger.debug("processing event %r", e)
        if isinstance(e, events.Event):
            return self.proccess_control_event(e)
        else:
            self.last_events.append(e)
            self.last_events.pop(0)
            return self.process_key_event(e)

    def proccess_control_event(self, e):

        if isinstance(e, events.RefreshRequestEvent):
            if e.when != 'now':
                pass # This is a scheduled refresh - it's really just a refresh (so nop)
            elif self.status_bar.has_focus:
                self.status_bar.process_event(e)
            else:
                assert self.coderunner.code_is_waiting
                self.run_code_and_maybe_finish()

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
                        self.process_simple_keypress(ee)

        elif self.stdin.has_focus:
            return self.stdin.process_event(e)

        elif isinstance(e, events.SigIntEvent):
            logger.debug('received sigint event')
            self.keyboard_interrupt()
            return

        elif isinstance(e, events.ReloadEvent):
            if self.watching_files:
                self.clear_modules_and_reevaluate()
                self.status_bar.message('Reloaded at ' + time.strftime('%H:%M:%S') + ' because ' + ' & '.join(e.files_modified) + ' modified')

        else:
            raise ValueError("don't know how to handle this event type: %r" % e)

    def process_key_event(self, e):
        # To find the curtsies name for a keypress, try python -m curtsies.events
        if self.status_bar.has_focus: return self.status_bar.process_event(e)
        if self.stdin.has_focus:      return self.stdin.process_event(e)

        if (e in ("<RIGHT>", '<Ctrl-f>') and self.config.curtsies_right_arrow_completion
                and self.cursor_offset == len(self.current_line)):
            self.current_line += self.current_suggestion
            self.cursor_offset = len(self.current_line)

        elif e in ("<UP>",) + key_dispatch[self.config.up_one_line_key]:
            self.up_one_line()
        elif e in ("<DOWN>",) + key_dispatch[self.config.down_one_line_key]:
            self.down_one_line()
        elif e in ("<Ctrl-d>",):
            self.on_control_d()
        elif e in ("<Esc+.>",):
            self.get_last_word()
        elif e in ("<Esc+r>",):
            self.incremental_search(reverse=True)
        elif e in ("<Esc+s>",):
            self.incremental_search()
        elif e in ("<BACKSPACE>", '<Ctrl-h>') and self.special_mode:
            self.add_to_incremental_search(self, backspace=True)
        elif e in self.edit_keys.cut_buffer_edits:
            self.readline_kill(e)
        elif e in self.edit_keys.simple_edits:
            self.cursor_offset, self.current_line = self.edit_keys.call(e,
                    cursor_offset=self.cursor_offset,
                    line=self.current_line,
                    cut_buffer=self.cut_buffer)
        elif e in key_dispatch[self.config.cut_to_buffer_key]:
            self.cut_to_buffer()
        elif e in key_dispatch[self.config.reimport_key]:
            self.clear_modules_and_reevaluate()
        elif e in key_dispatch[self.config.toggle_file_watch_key]:
            return self.toggle_file_watch()
        elif e in key_dispatch[self.config.clear_screen_key]:
            self.request_paint_to_clear_screen = True
        elif e in key_dispatch[self.config.show_source_key]:
            self.show_source()
        elif e in key_dispatch[self.config.help_key]:
            self.pager(self.help_text())
        elif e in key_dispatch[self.config.suspend_key]:
            raise SystemExit()
        elif e in key_dispatch[self.config.exit_key]:
            raise SystemExit()
        elif e in ("\n", "\r", "<PADENTER>", "<Ctrl-j>", "<Ctrl-m>"):
            self.on_enter()
        elif e == '<TAB>': # tab
            self.on_tab()
        elif e in ("<Shift-TAB>",):
            self.on_tab(back=True)
        elif e in key_dispatch[self.config.undo_key]: #ctrl-r for undo
            self.undo()
        elif e in key_dispatch[self.config.save_key]: # ctrl-s for save
            greenlet.greenlet(self.write2file).switch()
        elif e in key_dispatch[self.config.pastebin_key]: # F8 for pastebin
            greenlet.greenlet(self.pastebin).switch()
        elif e in key_dispatch[self.config.external_editor_key]:
            self.send_session_to_external_editor()
        elif e in key_dispatch[self.config.edit_config_key]:
            greenlet.greenlet(self.edit_config).switch()
        #TODO add PAD keys hack as in bpython.cli
        elif e in key_dispatch[self.config.edit_current_block_key]:
            self.send_current_block_to_external_editor()
        elif e in ["<ESC>"]: #ESC
            self.special_mode = None
        elif e in ["<SPACE>"]:
            self.add_normal_character(' ')
        else:
            self.add_normal_character(e)

    def get_last_word(self):

        def last_word(line):
            if not line:
                return ''
            return line.split().pop()

        previous_word = last_word(self.rl_history.entry)
        word = last_word(self.rl_history.back())
        line=self.current_line
        self._set_current_line(line[:len(line)-len(previous_word)]+word, reset_rl_history=False)
        
        self._set_cursor_offset(self.cursor_offset-len(previous_word)+len(word), reset_rl_history=False)
 

    def incremental_search(self, reverse=False, include_current=False):
        if self.special_mode == None:
            self.rl_history.enter(self.current_line)
            self.incremental_search_target = ''
        else:
            if self.incremental_search_target:
                line = (self.rl_history.back(False, search=True,
                                            target=self.incremental_search_target,
                                            include_current=include_current)
                        if reverse else
                        self.rl_history.forward(False, search=True,
                                                target=self.incremental_search_target,
                                                include_current=include_current))
                self._set_current_line(line,
                                       reset_rl_history=False, clear_special_mode=False)
                self._set_cursor_offset(len(self.current_line),
                                        reset_rl_history=False, clear_special_mode=False)
        if reverse:
            self.special_mode = 'reverse_incremental_search'
        else:
            self.special_mode = 'incremental_search'

    def readline_kill(self, e):
        func = self.edit_keys[e]
        self.cursor_offset, self.current_line, cut = func(self.cursor_offset, self.current_line)
        if self.last_events[-2] == e: # consecutive kill commands are cumulative
            if func.kills == 'ahead': self.cut_buffer += cut
            elif func.kills == 'behind': self.cut_buffer = cut + self.cut_buffer
            else: raise ValueError("cut had value other than 'ahead' or 'behind'")
        else:
            self.cut_buffer = cut

    def on_enter(self, insert_into_history=True):
        self.cursor_offset = -1 # so the cursor isn't touching a paren
        self.unhighlight_paren()        # in unhighlight_paren
        self.highlighted_paren = None

        self.rl_history.append(self.current_line)
        self.rl_history.last()
        self.history.append(self.current_line)
        self.push(self.current_line, insert_into_history=insert_into_history)

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
            return self.current_line[:self.cursor_offset].strip()

        logger.debug('self.matches_iter.matches: %r', self.matches_iter.matches)
        if not only_whitespace_left_of_cursor():
            front_white = (len(self.current_line[:self.cursor_offset]) -
                len(self.current_line[:self.cursor_offset].lstrip()))
            to_add = 4 - (front_white % self.config.tab_length)
            for _ in range(to_add):
                self.add_normal_character(' ')
            return

        # run complete() if we aren't already iterating through matches
        if not self.matches_iter:
            self.list_win_visible = self.complete(tab=True)

        # 3. check to see if we can expand the current word
        if self.matches_iter.is_cseq():
            self._cursor_offset, self._current_line = self.matches_iter.substitute_cseq()
            # using _current_line so we don't trigger a completion reset
            if not self.matches_iter:
                self.list_win_visible = self.complete()

        elif self.matches_iter.matches:
            self.current_match = back and self.matches_iter.previous() \
                                  or self.matches_iter.next()
            self._cursor_offset, self._current_line = self.matches_iter.cur_line()
            # using _current_line so we don't trigger a completion reset

    def on_control_d(self):
        if self.current_line == '':
            raise SystemExit()
        else:
            self.current_line = self.current_line[:self.cursor_offset] + self.current_line[self.cursor_offset+1:]

    def cut_to_buffer(self):
        self.cut_buffer = self.current_line[self.cursor_offset:]
        self.current_line = self.current_line[:self.cursor_offset]

    def yank_from_buffer(self):
        pass

    def up_one_line(self):
        self.rl_history.enter(self.current_line)
        self._set_current_line(self.rl_history.back(False, search=self.config.curtsies_right_arrow_completion),
                               reset_rl_history=False)
        self._set_cursor_offset(len(self.current_line), reset_rl_history=False)

    def down_one_line(self):
        self.rl_history.enter(self.current_line)
        self._set_current_line(self.rl_history.forward(False, search=self.config.curtsies_right_arrow_completion),
                               reset_rl_history=False)
        self._set_cursor_offset(len(self.current_line), reset_rl_history=False)

    def process_simple_keypress(self, e):
        if e in (u"<Ctrl-j>", u"<Ctrl-m>", u"<PADENTER>", u"\n", u"\r"): # '\n' necessary for pastes
            self.on_enter()
            while self.fake_refresh_requested:
                self.fake_refresh_requested = False
                self.process_event(events.RefreshRequestEvent())
        elif isinstance(e, events.Event):
            pass # ignore events
        elif e == '<SPACE>':
            self.add_normal_character(' ')
        else:
            self.add_normal_character(e)

    def send_current_block_to_external_editor(self, filename=None):
        text = self.send_to_external_editor(self.get_current_block().encode('utf8'))
        lines = [line for line in text.split('\n')]
        while lines and not lines[-1].split():
            lines.pop()
        events = '\n'.join(lines + ([''] if len(lines) == 1 else ['', '']))
        self.clear_current_block()
        with self.in_paste_mode():
            for e in events:
                self.process_simple_keypress(e)
        self.cursor_offset = len(self.current_line)

    def send_session_to_external_editor(self, filename=None):
        for_editor = '### current bpython session - file will be reevaluated, ### lines will not be run\n'.encode('utf8')
        for_editor += ('\n'.join(line[len(self.ps1):] if line.startswith(self.ps1) else
                                 (line[len(self.ps2):] if line.startswith(self.ps2) else
                                 '### '+line)
                                 for line in self.getstdout().split('\n')).encode('utf8'))
        text = self.send_to_external_editor(for_editor)
        lines = text.split('\n')
        self.history = [line for line in lines if line[:4] != '### ']
        self.reevaluate(insert_into_history=True)
        self.current_line = lines[-1][4:]
        self.cursor_offset = len(self.current_line)

    def clear_modules_and_reevaluate(self):
        if self.watcher: self.watcher.reset()
        cursor, line = self.cursor_offset, self.current_line
        for modname in sys.modules.keys():
            if modname not in self.original_modules:
                del sys.modules[modname]
        self.reevaluate(insert_into_history=True)
        self.cursor_offset, self.current_line = cursor, line
        self.status_bar.message('Reloaded at ' + time.strftime('%H:%M:%S') + ' by user')

    def toggle_file_watch(self):
        if self.watcher:
            msg = "Auto-reloading active, watching for file changes..."
            if self.watching_files:
                self.watcher.deactivate()
                self.watching_files = False
                self.status_bar.pop_permanent_message(msg)
            else:
                self.watching_files = True
                self.status_bar.push_permanent_message(msg)
                self.watcher.activate()
        else:
            self.status_bar.message('Autoreloading not available because watchdog not installed')

    ## Handler Helpers
    def add_normal_character(self, char):
        if len(char) > 1 or is_nop(char):
            return
        if self.special_mode:
            self.add_to_incremental_search(char)
        else:
            self.current_line = (self.current_line[:self.cursor_offset] +
                                 char +
                                 self.current_line[self.cursor_offset:])
            self.cursor_offset += 1
        if self.config.cli_trim_prompts and self.current_line.startswith(self.ps1):
            self.current_line = self.current_line[4:]
            self.cursor_offset = max(0, self.cursor_offset - 4)

    def add_to_incremental_search(self, char=None, backspace=False):
        """Modify the current search term while in incremental search.

        The only operations allowed in incremental search mode are
        adding characters and backspacing."""
        if char is None and not backspace:
            raise ValueError("must provide a char or set backspace to True")
        if backspace:
            self.incremental_search_target = self.incremental_search_target[:-1]
        else:
            self.incremental_search_target += char
        if self.special_mode == 'reverse_incremental_search':
            self.incremental_search(reverse=True, include_current=True)
        elif self.special_mode == 'incremental_search':
            self.incremental_search(include_current=True)
        else:
            raise ValueError('add_to_incremental_search should only be called in a special mode')

    def update_completion(self, tab=False):
        """Update visible docstring and matches, and possibly hide/show completion box"""
        #Update autocomplete info; self.matches_iter and self.argspec
        #Should be called whenever the completion box might need to appear / dissapear
        #when current line or cursor offset changes, unless via selecting a match
        self.current_match = None
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
        c, code_will_parse = self.buffer_finished_will_parse()
        self.saved_predicted_parse_error = not code_will_parse
        if c:
            logger.debug('finished - buffer cleared')
            self.display_lines.extend(self.display_buffer_lines)
            self.display_buffer = []
            self.buffer = []
            self.cursor_offset = 0

        self.coderunner.load_code(code_to_run)
        self.run_code_and_maybe_finish()

    def buffer_finished_will_parse(self):
        """Returns a tuple of whether the buffer could be complete and whether it will parse

        True, True means code block is finished and no predicted parse error
        True, False means code block is finished because a parse error is predicted
        False, True means code block is unfinished
        False, False isn't possible - an predicted error makes code block done"""
        try:
            finished = bool(code.compile_command('\n'.join(self.buffer)))
            code_will_parse = True
        except (ValueError, SyntaxError, OverflowError):
            finished = True
            code_will_parse = False
        return finished, code_will_parse

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

            self.current_line = ' '*indent
            self.cursor_offset = len(self.current_line)

    def keyboard_interrupt(self):
        #TODO factor out the common cleanup from running a line
        self.cursor_offset = -1
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
        self.cursor_offset = 0
        self.saved_indent = 0
        self.current_line = ''
        self.cursor_offset = len(self.current_line)

    def get_current_block(self):
        return '\n'.join(self.buffer + [self.current_line])

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
        lines = error.split('\n')
        if lines[-1]:
            self.current_stdouterr_line += lines[-1]
        self.display_lines.extend(sum([paint.display_linize(line, self.width, blank_line=True) for line in lines[:-1]], []))

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
            fs = bpythonparse(format(self.tokenize(self.current_line), self.formatter))
            if self.special_mode:
                if self.incremental_search_target in self.current_line:
                    fs = fmtfuncs.on_magenta(self.incremental_search_target).join(fs.split(self.incremental_search_target))
            elif self.rl_history.saved_line and self.rl_history.saved_line in self.current_line:
                if self.config.curtsies_right_arrow_completion:
                    fs = fmtfuncs.on_magenta(self.rl_history.saved_line).join(fs.split(self.rl_history.saved_line))
            logger.debug('Display line %r -> %r', self.current_line, fs)
        else:
            fs = fmtstr(self.current_line)
        if hasattr(self, 'old_fs') and str(fs) != str(self.old_fs):
            pass
        self.old_fs = fs
        return fs

    @property
    def lines_for_display(self):
        """All display lines (wrapped, colored, with prompts)"""
        return self.display_lines + self.display_buffer_lines

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
        if self.special_mode == 'reverse_incremental_search':
            return func_for_letter(self.config.color_scheme['prompt'])(
                '(reverse-i-search)`%s\': ' % (self.incremental_search_target,)) + self.current_line_formatted
        elif self.special_mode == 'incremental_search':
            return func_for_letter(self.config.color_scheme['prompt'])(
                '(i-search)`%s\': ' % (self.incremental_search_target,)) + self.current_line_formatted
        return (func_for_letter(self.config.color_scheme['prompt'])(self.ps1)
                if self.done else
                func_for_letter(self.config.color_scheme['prompt_more'])(self.ps2)) + self.current_line_formatted

    @property
    def current_cursor_line_without_suggestion(self):
        """Current line, either output/input or Python prompt + code"""
        value = (self.current_output_line +
                ('' if self.coderunner.running else self.display_line_with_prompt))
        logger.debug('current cursor line: %r', value)
        return value

    @property
    def current_cursor_line(self):
        if self.config.curtsies_right_arrow_completion:
            return (self.current_cursor_line_without_suggestion +
                func_for_letter(self.config.color_scheme['right_arrow_suggestion'])(self.current_suggestion))
        else:
            return self.current_cursor_line_without_suggestion

    @property
    def current_suggestion(self):
        matches = [e for e in self.rl_history.entries if e.startswith(self.current_line) and self.current_line]
        return matches[-1][len(self.current_line):] if matches else ''

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
        show_status_bar = bool(self.status_bar.should_show_message) or (self.config.curtsies_fill_terminal or self.status_bar.has_focus)
        if show_status_bar:
            min_height -= 1

        current_line_start_row = len(self.lines_for_display) - max(0, self.scroll_offset)
        #current_line_start_row = len(self.lines_for_display) - self.scroll_offset
        if self.request_paint_to_clear_screen: # or show_status_bar and about_to_exit ?
            self.request_paint_to_clear_screen = False
            if self.config.curtsies_fill_terminal: #TODO clean up this logic - really necessary check?
                arr = FSArray(self.height - 1 + current_line_start_row, width)
            else:
                arr = FSArray(self.height + current_line_start_row, width)
        else:
            arr = FSArray(0, width)
        #TODO test case of current line filling up the whole screen (there aren't enough rows to show it)
        if self.inconsistent_history == True:
            msg = "#<---History inconsistent with output shown--->"
            arr[0, 0:min(len(msg), width)] = [msg[:width]]
            self.inconsistent_history = False
"""FIX THE THING This if may need to go after the second one, but the while applies to both"""
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
            cursor_row, cursor_column = divmod(len(self.current_stdouterr_line) + self.stdin.cursor_offset, width)
            assert cursor_column >= 0, cursor_column
        elif self.coderunner.running: #TODO does this ever happen?
            cursor_row, cursor_column = divmod(len(self.current_cursor_line_without_suggestion) + self.cursor_offset, width)
            assert cursor_column >= 0, (cursor_column, len(self.current_cursor_line), len(self.current_line), self.cursor_offset)
        else:
            cursor_row, cursor_column = divmod(len(self.current_cursor_line_without_suggestion) - len(self.current_line) + self.cursor_offset, width)
            assert cursor_column >= 0, (cursor_column, len(self.current_cursor_line), len(self.current_line), self.cursor_offset)
        cursor_row += current_line_start_row

        if self.list_win_visible:
            logger.debug('infobox display code running')
            visible_space_above = history.height
            visible_space_below = min_height - current_line_end_row - 1

            info_max_rows = max(visible_space_above, visible_space_below)
            infobox = paint.paint_infobox(info_max_rows,
                                          int(width * self.config.cli_suggestion_width),
                                          self.matches_iter.matches,
                                          self.argspec,
                                          self.current_match,
                                          self.docstring,
                                          self.config,
                                          self.matches_iter.completer.format if self.matches_iter.completer else None)

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
        s += " cursor_offset:" + repr(self.cursor_offset) + '\n'
        s += " num display lines:" + repr(len(self.display_lines)) + '\n'
        s += " lines scrolled down:" + repr(self.scroll_offset) + '\n'
        s += '>'
        return s

    def _get_current_line(self):
        return self._current_line
    def _set_current_line(self, line, update_completion=True, reset_rl_history=True, clear_special_mode=True):
        self._current_line = line
        if update_completion:
            self.update_completion()
        if reset_rl_history:
            self.rl_history.reset()
        if clear_special_mode:
            self.special_mode = None
    current_line = property(_get_current_line, _set_current_line, None,
                            "The current line")
    def _get_cursor_offset(self):
        return self._cursor_offset
    def _set_cursor_offset(self, offset, update_completion=True, reset_rl_history=True, clear_special_mode=True):
        if update_completion:
            self.update_completion()
        if reset_rl_history:
            self.rl_history.reset()
        if clear_special_mode:
            self.special_mode = None
        self._cursor_offset = offset
        self.update_completion()
    cursor_offset = property(_get_cursor_offset, _set_cursor_offset, None,
                            "The current cursor offset from the front of the line")
    def echo(self, msg, redraw=True):
        """
        Notification that redrawing the current line is necessary (we don't
        care, since we always redraw the whole screen)

        Supposed to parse and echo a formatted string with appropriate attributes.
        It's not supposed to update the screen if it's reevaluating the code (as it
        does with undo)."""
        logger.debug("echo called with %r" % msg)
    @property
    def cpos(self):
        "many WATs were had - it's the pos from the end of the line back"""
        return len(self.current_line) - self.cursor_offset
    def reprint_line(self, lineno, tokens):
        logger.debug("calling reprint line with %r %r", lineno, tokens)
        if self.config.syntax:
            self.display_buffer[lineno] = bpythonparse(format(tokens, self.formatter))

        return self.display_lines
    def reevaluate(self, insert_into_history=False):
        """bpython.Repl.undo calls this"""
        if self.watcher: self.watcher.reset()
        old_logical_lines = self.history
        old_display_lines = self.display_lines
        self.history = []
        self.display_lines = []

        if not self.weak_rewind:
            self.interp = self.interp.__class__()
            self.interp.writetb = self.send_to_stderr
            self.coderunner.interp = self.interp

        self.buffer = []
        self.display_buffer = []
        self.highlighted_paren = None

        self.reevaluating = True
        sys.stdin = ReevaluateFakeStdin(self.stdin, self)
        for line in old_logical_lines:
            self.current_line = line
            self.on_enter(insert_into_history=insert_into_history)
            while self.fake_refresh_requested:
                self.fake_refresh_requested = False
                self.process_event(events.RefreshRequestEvent())
        sys.stdin = self.stdin
        self.reevaluating = False
        num_lines_onscreen=len(self.lines_for_display)-max(0, self.scroll_offset)
        if old_display_lines[:len(self.display_lines)-num_lines_onscreen]!=self.display_lines:
            self.inconsistent_history = True
        self.cursor_offset = 0
        self.current_line = ''

    def getstdout(self):
        lines = self.lines_for_display + [self.current_line_formatted]
        s = '\n'.join([x.s if isinstance(x, FmtStr) else x for x in lines]
                     ) if lines else ''
        return s

    def focus_on_subprocess(self, args):
        prev_sigwinch_handler = signal.getsignal(signal.SIGWINCH)
        try:
            signal.signal(signal.SIGWINCH, self.orig_sigwinch_handler)
            with Termmode(self.orig_stdin, self.orig_tcattrs):
                terminal = blessings.Terminal(stream=sys.__stdout__)
                with terminal.fullscreen():
                    sys.__stdout__.write(terminal.save)
                    sys.__stdout__.write(terminal.move(0, 0))
                    sys.__stdout__.flush()
                    p = subprocess.Popen(args,
                                         stdin=self.orig_stdin,
                                         stderr=sys.__stderr__,
                                         stdout=sys.__stdout__)
                    p.wait()
                    sys.__stdout__.write(terminal.restore)
                    sys.__stdout__.flush()
        finally:
            signal.signal(signal.SIGWINCH, prev_sigwinch_handler)

    def pager(self, text):
        command = os.environ.get('PAGER', 'less -rf').split()
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(text)
            tmp.flush()
            self.focus_on_subprocess(command + [tmp.name])

    def show_source(self):
        source = self.get_source_of_current_name()
        if source is None:
            self.status_bar.message(_('Cannot show source.'))
        else:
            if self.config.highlight_show_source:
                source = format(PythonLexer().get_tokens(source), TerminalFormatter())
            self.pager(source)

    def help_text(self):
        return (self.version_help_text() + '\n' + self.key_help_text()).encode('utf8')

    def version_help_text(self):
        return (('bpython-curtsies version %s' % bpython.__version__) + ' ' +
                ('using curtsies version %s' % curtsies.__version__) + '\n' +
                HELP_MESSAGE.format(config_file_location=default_config_path(),
                                    example_config_url='https://raw.githubusercontent.com/bpython/bpython/master/sample-config',
                                    config=self.config)
               )

    def key_help_text(self):
        NOT_IMPLEMENTED = ['suspend', 'cut to buffer', 'search', 'last output', 'yank from buffer', 'cut to buffer']
        pairs = []
        pairs.append(['complete history suggestion', 'right arrow at end of line'])
        pairs.append(['previous match with current line', 'up arrow'])
        for functionality, key in [(attr[:-4].replace('_', ' '), getattr(self.config, attr))
                                   for attr in self.config.__dict__
                                   if attr.endswith('key')]:
            if functionality in NOT_IMPLEMENTED: key = "Not Implemented"
            if key == '': key = 'Disabled'

            pairs.append([functionality, key])

        max_func = max(len(func) for func, key in pairs)
        return '\n'.join('%s : %s' % (func.rjust(max_func), key) for func, key in pairs)

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
    if len(event) > 1:# basically "is there a special curtsies names for this key?"
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
