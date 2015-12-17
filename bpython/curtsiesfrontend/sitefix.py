import sys
import functools

from six.moves import builtins


def resetquit(builtins):
    """Redefine builtins 'quit' and 'exit' not so close stdin

    """
    def __call__(self, code=None):
        raise SystemExit(code)
    __call__.__name__ = 'FakeQuitCall'
    builtins.quit.__class__.__call__ = __call__


def monkeypatch_quit():
    if 'site' in sys.modules:
        resetquit(builtins)


orig_reload = builtins.reload


def reload(module):
    if module is sys:
        orig_stdout = sys.stdout
        orig_stderr = sys.stderr
        orig_stdin = sys.stdin
        orig_reload(sys)
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
        sys.stdin = orig_stdin
    else:
        builtins.reload(sys)


functools.update_wrapper(reload, orig_reload)


def monkeypatch_reload():
    builtins.reload = reload
