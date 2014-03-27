import greenlet
import time
import curtsies.events as events

from bpython.repl import Interaction as BpythonInteraction

from bpython.curtsiesfrontend.manual_readline import char_sequences as rl_char_sequences

class StatusBar(BpythonInteraction):
    """StatusBar and Interaction for Repl

    Passing of control back and forth between calls that use interact api
    (notify, confirm, file_prompt) like bpython.Repl.write2file and events
    on the main thread happens via those calls and self.wait_for_request_or_notify.

    Calling one of these three is required for the main thread to regain control!

    This is probably a terrible idea, and better would be rewriting this
    functionality in a evented or callback style, but trying to integrate
    bpython.Repl code.
    """
    def __init__(self, initial_message='', permanent_text="", refresh_request=lambda: None):
        self._current_line = ''
        self.cursor_offset_in_line = 0
        self.in_prompt = False
        self.in_confirm = False
        self.waiting_for_refresh = False
        self.prompt = ''
        self._message = initial_message
        self.message_start_time = time.time()
        self.message_time = 3
        self.permanent_text = permanent_text
        self.main_greenlet = greenlet.getcurrent()
        self.request_greenlet = None
        self.refresh_request = refresh_request

    @property
    def has_focus(self):
        return self.in_prompt or self.in_confirm or self.waiting_for_refresh

    def message(self, msg):
        self.message_start_time = time.time()
        self._message = msg

    def _check_for_expired_message(self):
        if self._message and time.time() > self.message_start_time + self.message_time:
            self._message = ''

    def process_event(self, e):
        """Returns True if shutting down"""
        assert self.in_prompt or self.in_confirm or self.waiting_for_refresh
        if isinstance(e, events.RefreshRequestEvent):
            self.waiting_for_refresh = False
            self.request_greenlet.switch()
        elif isinstance(e, events.PasteEvent):
            for ee in e.events:
                self.add_normal_character(ee if len(ee) == 1 else ee[-1]) #strip control seq
        elif e in rl_char_sequences:
            self.cursor_offset_in_line, self._current_line = rl_char_sequences[e](self.cursor_offset_in_line, self._current_line)
        elif e == "":
            raise KeyboardInterrupt()
        elif e == "":
            raise SystemExit()
        elif self.in_prompt and e in ("\n", "\r"):
            line = self._current_line
            self.escape()
            self.request_greenlet.switch(line)
        elif self.in_confirm:
            if e in ('y', 'Y'):
                self.request_greenlet.switch(True)
            else:
                self.request_greenlet.switch(False)
            self.escape()
        elif e in ['\x1b']:
            self.request_greenlet.switch(False)
            self.escape()
        else: # add normal character
            self.add_normal_character(e)

    def add_normal_character(self, e):
        self._current_line = (self._current_line[:self.cursor_offset_in_line] +
                             e +
                             self._current_line[self.cursor_offset_in_line:])
        self.cursor_offset_in_line += 1

    def escape(self):
        """unfocus from statusbar, clear prompt state, wait for notify call"""
        self.in_prompt = False
        self.in_confirm = False
        self.prompt = ''
        self._current_line = ''

    @property
    def current_line(self):
        self._check_for_expired_message()
        if self.in_prompt:
            return self.prompt + self._current_line
        if self.in_confirm:
            return self.prompt
        if self._message:
            return self._message
        return self.permanent_text

    # interaction interface - should be called from other greenlets
    def notify(self, msg, n=3):
        self.request_greenlet = greenlet.getcurrent()
        self.message_time = n
        self.message(msg)
        self.waiting_for_refresh = True
        self.refresh_request()
        self.main_greenlet.switch(msg)

    # below Really ought to be called from greenlets other than main because they block
    def confirm(self, q):
        """Expected to return True or False, given question prompt q"""
        self.request_greenlet = greenlet.getcurrent()
        self.prompt = q
        self.in_confirm = True
        return self.main_greenlet.switch(q)
    def file_prompt(self, s):
        """Expected to return a file name, given """
        self.request_greenlet = greenlet.getcurrent()
        self.prompt = s
        self.in_prompt = True
        result = self.main_greenlet.switch(s)
        return result
