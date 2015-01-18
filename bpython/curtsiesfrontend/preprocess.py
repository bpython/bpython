"""Tools for preparing code to be run in the REPL (removing blank lines, etc)"""
import re

from bpython.curtsiesfrontend.interpreter import code_finished_will_parse

#TODO specifically catch IndentationErrors instead of any syntax errors

def indent_empty_lines(s, compiler):
    """Indents blank lines that would otherwise cause early compilation

    Only really works if starting on a new line"""
    lines = s.split('\n')
    ends_with_newline = False
    if lines and not lines[-1]:
        ends_with_newline = True
        lines.pop()
    result_lines = []

    for p_line, line, n_line in zip([''] + lines[:-1], lines, lines[1:] + ['']):
        if len(line) == 0:
            p_indent = re.match(r'\s*', p_line).group()
            n_indent = re.match(r'\s*', n_line).group()
            result_lines.append(min([p_indent, n_indent], key=len) + line)
        else:
            result_lines.append(line)

    return '\n'.join(result_lines) + ('\n' if ends_with_newline else '')

