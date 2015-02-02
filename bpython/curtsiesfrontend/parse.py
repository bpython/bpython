
from bpython.formatter import BPythonFormatter
from bpython._py3compat import PythonLexer
from bpython.config import Struct, loadini, default_config_path

from curtsies.termformatconstants import FG_COLORS, BG_COLORS, colors
from curtsies.formatstring import fmtstr, FmtStr

from pygments import format
from functools import partial

import re

cnames = dict(zip('krgybmcwd', colors + ('default',)))

def func_for_letter(l, default='k'):
    """Returns FmtStr constructor for a bpython-style color code"""
    if l == 'd':
        l = default
    elif l == 'D':
        l = default.upper()
    return partial(fmtstr, fg=cnames[l.lower()], bold=(l.lower() != l))

def color_for_letter(l, default='k'):
    if l == 'd':
        l = default
    return cnames[l.lower()]

def parse(s):
    """Returns a FmtStr object from a bpython-formatted colored string"""
    rest = s
    stuff = []
    while True:
        if not rest:
            break
        start, rest = peel_off_string(rest)
        stuff.append(start)
    return (sum((fs_from_match(d) for d in stuff[1:]), fs_from_match(stuff[0]))
            if len(stuff) > 0
            else FmtStr())

def fs_from_match(d):
    atts = {}
    if d['fg']:

        # this isn't according to spec as I understand it
        if d['fg'] != d['fg'].lower():
            d['bold'] = True
        #TODO figure out why boldness isn't based on presence of \x02

        color = cnames[d['fg'].lower()]
        if color != 'default':
            atts['fg'] = FG_COLORS[color]
    if d['bg']:
        if d['bg'] == 'I':
            color = colors[(colors.index(color) + (len(colors) // 2)) % len(colors)] # hack for finding the "inverse"
        else:
            color = cnames[d['bg'].lower()]
        if color != 'default':
            atts['bg'] = BG_COLORS[color]
    if d['bold']:
        atts['bold'] = True
    return fmtstr(d['string'], **atts)

def peel_off_string(s):
    p = r"""(?P<colormarker>\x01
                (?P<fg>[krgybmcwdKRGYBMCWD]?)
                (?P<bg>[krgybmcwdKRGYBMCWDI]?)?)
            (?P<bold>\x02?)
            \x03
            (?P<string>[^\x04]*)
            \x04
            (?P<rest>.*)
            """
    m = re.match(p, s, re.VERBOSE | re.DOTALL)
    assert m, repr(s)
    d = m.groupdict()
    rest = d['rest']
    del d['rest']
    return d, rest
