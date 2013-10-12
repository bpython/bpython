"""implementations of simple readline control sequences

just the ones that fit the model of transforming the current line
and the cursor location
in the order of description at http://www.bigsmoke.us/readline/shortcuts"""

from bpython.scrollfrontend.friendly import NotImplementedError
import re
char_sequences = {}

#TODO fix this - should use value in repl.
# Sadly, this breaks the pure function aspect of backspace!
INDENT = 4

#TODO make an object out of this so instances can have keybindings via config

def on(seq):
    def add_to_char_sequences(func):
        char_sequences[seq] = func
        return func
    return add_to_char_sequences

@on('[D')
@on('')
@on(chr(2))
@on('KEY_LEFT')
def left_arrow(cursor_offset, line):
    return max(0, cursor_offset - 1), line

@on('[C')
@on('')
@on(chr(6))
@on('KEY_RIGHT')
def right_arrow(cursor_offset, line):
    return min(len(line), cursor_offset + 1), line

@on('')
@on('KEY_HOME')
def beginning_of_line(cursor_offset, line):
    return 0, line

@on('')
@on('KEY_END')
def end_of_line(cursor_offset, line):
    return len(line), line

@on('f')
@on('l')
@on('\x1bOC')
def forward_word(cursor_offset, line):
    patt = r"\S\s"
    match = re.search(patt, line[cursor_offset:]+' ')
    delta = match.end() - 1 if match else 0
    return (cursor_offset + delta, line)

@on('b')
@on('\x1bOD')
@on('\x1bB')
def back_word(cursor_offset, line):
    return (last_word_pos(line[:cursor_offset]), line)

def last_word_pos(string):
    """returns the start index of the last word of given string"""
    patt = r'\S\s'
    match = re.search(patt, string[::-1])
    index = match and len(string) - match.end() + 1
    return index or 0

@on('[3~')
@on('KEY_DC')
def delete(cursor_offset, line):
    return (cursor_offset,
            line[:cursor_offset] + line[cursor_offset+1:])

@on('')
@on('')
@on('KEY_BACKSPACE')
def backspace(cursor_offset, line):
    if cursor_offset == 0:
        return cursor_offset, line
    if not line[:cursor_offset].strip(): #if just whitespace left of cursor
        front_white = len(line[:cursor_offset]) - len(line[:cursor_offset].lstrip())
        to_delete = ((front_white - 1) % INDENT) + 1
        return cursor_offset - to_delete, line[:to_delete]
    return (cursor_offset - 1,
            line[:cursor_offset - 1] + line[cursor_offset:])

@on('')
def delete_from_cursor_back(cursor_offset, line):
    return 0, line[cursor_offset:]

@on('')
def delete_from_cursor_forward(cursor_offset, line):
    return cursor_offset, line[:cursor_offset]

@on('d') # option-d
def delete_rest_of_word(cursor_offset, line):
    m = re.search(r'\w\b', line[cursor_offset:])
    if not m:
        return cursor_offset, line
    return cursor_offset, line[:cursor_offset] + line[m.start()+cursor_offset+1:]

@on('')
def delete_word_to_cursor(cursor_offset, line):
    matches = list(re.finditer(r'\s\S', line[:cursor_offset]))
    start = matches[-1].start()+1 if matches else 0
    return start, line[:start] + line[cursor_offset:]

@on('y')
def yank_prev_prev_killed_text(cursor_offset, line):
    raise NotImplementedError()

@on('')
def transpose_character_before_cursor(cursor_offset, line):
    return (min(len(line), cursor_offset + 1),
            line[:cursor_offset-1] +
            (line[cursor_offset] if len(line) > cursor_offset else '') +
            line[cursor_offset - 1] +
            line[cursor_offset+1:])

@on('t')
def transpose_word_before_cursor(cursor_offset, line):
    raise NotImplementedError()

# bonus functions (not part of readline)

@on('r')
def delete_line(cursor_offset, line):
    return 0, ""

@on('u')
def uppercase_next_word(cursor_offset, line):
    raise NotImplementedError()

@on('c')
def titlecase_next_word(cursor_offset, line):
    raise NotImplementedError()

@on('\x1b\x7f')
@on('\xff')
def delete_word_from_cursor_back(cursor_offset, line):
    """Whatever my option-delete does in bash on my mac"""
    if not line:
        return cursor_offset, line
    starts = [m.start() for m in list(re.finditer(r'\b\w', line)) if m.start() < cursor_offset]
    if starts:
        return starts[-1], line[:starts[-1]] + line[cursor_offset:]
    return cursor_offset, line

def get_updated_char_sequences(key_dispatch, config):
    updated_char_sequences = dict(char_sequences)
    updated_char_sequences[key_dispatch[config.delete_key]] = backspace
    updated_char_sequences[key_dispatch[config.clear_word_key]] = delete_word_to_cursor
    updated_char_sequences[key_dispatch[config.clear_line_key]] = delete_from_cursor_back
    return updated_char_sequences

if __name__ == '__main__':
    import doctest; doctest.testmod()
    from pprint import pprint
    pprint(char_sequences)


