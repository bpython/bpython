"""Extracting and changing portions of the current line

All functions take cursor offset from the beginning of the line and the line of
Python code, and return None, or a tuple of the start index, end index, and the
word."""
from __future__ import unicode_literals

import re

from itertools import chain
from collections import namedtuple
from pygments.token import Token

from bpython.lazyre import LazyReCompile
from bpython._py3compat import PythonLexer, py3

current_word_re = LazyReCompile(r'[\w_][\w0-9._]*[(]?')
LinePart = namedtuple('LinePart', ['start', 'stop', 'word'])


def current_word(cursor_offset, line):
    """the object.attribute.attribute just before or under the cursor"""
    pos = cursor_offset
    matches = current_word_re.finditer(line)
    start = pos
    end = pos
    word = None
    for m in matches:
        if m.start() < pos and m.end() >= pos:
            start = m.start()
            end = m.end()
            word = m.group()
    if word is None:
        return None
    return LinePart(start, end, word)


current_dict_key_re = LazyReCompile(r'''[\w_][\w0-9._]*\[([\w0-9._(), '"]*)''')


def current_dict_key(cursor_offset, line):
    """If in dictionary completion, return the current key"""
    matches = current_dict_key_re.finditer(line)
    for m in matches:
        if m.start(1) <= cursor_offset and m.end(1) >= cursor_offset:
            return LinePart(m.start(1), m.end(1), m.group(1))
    return None


current_dict_re = LazyReCompile(r'''([\w_][\w0-9._]*)\[([\w0-9._(), '"]*)''')


def current_dict(cursor_offset, line):
    """If in dictionary completion, return the dict that should be used"""
    matches = current_dict_re.finditer(line)
    for m in matches:
        if m.start(2) <= cursor_offset and m.end(2) >= cursor_offset:
            return LinePart(m.start(1), m.end(1), m.group(1))
    return None


current_string_re = LazyReCompile(
    '''(?P<open>(?:""")|"|(?:''\')|')(?:((?P<closed>.+?)(?P=open))|'''
    '''(?P<unclosed>.+))''')


def current_string(cursor_offset, line):
    """If inside a string of nonzero length, return the string (excluding
    quotes)

    Weaker than bpython.Repl's current_string, because that checks that a
    string is a string based on previous lines in the buffer."""
    for m in current_string_re.finditer(line):
        i = 3 if m.group(3) else 4
        if m.start(i) <= cursor_offset and m.end(i) >= cursor_offset:
            return LinePart(m.start(i), m.end(i), m.group(i))
    return None


current_object_re = LazyReCompile(r'([\w_][\w0-9_]*)[.]')


def current_object(cursor_offset, line):
    """If in attribute completion, the object on which attribute should be
    looked up."""
    match = current_word(cursor_offset, line)
    if match is None:
        return None
    start, end, word = match
    matches = current_object_re.finditer(word)
    s = ''
    for m in matches:
        if m.end(1) + start < cursor_offset:
            if s:
                s += '.'
            s += m.group(1)
    if not s:
        return None
    return LinePart(start, start+len(s), s)


current_object_attribute_re = LazyReCompile(r'([\w_][\w0-9_]*)')


def current_object_attribute(cursor_offset, line):
    """If in attribute completion, the attribute being completed"""
    match = current_word(cursor_offset, line)
    if match is None:
        return None
    start, end, word = match
    matches = current_object_attribute_re.finditer(word)
    next(matches)
    for m in matches:
        if (m.start(1) + start <= cursor_offset and
                m.end(1) + start >= cursor_offset):
            return LinePart(m.start(1) + start, m.end(1) + start, m.group(1))
    return None


current_from_import_from_re = LazyReCompile(
    r'from ([\w0-9_.]*)(?:\s+import\s+([\w0-9_]+[,]?\s*)+)*')


def current_from_import_from(cursor_offset, line):
    """If in from import completion, the word after from

    returns None if cursor not in or just after one of the two interesting
    parts of an import: from (module) import (name1, name2)
    """
    # TODO allow for as's
    tokens = line.split()
    if not ('from' in tokens or 'import' in tokens):
        return None
    matches = current_from_import_from_re.finditer(line)
    for m in matches:
        if ((m.start(1) < cursor_offset and m.end(1) >= cursor_offset) or
                (m.start(2) < cursor_offset and m.end(2) >= cursor_offset)):
            return LinePart(m.start(1), m.end(1), m.group(1))
    return None


current_from_import_import_re_1 = LazyReCompile(r'from\s([\w0-9_.]*)\s+import')
current_from_import_import_re_2 = LazyReCompile(r'([\w0-9_]+)')
current_from_import_import_re_3 = LazyReCompile(r'[,][ ]([\w0-9_]*)')


def current_from_import_import(cursor_offset, line):
    """If in from import completion, the word after import being completed

    returns None if cursor not in or just after one of these words
    """
    baseline = current_from_import_import_re_1.search(line)
    if baseline is None:
        return None
    match1 = current_from_import_import_re_2.search(line[baseline.end():])
    if match1 is None:
        return None
    matches = current_from_import_import_re_3.finditer(line[baseline.end():])
    for m in chain((match1, ), matches):
        start = baseline.end() + m.start(1)
        end = baseline.end() + m.end(1)
        if start < cursor_offset and end >= cursor_offset:
            return LinePart(start, end, m.group(1))
    return None


