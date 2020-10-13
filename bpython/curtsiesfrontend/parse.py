from functools import partial
import re

from bpython.lazyre import LazyReCompile

from curtsies.termformatconstants import FG_COLORS, BG_COLORS, colors
from curtsies.formatstring import fmtstr, FmtStr


cnames = dict(zip("krgybmcwd", colors + ("default",)))


def func_for_letter(l, default="k"):
    """Returns FmtStr constructor for a bpython-style color code"""
    if l == "d":
        l = default
    elif l == "D":
        l = default.upper()
    return partial(fmtstr, fg=cnames[l.lower()], bold=l.isupper())


def color_for_letter(l, default="k"):
    if l == "d":
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
    return (
        sum((fs_from_match(d) for d in stuff[1:]), fs_from_match(stuff[0]))
        if len(stuff) > 0
        else FmtStr()
    )


def fs_from_match(d):
    atts = {}
    if d["fg"]:

        # this isn't according to spec as I understand it
        if d["fg"].isupper():
            d["bold"] = True
        # TODO figure out why boldness isn't based on presence of \x02

        color = cnames[d["fg"].lower()]
        if color != "default":
            atts["fg"] = FG_COLORS[color]
    if d["bg"]:
        if d["bg"] == "I":
            # hack for finding the "inverse"
            color = colors[
                (colors.index(color) + (len(colors) // 2)) % len(colors)
            ]
        else:
            color = cnames[d["bg"].lower()]
        if color != "default":
            atts["bg"] = BG_COLORS[color]
    if d["bold"]:
        atts["bold"] = True
    return fmtstr(d["string"], **atts)


peel_off_string_re = LazyReCompile(
    r"""(?P<colormarker>\x01
            (?P<fg>[krgybmcwdKRGYBMCWD]?)
            (?P<bg>[krgybmcwdKRGYBMCWDI]?)?)
        (?P<bold>\x02?)
        \x03
        (?P<string>[^\x04]*)
        \x04
        (?P<rest>.*)
        """,
    re.VERBOSE | re.DOTALL,
)


def peel_off_string(s):
    m = peel_off_string_re.match(s)
    assert m, repr(s)
    d = m.groupdict()
    rest = d["rest"]
    del d["rest"]
    return d, rest
