import code
import Queue
import signal
import sys
import threading
import logging

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

    def load_code(self, source):
        self.source = source
        self.code_thread = None

    def run_code(self, input=None):
        """Returns Truthy values if code finishes, False otherwise

        if source code is complete, returns "done"
        if source code is incomplete, returns "unfinished"
        """
        if self.code_thread is None:
            assert self.source
            self.code_thread = threading.Thread(target=self._blocking_run_code, name='codethread')
            self.code_thread.daemon = True
            self.code_thread.start()
        else:
            assert self.code_is_waiting
            self.code_is_waiting = False
            self.responses_for_code_thread.put(input)

        request = self.requests_from_code_thread.get()
        if request[0] == 'done':
            return 'unfinished' if request[1] else 'done'
        else:
            method, args, kwargs = request
            self.code_is_waiting = True
            if method:
                method(*args, **kwargs)
                self.stuff_a_refresh_request()
            return False

    def _blocking_run_code(self):
        unfinished = self.interp.runsource(self.source)
        self.requests_from_code_thread.put(('done', unfinished))
    def _blocking_wait_for(self, method=lambda: None, args=[], kwargs={}):
        """The method the code would like to be called, or nothing

        Nothing means calls to run_code must be...
        does this thing even have a point? is it required for stdout.write?
        """
        self.requests_from_code_thread.put((method, args, kwargs))
        return self.responses_for_code_thread.get()

class FakeOutput(object):
    def __init__(self, coderunner, please):
        self.coderunner = coderunner
        self.please = please
    def write(self, *args, **kwargs):
        return self.coderunner._blocking_wait_for(self.please, args, kwargs)

if __name__ == '__main__':
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    c = CodeRunner(stuff_a_refresh_request=lambda: orig_stdout.flush() or orig_stderr.flush())
    stdout = FakeOutput(c, orig_stdout.write)
    stderr = FakeOutput(c, orig_stderr.write)
    sys.stdout = stdout
    sys.stderr = stderr
    c.load_code('1 + 1')
    c.run_code()
    c.run_code()
    c.run_code()