current_import_re_1 = LazyReCompile(r'import')
current_import_re_2 = LazyReCompile(r'([\w0-9_.]+)')
current_import_re_3 = LazyReCompile(r'[,][ ]([\w0-9_.]*)')


def current_import(cursor_offset, line):
    # TODO allow for multiple as's
    baseline = current_import_re_1.search(line)
    if baseline is None:
        return None
    match1 = current_import_re_2.search(line[baseline.end():])
    if match1 is None:
        return None
    matches = current_import_re_3.finditer(line[baseline.end():])
    for m in chain((match1, ), matches):
        start = baseline.end() + m.start(1)
        end = baseline.end() + m.end(1)
        if start < cursor_offset and end >= cursor_offset:
            return LinePart(start, end, m.group(1))


current_method_definition_name_re = LazyReCompile("def\s+([a-zA-Z_][\w]*)")


def current_method_definition_name(cursor_offset, line):
    """The name of a method being defined"""
    matches = current_method_definition_name_re.finditer(line)
    for m in matches:
        if (m.start(1) <= cursor_offset and m.end(1) >= cursor_offset):
            return LinePart(m.start(1), m.end(1), m.group(1))
    return None


current_single_word_re = LazyReCompile(r"(?<![.])\b([a-zA-Z_][\w]*)")


def current_single_word(cursor_offset, line):
    """the un-dotted word just before or under the cursor"""
    matches = current_single_word_re.finditer(line)
    for m in matches:
        if m.start(1) <= cursor_offset and m.end(1) >= cursor_offset:
            return LinePart(m.start(1), m.end(1), m.group(1))
    return None


def current_dotted_attribute(cursor_offset, line):
    """The dotted attribute-object pair before the cursor"""
    match = current_word(cursor_offset, line)
    if match is None:
        return None
    start, end, word = match
    if '.' in word[1:]:
        return LinePart(start, end, word)


current_string_literal_attr_re = LazyReCompile(
    "('''" +
    r'''|"""|'|")''' +
    r'''((?:(?=([^"'\\]+|\\.|(?!\1)["']))\3)*)\1[.]([a-zA-Z_]?[\w]*)''')


def current_string_literal_attr(cursor_offset, line):
    """The attribute following a string literal"""
    matches = current_string_literal_attr_re.finditer(line)
    for m in matches:
        if m.start(4) <= cursor_offset and m.end(4) >= cursor_offset:
            return LinePart(m.start(4), m.end(4), m.group(4))
    return None


current_indexed_member_re = LazyReCompile(
    r'''([a-zA-Z_][\w.]*)\[([a-zA-Z0-9_"']+)\]\.([\w.]*)''')


def current_indexed_member_access(cursor_offset, line):
    """An identifier being indexed and member accessed"""
    matches = current_indexed_member_re.finditer(line)
    for m in matches:
        if m.start(3) <= cursor_offset and m.end(3) >= cursor_offset:
            return LinePart(m.start(1), m.end(3), m.group())


def current_indexed_member_access_identifier(cursor_offset, line):
    """An identifier being indexed, e.g. foo in foo[1].bar"""
    matches = current_indexed_member_re.finditer(line)
    for m in matches:
        if m.start(3) <= cursor_offset and m.end(3) >= cursor_offset:
            return LinePart(m.start(1), m.end(1), m.group(1))


def current_indexed_member_access_identifier_with_index(cursor_offset, line):
    """An identifier being indexed with the index, e.g. foo[1] in foo[1].bar"""
    matches = current_indexed_member_re.finditer(line)
    for m in matches:
        if m.start(3) <= cursor_offset and m.end(3) >= cursor_offset:
            return LinePart(m.start(1), m.end(2)+1,
                            "%s[%s]" % (m.group(1), m.group(2)))


def current_indexed_member_access_member(cursor_offset, line):
    """The member name of an indexed object, e.g. bar in foo[1].bar"""
    matches = current_indexed_member_re.finditer(line)
    for m in matches:
        if m.start(3) <= cursor_offset and m.end(3) >= cursor_offset:
            return LinePart(m.start(3), m.end(3), m.group(3))

current_simple_expression_re = LazyReCompile(
    r'''([a-zA-Z_][\w.]*)\[([a-zA-Z0-9_"']+)\]\.([\w.]*)''')

def _current_simple_expression(cursor_offset, line):
    """
    Returns the current "simple expression" being attribute accessed

    build asts from with increasing numbers of characters.
    Find the biggest valid ast.
    Once our attribute access is a subtree, stop


    """
    for i in range(cursor):
        pass


def current_simple_expression(cursor_offset, line):
    """The expression attribute lookup being performed on

    e.g. <foo[0][1].bar>.ba|z
    A "simple expression" contains only . lookup and [] indexing."""


def current_simple_expression_attribute(cursor_offset, line):
    """The attribute being looked up on a simple expression

    e.g. foo[0][1].bar.<ba|z>
    A "simple expression" contains only . lookup and [] indexing."""








