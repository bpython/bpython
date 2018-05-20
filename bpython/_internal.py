# encoding: utf-8

from __future__ import absolute_import

import pydoc
import sys

from .pager import page

# Ugly monkeypatching
pydoc.pager = page


class _Helper(object):

    def __init__(self):
        if hasattr(pydoc.Helper, "output"):
            # See issue #228
            self.helper = pydoc.Helper(sys.stdin, None)
        else:
            self.helper = pydoc.Helper(sys.stdin, sys.stdout)

    def __repr__(self):
        return ("Type help() for interactive help, "
                "or help(object) for help about object.")

    def __call__(self, *args, **kwargs):
        self.helper(*args, **kwargs)


_help = _Helper()


# vim: sw=4 ts=4 sts=4 ai et
