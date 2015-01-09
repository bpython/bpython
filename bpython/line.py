"""Extracting and changing portions of the current line

All functions take cursor offset from the beginning of the line and the line of python code,
and return None, or a tuple of the start index, end index, and the word"""

import re

current_word_re = re.compile(r'[\w_][\w0-9._]*[(]?')
current_dict_key_re = re.compile(r'''[\w_][\w0-9._]*\[([\w0-9._(), '"]*)''')
current_dict_re = re.compile(r'''([\w_][\w0-9._]*)\[([\w0-9._(), '"]*)''')
current_string_re = re.compile(
    '''(?P<open>(?:""")|"|(?:''\')|')(?:((?P<closed>.+?)(?P=open))|(?P<unclosed>.+))''')
current_object_re = re.compile(r'([\w_][\w0-9_]*)[.]')
current_object_attribute_re = re.compile(r'([\w_][\w0-9_]*)[.]?')
current_from_import_from_re = re.compile(r'from ([\w0-9_.]*)(?:\s+import\s+([\w0-9_]+[,]?\s*)+)*')
current_from_import_import_re_1 = re.compile(r'from\s([\w0-9_.]*)\s+import')
current_from_import_import_re_2 = re.compile(r'([\w0-9_]+)')
current_from_import_import_re_3 = re.compile(r'[,][ ]([\w0-9_]*)')
current_import_re_1 = re.compile(r'import')
current_import_re_2 = re.compile(r'([\w0-9_.]+)')
current_import_re_3 = re.compile(r'[,][ ]([\w0-9_.]*)')
current_method_definition_name_re = re.compile("def\s+([a-zA-Z_][\w]*)")
current_single_word_re = re.compile(r"(?<![.])\b([a-zA-Z_][\w]*)")
current_string_literal_attr_re = re.compile(
    "('''" +
    r'''|"""|'|")((?:(?=([^"'\\]+|\\.|(?!\1)["']))\3)*)\1[.]([a-zA-Z_]?[\w]*)''')

def current_word(cursor_offset, line):
    """the object.attribute.attribute just before or under the cursor"""
    pos = cursor_offset
    matches = list(current_word_re.finditer(line))
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
    return (start, end, word)

def current_dict_key(cursor_offset, line):
    """If in dictionary completion, return the current key"""
    matches = list(current_dict_key_re.finditer(line))
    for m in matches:
        if m.start(1) <= cursor_offset and m.end(1) >= cursor_offset:
            return (m.start(1), m.end(1), m.group(1))
    return None

def current_dict(cursor_offset, line):
    """If in dictionary completion, return the dict that should be used"""
    matches = list(current_dict_re.finditer(line))
    for m in matches:
        if m.start(2) <= cursor_offset and m.end(2) >= cursor_offset:
            return (m.start(1), m.end(1), m.group(1))
    return None

def current_string(cursor_offset, line):
    """If inside a string of nonzero length, return the string (excluding quotes)

    Weaker than bpython.Repl's current_string, because that checks that a string is a string
    based on previous lines in the buffer"""
    for m in current_string_re.finditer(line):
        i = 3 if m.group(3) else 4
        if m.start(i) <= cursor_offset and m.end(i) >= cursor_offset:
            return m.start(i), m.end(i), m.group(i)
    return None

def current_object(cursor_offset, line):
    """If in attribute completion, the object on which attribute should be looked up"""
    match = current_word(cursor_offset, line)
    if match is None: return None
    start, end, word = match
    matches = list(current_object_re.finditer(word))
    s = ''
    for m in matches:
        if m.end(1) + start < cursor_offset:
            if s:
                s += '.'
            s += m.group(1)
    if not s:
        return None
    return start, start+len(s), s

def current_object_attribute(cursor_offset, line):
    """If in attribute completion, the attribute being completed"""
    match = current_word(cursor_offset, line)
    if match is None: return None
    start, end, word = match
    matches = list(current_object_attribute_re.finditer(word))
    for m in matches[1:]:
        if m.start(1) + start <= cursor_offset and m.end(1) + start >= cursor_offset:
            return m.start(1) + start, m.end(1) + start, m.group(1)
    return None

def current_from_import_from(cursor_offset, line):
    """If in from import completion, the word after from

    returns None if cursor not in or just after one of the two interesting parts
    of an import: from (module) import (name1, name2)
    """
    #TODO allow for as's
    tokens = line.split()
    if not ('from' in tokens or 'import' in tokens):
        return None
    matches = list(current_from_import_from_re.finditer(line))
    for m in matches:
        if ((m.start(1) < cursor_offset and m.end(1) >= cursor_offset) or
            (m.start(2) < cursor_offset and m.end(2) >= cursor_offset)):
            return m.start(1), m.end(1), m.group(1)
    return None

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
    matches = list(current_from_import_import_re_3.finditer(line[baseline.end():]))
    for m in [match1] + matches:
        start = baseline.end() + m.start(1)
        end = baseline.end() + m.end(1)
        if start < cursor_offset and end >= cursor_offset:
            return start, end, m.group(1)
    return None

def current_import(cursor_offset, line):
    #TODO allow for multiple as's
    baseline = current_import_re_1.search(line)
    if baseline is None:
        return None
    match1 = current_import_re_2.search(line[baseline.end():])
    if match1 is None:
        return None
    matches = list(current_import_re_3.finditer(line[baseline.end():]))
    for m in [match1] + matches:
        start = baseline.end() + m.start(1)
        end = baseline.end() + m.end(1)
        if start < cursor_offset and end >= cursor_offset:
            return start, end, m.group(1)

def current_method_definition_name(cursor_offset, line):
    """The name of a method being defined"""
    matches = current_method_definition_name_re.finditer(line)
    for m in matches:
        if (m.start(1) <= cursor_offset and m.end(1) >= cursor_offset):
            return m.start(1), m.end(1), m.group(1)
    return None

def current_single_word(cursor_offset, line):
    """the un-dotted word just before or under the cursor"""
    matches = current_single_word_re.finditer(line)
    for m in matches:
        if (m.start(1) <= cursor_offset and m.end(1) >= cursor_offset):
            return m.start(1), m.end(1), m.group(1)
    return None

def current_dotted_attribute(cursor_offset, line):
    """The dotted attribute-object pair before the cursor"""
    match = current_word(cursor_offset, line)
    if match is None: return None
    start, end, word = match
    if '.' in word[1:]:
        return start, end, word

def current_string_literal_attr(cursor_offset, line):
    """The attribute following a string literal"""
    matches = current_string_literal_attr_re.finditer(line)
    for m in matches:
        if (m.start(4) <= cursor_offset and m.end(4) >= cursor_offset):
            return m.start(4), m.end(4), m.group(4)
    return None
