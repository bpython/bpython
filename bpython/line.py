"""Extracting and changing portions of the current line

All functions take cursor offset from the beginning of the line and the line of python code,
and return None, or a tuple of the start index, end index, and the word"""

import re

def current_word(cursor_offset, line):
    """the object.attribute.attribute just before or under the cursor"""
    pos = cursor_offset
    matches = list(re.finditer(r'[\w_][\w0-9._]*[(]?', line))
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
    matches = list(re.finditer(r'[\w_][\w0-9._]*\[([\w0-9._(), ]*)', line))
    for m in matches:
        if m.start(1) <= cursor_offset and m.end(1) >= cursor_offset:
            return (m.start(1), m.end(1), m.group(1))
    return None

def current_dict(cursor_offset, line):
    """If in dictionary completion, return the dict that should be used"""
    matches = list(re.finditer(r'([\w_][\w0-9._]*)\[([\w0-9._(), ]*)', line))
    for m in matches:
        if m.start(2) <= cursor_offset and m.end(2) >= cursor_offset:
            return (m.start(1), m.end(1), m.group(1))
    return None

def current_string(cursor_offset, line):
    """If inside a string, return the string (excluding quotes)

    Weaker than bpython.Repl's current_string, because that checks that a string is a string
    based on previous lines in the buffer"""
    matches = list(re.finditer('''(?P<open>(?:""")|"|(?:''\')|')(.*?)(?P=open)''', line))
    for m in matches:
        if m.start(2) <= cursor_offset and m.end(2) >= cursor_offset:
            return m.start(2), m.end(2), m.group(2)
    return None

def current_object(cursor_offset, line):
    """If in attribute completion, the object on which attribute should be looked up"""
    match = current_word(cursor_offset, line)
    if match is None: return None
    start, end, word = match
    matches = list(re.finditer(r'([\w_][\w0-9_]*)[.]', word))
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
    matches = list(re.finditer(r'([\w_][\w0-9_]*)[.]?', word))
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
    matches = list(re.finditer(r'from ([\w0-9_.]*)(?:\s+import\s+([\w0-9_]+[,]?\s*)+)*', line))
    for m in matches:
        if ((m.start(1) < cursor_offset and m.end(1) >= cursor_offset) or
            (m.start(2) < cursor_offset and m.end(2) >= cursor_offset)):
            return m.start(1), m.end(1), m.group(1)
    return None

def current_from_import_import(cursor_offset, line):
    """If in from import completion, the word after import being completed

    returns None if cursor not in or just after one of these words
    """
    baseline = re.search(r'from\s([\w0-9_.]*)\s+import', line)
    if baseline is None:
        return None
    match1 = re.search(r'([\w0-9_]+)', line[baseline.end():])
    if match1 is None:
        return None
    matches = list(re.finditer(r'[,][ ]([\w0-9_]*)', line[baseline.end():]))
    for m in [match1] + matches:
        start = baseline.end() + m.start(1)
        end = baseline.end() + m.end(1)
        if start < cursor_offset and end >= cursor_offset:
            return start, end, m.group(1)
    return None

def current_import(cursor_offset, line):
    #TODO allow for multiple as's
    baseline = re.search(r'import', line)
    if baseline is None:
        return None
    match1 = re.search(r'([\w0-9_.]+)', line[baseline.end():])
    if match1 is None:
        return None
    matches = list(re.finditer(r'[,][ ]([\w0-9_.]*)', line[baseline.end():]))
    for m in [match1] + matches:
        start = baseline.end() + m.start(1)
        end = baseline.end() + m.end(1)
        if start < cursor_offset and end >= cursor_offset:
            return start, end, m.group(1)
