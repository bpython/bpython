import code
import Queue
import signal
import sys
import threading
import logging

class SigintHappened(object):
    pass

class SystemExitFromCodeThread(SystemExit):
    pass

class CodeRunner(object):
    """Runs user code in an interpreter, taking care of stdout/in/err"""
    def __init__(self, interp=None, stuff_a_refresh_request=lambda:None):
        self.interp = interp or code.InteractiveInterpreter()
        self.source = None
        self.code_thread = None
        self.requests_from_code_thread = Queue.Queue(maxsize=1)
        self.responses_for_code_thread = Queue.Queue(maxsize=1)
        self.stuff_a_refresh_request = stuff_a_refresh_request
        self.code_is_waiting = False
        self.sigint_happened = False
        self.orig_sigint_handler = None

    @property
    def running(self):
        return self.source and self.code_thread

    def load_code(self, source):
        """Prep code to be run"""
        self.source = source
        self.code_thread = None

    def _unload_code(self):
        """Called when done running code"""
        self.source = None
        self.code_thread = None
        self.code_is_waiting = False

    def run_code(self, for_code=None):
        """Returns Truthy values if code finishes, False otherwise

        if for_code is provided, send that value to the code thread
        if source code is complete, returns "done"
        if source code is incomplete, returns "unfinished"
        """
        if self.code_thread is None:
            assert self.source is not None
            self.code_thread = threading.Thread(target=self._blocking_run_code, name='codethread')
            self.code_thread.daemon = True
            self.orig_sigint_handler = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, self.sigint_handler)
            self.code_thread.start()
        else:
            assert self.code_is_waiting
            self.code_is_waiting = False
            signal.signal(signal.SIGINT, self.sigint_handler)
            if self.sigint_happened:
                self.sigint_happened = False
                self.responses_for_code_thread.put(SigintHappened)
            else:
                self.responses_for_code_thread.put(for_code)

        request = self.requests_from_code_thread.get()
        if request in ['wait', 'refresh']:
            self.code_is_waiting = True
            if request == 'refresh':
                self.stuff_a_refresh_request()
            return False
        elif request in ['done', 'unfinished']:
            self._unload_code()
            signal.signal(signal.SIGINT, self.orig_sigint_handler)
            self.orig_sigint_handler = None
            return request
        elif request in ['SystemExit']: #use the object?
            self._unload_code()
            raise SystemExitFromCodeThread()
        else:
            raise ValueError("Not a valid request_from_code_thread value: %r" % request)

    def sigint_handler(self, *args):
        if threading.current_thread() is self.code_thread:
            logging.debug('sigint while running user code!')
            raise KeyboardInterrupt()
        else:
            logging.debug('sigint while fufilling code request sigint handler running!')
            self.sigint_happened = True

    def _blocking_run_code(self):
        try:
            unfinished = self.interp.runsource(self.source)
        except SystemExit:
            self.requests_from_code_thread.put('SystemExit')
            return
        self.requests_from_code_thread.put('unfinished' if unfinished else 'done')

    def wait_and_get_value(self):
        """Return the argument passed in to .run_code(for_code)

        Nothing means calls to run_code must be...
        """
        self.requests_from_code_thread.put('wait')
        value = self.responses_for_code_thread.get()
        if value is SigintHappened:
            raise KeyboardInterrupt()
        return value

    def refresh_and_get_value(self):
        """Returns the argument passed in to .run_code(for_code) """
        self.requests_from_code_thread.put('refresh')
        value = self.responses_for_code_thread.get()
        if value is SigintHappened:
            raise KeyboardInterrupt()
        return value

class FakeOutput(object):
    def __init__(self, coderunner, please):
        self.coderunner = coderunner
        self.please = please
    def write(self, *args, **kwargs):
        self.please(*args, **kwargs)
        return self.coderunner.refresh_and_get_value()

def test_simple():
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    c = CodeRunner(stuff_a_refresh_request=lambda: orig_stdout.flush() or orig_stderr.flush())
    stdout = FakeOutput(c, orig_stdout.write)
    sys.stdout = stdout
    c.load_code('1 + 1')
    c.run_code()
    c.run_code()
    c.run_code()

def test_exception():
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    c = CodeRunner(stuff_a_refresh_request=lambda: orig_stdout.flush() or orig_stderr.flush())
    def ctrlc():
        raise KeyboardInterrupt()
    stdout = FakeOutput(c, lambda x: ctrlc())
    sys.stdout = stdout
    c.load_code('1 + 1')
    c.run_code()

if __name__ == '__main__':
    test_simple()

