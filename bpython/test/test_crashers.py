import fcntl
import os
import pty
import struct
import sys
import termios
import textwrap
import unittest

try:
    from twisted.internet import reactor
    from twisted.internet.defer import Deferred
    from twisted.internet.protocol import ProcessProtocol
    from twisted.trial.unittest import TestCase as TrialTestCase
except ImportError:
    reactor = None

TEST_CONFIG = os.path.join(os.path.dirname(__file__), "test.config")

def set_win_size(fd, rows, columns):
    s = struct.pack('HHHH', rows, columns, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, s)

class CrashersTest(object):
    backend = "cli"

    def run_bpython(self, input):
        """
        Run bpython (with `backend` as backend) in a subprocess and
        enter the given input. Uses a test config that disables the
        paste detection.

        Retuns bpython's output.
        """
        result = Deferred()

        class Protocol(ProcessProtocol):
            STATES = (SEND_INPUT, COLLECT) = xrange(2)

            def __init__(self):
                self.data = ""
                self.delayed_call = None
                self.states = iter(self.STATES)
                self.state = self.states.next()

            def outReceived(self, data):
                self.data += data
                if self.delayed_call is not None:
                    self.delayed_call.cancel()
                self.delayed_call = reactor.callLater(0.5, self.next)

            def next(self):
                self.delayed_call = None
                if self.state == self.SEND_INPUT:
                    index = self.data.find(">>> ")
                    if index >= 0:
                        self.data = self.data[index + 4:]
                        self.transport.write(input)
                        self.state = self.states.next()
                else:
                    self.transport.closeStdin()
                    if self.transport.pid is not None:
                        self.delayed_call = None
                        self.transport.signalProcess("TERM")

            def processExited(self, reason):
                if self.delayed_call is not None:
                    self.delayed_call.cancel()
                result.callback(self.data)

        (master, slave) = pty.openpty()
        set_win_size(slave, 25, 80)
        reactor.spawnProcess(Protocol(), sys.executable,
            (sys.executable, "-m", "bpython." + self.backend,
             "--config",  TEST_CONFIG),
            env=dict(TERM="vt100", LANG=os.environ.get("LANG", "")),
            usePTY=(master, slave, os.ttyname(slave)))
        return result

    def test_issue108(self):
        input = textwrap.dedent(
            """\
            def spam():
            u"y\\xe4y"
            \b
            spam(""")
        deferred = self.run_bpython(input)
        return deferred.addCallback(self.check_no_traceback)

    def test_issue133(self):
        input = textwrap.dedent(
            """\
            def spam(a, (b, c)):
            pass
            \b
            spam(1""")
        return self.run_bpython(input).addCallback(self.check_no_traceback)

    def check_no_traceback(self, data):
        tb = data[data.find("Traceback"):]
        self.assertTrue("Traceback" not in data, tb)

if reactor is not None:
    class CursesCrashersTest(TrialTestCase, CrashersTest):
        backend = "cli"

    class UrwidCrashersTest(TrialTestCase, CrashersTest):
        backend = "urwid"

if __name__ == "__main__":
    unittest.main()
