""""""
import sys

from bpython._py3compat import py3

def resetquit(builtins):
    """Redefine builtins 'quit' and 'exit' not so close stdin

    """
    def __call__(self, code=None):
        raise SystemExit(code)
    __call__.__name__ = 'FakeQuitCall'
    builtins.quit.__class__.__call__ = __call__

def monkeypatch_quit():
    if 'site' in sys.modules:
        resetquit(sys.modules['builtins' if py3 else '__builtin__'])
