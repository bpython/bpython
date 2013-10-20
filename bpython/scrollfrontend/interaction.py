import Queue
import time

from bpython.repl import Interaction as BpythonInteraction

from bpython.scrollfrontend.manual_readline import char_sequences as rl_char_sequences

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
    def __init__(self, initial_message='', permanent_text=""):
        self._current_line = ''
        self.cursor_offset_in_line = 0
        self.in_prompt = False
        self.in_confirm = False
        self.prompt = ''
        self._message = initial_message
        self.message_start_time = time.time()
        self.message_time = 3
        self.permanent_text = permanent_text
        self.response_queue = Queue.Queue(maxsize=1)
        self.request_or_notify_queue = Queue.Queue()

    @property
    def has_focus(self):
        return self.in_prompt or self.in_confirm

    def message(self, msg):
        self.message_start_time = time.time()
        self._message = msg

    def _check_for_expired_message(self):
        if self._message and time.time() > self.message_start_time + self.message_time:
            self._message = ''

    def process_event(self, e):
        """Returns True if shutting down"""
        assert self.in_prompt or self.in_confirm
        if e in rl_char_sequences:
            self.cursor_offset_in_line, self._current_line = rl_char_sequences[e](self.cursor_offset_in_line, self._current_line)
        elif e == "":
            raise KeyboardInterrupt()
        elif e == "":
            raise SystemExit()
        elif self.in_prompt and e in ("\n", "\r"):
            self.response_queue.put(self._current_line)
            self.escape()
        elif self.in_confirm:
            if e in ('y', 'Y'):
                self.response_queue.put(True)
            else:
                self.response_queue.put(False)
            self.escape()
        elif e in ['\x1b', '\t', '\x1b\t', '\x1b\x1b']:
            self.response_queue.put(False)
            self.escape()
        else: # add normal character
            self._current_line = (self._current_line[:self.cursor_offset_in_line] +
                                 e +
                                 self._current_line[self.cursor_offset_in_line:])
            self.cursor_offset_in_line += 1

    def escape(self):
        """unfocus from statusbar, clear prompt state, wait for notify call"""
        self.wait_for_request_or_notify()
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

    def wait_for_request_or_notify(self):
        try:
            r = self.request_or_notify_queue.get(True, 1)
        except Queue.Empty:
            raise Exception('Main thread blocked because task thread not calling back')
        return r

    # interaction interface - should be called from other threads
    def notify(self, msg, n=3):
        self.message_time = n
        self.message(msg)
        self.request_or_notify_queue.put(msg)
    # below Really ought to be called from threads other than the mainloop because they block
    def confirm(self, q):
        """Expected to return True or False, given question prompt q"""
        self.prompt = q
        self.in_confirm = True
        self.request_or_notify_queue.put(q)
        return self.response_queue.get()
    def file_prompt(self, s):
        """Expected to return a file name, given """
        self.prompt = s.replace('Esc', 'Tab')
        self.in_prompt = True
        self.request_or_notify_queue.put(s)
        r = self.response_queue.get()
        return r

