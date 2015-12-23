import functools
import imp
import sys

from six.moves import builtins

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
        resetquit(builtins)

orig_reload = None
if py3:
    import importlib
    if hasattr(importlib, 'reload'):
        orig_reload = importlib.reload
    elif hasattr(imp, 'reload'):
        orig_reload = imp.reload
else:
    orig_reload = builtins.reload

if orig_reload:
    def reload(module):
        if module is sys:
            orig_stdout = sys.stdout
            orig_stderr = sys.stderr
            orig_stdin = sys.stdin
            r = orig_reload(sys)
            sys.stdout = orig_stdout
            sys.stderr = orig_stderr
            sys.stdin = orig_stdin
            return r
        else:
            return orig_reload(module)

    functools.update_wrapper(reload, orig_reload)


def monkeypatch_reload():
    if py3 and hasattr(importlib, 'reload'):
        importlib.reload = reload
    elif py3 and hasattr(imp, 'reload'):
        imp.reload = reload
    else:
        builtins.reload = reload
