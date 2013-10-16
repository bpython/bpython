# -*- coding: utf-8 -*- 

from fmtstr.fmtfuncs import *
from fmtstr.fsarray import fsarray
from fmtstr.bpythonparse import func_for_letter

import logging

#TODO take the boring parts of repl.paint out into here?

# All paint functions should
# * return an array of the width they were asked for
# * return an array not larger than the height they were asked for

def display_linize(msg, columns):
    display_lines = ([msg[start:end]
                        for start, end in zip(
                            range(0, len(msg), columns),
                            range(columns, len(msg)+columns, columns))]
                    if msg else [])
    return display_lines

def paint_history(rows, columns, display_lines):
    lines = []
    for r, line in zip(range(rows), display_lines[-rows:]):
        lines.append((fmtstr(line)+' '*1000)[:columns])
    r = fsarray(lines)
    assert r.shape[0] <= rows, repr(r.shape)+' '+repr(rows)
    assert r.shape[1] <= columns, repr(r.shape)+' '+repr(columns)
    return r

def paint_current_line(rows, columns, current_display_line):
    lines = display_linize(current_display_line, columns)
    return fsarray([(line+' '*columns)[:columns] for line in lines])

def matches_lines(rows, columns, matches, current, config):
    highlight_color = lambda x: red(on_blue(x))
    if not matches:
        return []
    color = func_for_letter(config.color_scheme['main'])
    max_match_width = max(len(m) for m in matches)
    words_wide = max(1, (columns - 1) // (max_match_width + 1))
    matches_lines = [fmtstr(' ').join(color(m.ljust(max_match_width))
                                        if m != current
                                        else highlight_color(m) + ' '*(max_match_width - len(m))
                                      for m in matches[i:i+words_wide])
                     for i in range(0, len(matches), words_wide)]
    logging.debug('match: %r' % current)
    logging.debug('matches_lines: %r' % matches_lines)
    return matches_lines

def formatted_argspec(argspec):
    return argspec[0] + '(' + ", ".join(argspec[1][0]) + ')'

def paint_infobox(rows, columns, matches, argspec, match, docstring, config):
    """Returns painted completions, argspec, match, docstring etc."""
    if not (rows and columns):
        return fsarray(0, 0)
    color = func_for_letter(config.color_scheme['main'])
    lines = ((display_linize(blue(formatted_argspec(argspec)), columns-2) if argspec else []) +
             ([fmtstr('')] if docstring else []) +
             sum(([color(x) for x in display_linize(line, columns-2)]
                 for line in docstring.split('\n')) if docstring else [], []) +
             (matches_lines(rows, columns, matches, match, config) if matches else [])
             )

    # add borders
    width = min(columns - 2, max([len(line) for line in lines]))
    output_lines = []
    output_lines.append(u'┌'+u'─'*width+u'┐')
    for line in lines:
        output_lines.append(u'│'+((line+' '*(width - len(line)))[:width])+u'│')
    output_lines.append(u'└'+u'─'*width+u'┘')
    r = fsarray(output_lines[:rows])
    assert len(r.shape) == 2
    #return r
    return fsarray(r[:rows-1, :])

def paint_last_events(rows, columns, names):
    width = min(max(len(name) for name in names), columns-2)
    output_lines = []
    output_lines.append(u'┌'+u'─'*width+u'┐')
    for name in names[-(rows-2):]:
        output_lines.append(u'│'+name[:width].center(width)+u'│')
    output_lines.append(u'└'+u'─'*width+u'┘')
    r = fsarray(output_lines)
    return r

def paint_statusbar(rows, columns, msg, config):
    return fsarray([func_for_letter(config.color_scheme['main'])(msg.ljust(columns))])

