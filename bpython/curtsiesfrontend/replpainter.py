# -*- coding: utf-8 -*-

import logging
import itertools
from six.moves import range

from curtsies import fsarray, fmtstr
from curtsies.formatstring import linesplit
from curtsies.fmtfuncs import bold

from bpython.curtsiesfrontend.parse import func_for_letter
from bpython._py3compat import py3
if not py3:
    import inspect

logger = logging.getLogger(__name__)

# All paint functions should
# * return an array of the width they were asked for
# * return an array not taller than the height they were asked for


def display_linize(msg, columns, blank_line=False):
    """Returns lines obtained by splitting msg over multiple lines.

    Warning: if msg is empty, returns an empty list of lines"""
    display_lines = ([msg[start:end]
                      for start, end in zip(
                          range(0, len(msg), columns),
                          range(columns, len(msg)+columns, columns))]
                     if msg else ([''] if blank_line else []))
    return display_lines


def paint_history(rows, columns, display_lines):
    lines = []
    for r, line in zip(range(rows), display_lines[-rows:]):
        lines.append(fmtstr(line[:columns]))
    r = fsarray(lines, width=columns)
    assert r.shape[0] <= rows, repr(r.shape)+' '+repr(rows)
    assert r.shape[1] <= columns, repr(r.shape)+' '+repr(columns)
    return r


def paint_current_line(rows, columns, current_display_line):
    lines = display_linize(current_display_line, columns, True)
    return fsarray(lines, width=columns)


def matches_lines(rows, columns, matches, current, config, format):
    highlight_color = func_for_letter(config.color_scheme['operator'].lower())

    if not matches:
        return []
    color = func_for_letter(config.color_scheme['main'])
    max_match_width = max(len(m) for m in matches)
    words_wide = max(1, (columns - 1) // (max_match_width + 1))
    matches = [format(m) for m in matches]
    if current:
        current = format(current)

    matches_lines = [fmtstr(' ').join(color(m.ljust(max_match_width))
                                      if m != current
                                      else highlight_color(
                                          m.ljust(max_match_width))
                                      for m in matches[i:i+words_wide])
                     for i in range(0, len(matches), words_wide)]

    logger.debug('match: %r' % current)
    logger.debug('matches_lines: %r' % matches_lines)
    return matches_lines


def formatted_argspec(argspec, columns, config):
    # Pretty directly taken from bpython.cli
    is_bound_method = argspec[2]
    func = argspec[0]
    args = argspec[1][0]
    kwargs = argspec[1][3]
    _args = argspec[1][1]  # *args
    _kwargs = argspec[1][2]  # **kwargs
    is_bound_method = argspec[2]
    in_arg = argspec[3]
    if py3:
        kwonly = argspec[1][4]
        kwonly_defaults = argspec[1][5] or dict()

    arg_color = func_for_letter(config.color_scheme['name'])
    func_color = func_for_letter(config.color_scheme['name'].swapcase())
    punctuation_color = func_for_letter(config.color_scheme['punctuation'])
    token_color = func_for_letter(config.color_scheme['token'])
    bolds = {token_color: lambda x: bold(token_color(x)),
             arg_color: lambda x: bold(arg_color(x))}

    s = func_color(func) + arg_color(': (')

    if is_bound_method and isinstance(in_arg, int):
        # TODO what values could this have?
        in_arg += 1

    for i, arg in enumerate(args):
        kw = None
        if kwargs and i >= len(args) - len(kwargs):
            kw = str(kwargs[i - (len(args) - len(kwargs))])
        color = token_color if in_arg in (i, arg) else arg_color
        if i == in_arg or arg == in_arg:
            color = bolds[color]

        if not py3:
            s += color(inspect.strseq(arg, str))
        else:
            s += color(arg)

        if kw is not None:
            s += punctuation_color('=')
            s += token_color(kw)

        if i != len(args) - 1:
            s += punctuation_color(', ')

    if _args:
        if args:
            s += punctuation_color(', ')
        s += token_color('*%s' % (_args,))

    if py3 and kwonly:
        if not _args:
            if args:
                s += punctuation_color(', ')
            s += punctuation_color('*')
        marker = object()
        for arg in kwonly:
            s += punctuation_color(', ')
            color = token_color
            if in_arg:
                color = bolds[color]
            s += color(arg)
            default = kwonly_defaults.get(arg, marker)
            if default is not marker:
                s += punctuation_color('=')
                s += token_color(repr(default))

    if _kwargs:
        if args or _args or (py3 and kwonly):
            s += punctuation_color(', ')
        s += token_color('**%s' % (_kwargs,))
    s += punctuation_color(')')

    return linesplit(s, columns)


def formatted_docstring(docstring, columns, config):
    color = func_for_letter(config.color_scheme['comment'])
    return sum(([color(x) for x in (display_linize(line, columns) if line else
                                    fmtstr(''))]
                for line in docstring.split('\n')), [])


def paint_infobox(rows, columns, matches, argspec, match, docstring, config,
                  format):
    """Returns painted completions, argspec, match, docstring etc."""
    if not (rows and columns):
        return fsarray(0, 0)
    width = columns - 4
    lines = ((formatted_argspec(argspec, width, config) if argspec else []) +
             (matches_lines(rows, width, matches, match, config, format)
              if matches else []) +
             (formatted_docstring(docstring, width, config)
              if docstring else []))

    def add_border(line):
        """Add colored borders left and right to a line."""
        new_line = border_color(config.left_border + ' ')
        new_line += line.ljust(width)[:width]
        new_line += border_color(' ' + config.right_border)
        return new_line

    border_color = func_for_letter(config.color_scheme['main'])

    top_line = border_color(config.left_top_corner +
                            config.top_border * (width + 2) +
                            config.right_top_corner)
    bottom_line = border_color(config.left_bottom_corner +
                               config.bottom_border * (width + 2) +
                               config.right_bottom_corner)

    output_lines = list(itertools.chain((top_line, ), map(add_border, lines),
                                        (bottom_line, )))
    r = fsarray(output_lines[:min(rows - 1,
                                  len(output_lines) - 1)] + output_lines[-1:])
    return r


def paint_last_events(rows, columns, names, config):
    if not names:
        return fsarray([])
    width = min(max(len(name) for name in names), columns - 2)
    output_lines = []
    output_lines.append(config.left_top_corner+config.top_border * width +
                        config.right_top_corner)
    for name in reversed(names[max(0, len(names) - (rows - 2)):]):
        output_lines.append(config.left_border + name[:width].center(width) +
                            config.right_border)
    output_lines.append(config.left_bottom_corner +
                        config.bottom_border * width +
                        config.right_bottom_corner)
    return fsarray(output_lines)


def paint_statusbar(rows, columns, msg, config):
    func = func_for_letter(config.color_scheme['main'])
    return fsarray([func(msg.ljust(columns))[:columns]])
