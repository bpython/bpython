#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab

"""
Debugger factory. Set PYTHON_DEBUGGER to a module path that has a post_mortem
function in it. Defaults to pdb. This allows alternate debuggers to be used,
such as pycopia.debugger. :)
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


import os
import sys


post_mortem = None

def _get_debugger():
    global post_mortem
    modname = os.environ.get("PYTHON_DEBUGGER", "bpdb")
    __import__(modname)
    mod = sys.modules[modname]
    pm = getattr(mod, "post_mortem")
    if pm.__code__.co_argcount > 2:
        post_mortem = pm
    else:
        def _post_mortem(t, ex, exval):
            return pm(t)
        post_mortem = _post_mortem

_get_debugger()

