"""implementations of simple readline edit operations

just the ones that fit the model of transforming the current line
and the cursor location
based on http://www.bigsmoke.us/readline/shortcuts"""

import re
import inspect

INDENT = 4

#TODO Allow user config of keybindings for these actions

class AbstractEdits(object):

    default_kwargs = {
            'line': 'hello world',
            'cursor_offset': 5,
            'cut_buffer': 'there',
            }

    def __contains__(self, key):
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True

    def add(self, key, func, overwrite=False):
        if key in self:
            if overwrite:
                del self[key]
            else:
                raise ValueError('key %r already has a mapping' % (key,))
        params = inspect.getargspec(func)[0]
        args = dict((k, v) for k, v in self.default_kwargs.items() if k in params)
        r = func(**args)
        if len(r) == 2:
            if hasattr(func, 'kills'):
                raise ValueError('function %r returns two values, but has a kills attribute' % (func,))
            self.simple_edits[key] = func
        elif len(r) == 3:
            if not hasattr(func, 'kills'):
                raise ValueError('function %r returns three values, but has no kills attribute' % (func,))
            self.cut_buffer_edits[key] = func
        else:
            raise ValueError('return type of function %r not recognized' % (func,))

    def add_config_attr(self, config_attr, func):
        if config_attr in self.awaiting_config:
            raise ValueError('config attrribute %r already has a mapping' % (config_attr,))
        self.awaiting_config[config_attr] = func

    def call(self, key, **kwargs):
        func = self[key]
        params = inspect.getargspec(func)[0]
        args = dict((k, v) for k, v in kwargs.items() if k in params)
        return func(**args)

    def call_without_cut(self, key, **kwargs):
        """Looks up the function and calls it, returning only line and cursor offset"""
        r = self.call_for_two(key, **kwargs)
        return r[:2]

    def __getitem__(self, key):
        if key in self.simple_edits: return self.simple_edits[key]
        if key in self.cut_buffer_edits: return self.cut_buffer_edits[key]
        raise KeyError("key %r not mapped" % (key,))

    def __delitem__(self, key):
        if key in self.simple_edits: del self.simple_edits[key]
        elif key in self.cut_buffer_edits: del self.cut_buffer_edits[key]
        else: raise KeyError("key %r not mapped" % (key,))

class UnconfiguredEdits(AbstractEdits):
    """Maps key to edit functions, and bins them by what parameters they take.

    Only functions with specific signatures can be added:
        * func(**kwargs) -> cursor_offset, line
        * func(**kwargs) -> cursor_offset, line, cut_buffer
        where kwargs are in among the keys of Edits.default_kwargs
    These functions will be run to determine their return type, so no side effects!

    More concrete Edits instances can be created by applying a config with
    Edits.mapping_with_config() - this creates a new Edits instance
    that uses a config file to assign config_attr bindings.

    Keys can't be added twice, config attributes can't be added twice.
    """

    def __init__(self):
        self.simple_edits = {}
        self.cut_buffer_edits = {}
        self.awaiting_config = {}

    def mapping_with_config(self, config, key_dispatch):
        """Creates a new mapping object by applying a config object"""
        return ConfiguredEdits(self.simple_edits, self.cut_buffer_edits,
                               self.awaiting_config, config, key_dispatch)

    def on(self, key=None, config=None):
        if (key is None and config is None or
            key is not None and config is not None):
            raise ValueError("Must use exactly one of key, config")
        if key is not None:
            def add_to_keybinds(func):
                self.add(key, func)
                return func
            return add_to_keybinds
        else:
            def add_to_config(func):
                self.add_config_attr(config, func)
                return func
            return add_to_config

class ConfiguredEdits(AbstractEdits):
    def __init__(self, simple_edits, cut_buffer_edits, awaiting_config, config, key_dispatch):
        self.simple_edits = dict(simple_edits)
        self.cut_buffer_edits = dict(cut_buffer_edits)
        for attr, func in awaiting_config.items():
            for key in key_dispatch[getattr(config, attr)]:
                super(ConfiguredEdits, self).add(key, func, overwrite=True)

    def add_config_attr(self, config_attr, func):
        raise NotImplementedError("Config already set on this mapping")

    def add(self, key, func):
        raise NotImplementedError("Config already set on this mapping")

edit_keys = UnconfiguredEdits()

# Because the edits.on decorator runs the functions, functions which depend
# on other functions must be declared after their dependencies

def kills_behind(func):
    func.kills = 'behind'
    return func

def kills_ahead(func):
    func.kills = 'ahead'
    return func

@edit_keys.on('<Ctrl-b>')
@edit_keys.on('<LEFT>')
def left_arrow(cursor_offset, line):
    return max(0, cursor_offset - 1), line

@edit_keys.on('<Ctrl-f>')
@edit_keys.on('<RIGHT>')
def right_arrow(cursor_offset, line):
    return min(len(line), cursor_offset + 1), line

@edit_keys.on('<Ctrl-a>')
@edit_keys.on('<HOME>')
def beginning_of_line(cursor_offset, line):
    return 0, line

@edit_keys.on('<Ctrl-e>')
@edit_keys.on('<END>')
def end_of_line(cursor_offset, line):
    return len(line), line

@edit_keys.on('<Esc+f>')
@edit_keys.on('<Ctrl-RIGHT>')
@edit_keys.on('<Esc+RIGHT>')
def forward_word(cursor_offset, line):
    patt = r"\S\s"
    match = re.search(patt, line[cursor_offset:]+' ')
    delta = match.end() - 1 if match else 0
    return (cursor_offset + delta, line)

def last_word_pos(string):
    """returns the start index of the last word of given string"""
    patt = r'\S\s'
    match = re.search(patt, string[::-1])
    index = match and len(string) - match.end() + 1
    return index or 0

@edit_keys.on('<Esc+b>')
@edit_keys.on('<Ctrl-LEFT>')
@edit_keys.on('<Esc+LEFT>')
def back_word(cursor_offset, line):
    return (last_word_pos(line[:cursor_offset]), line)

@edit_keys.on('<PADDELETE>')
def delete(cursor_offset, line):
    return (cursor_offset,
            line[:cursor_offset] + line[cursor_offset+1:])

@edit_keys.on('<Ctrl-h>')
@edit_keys.on('<BACKSPACE>')
@edit_keys.on(config='delete_key')
def backspace(cursor_offset, line):
    if cursor_offset == 0:
        return cursor_offset, line
    if not line[:cursor_offset].strip(): #if just whitespace left of cursor
        #front_white = len(line[:cursor_offset]) - len(line[:cursor_offset].lstrip())
        to_delete = ((cursor_offset - 1) % INDENT) + 1
        return cursor_offset - to_delete, line[:cursor_offset - to_delete] + line[cursor_offset:]
    return (cursor_offset - 1,
            line[:cursor_offset - 1] + line[cursor_offset:])

@edit_keys.on('<Ctrl-u>')
@edit_keys.on(config='clear_line_key')
def delete_from_cursor_back(cursor_offset, line):
    return 0, line[cursor_offset:]

@edit_keys.on('<Esc+d>') # option-d
@kills_ahead
def delete_rest_of_word(cursor_offset, line):
    m = re.search(r'\w\b', line[cursor_offset:])
    if not m:
        return cursor_offset, line, ''
    return (cursor_offset, line[:cursor_offset] + line[m.start()+cursor_offset+1:],
            line[cursor_offset:m.start()+cursor_offset+1])

@edit_keys.on('<Ctrl-w>')
@edit_keys.on(config='clear_word_key')
@kills_behind
def delete_word_to_cursor(cursor_offset, line):
    matches = list(re.finditer(r'\s\S', line[:cursor_offset]))
    start = matches[-1].start()+1 if matches else 0
    return start, line[:start] + line[cursor_offset:], line[start:cursor_offset]

@edit_keys.on('<Esc+y>')
def yank_prev_prev_killed_text(cursor_offset, line, cut_buffer): #TODO not implemented - just prev
    return cursor_offset+len(cut_buffer), line[:cursor_offset] + cut_buffer + line[cursor_offset:]

@edit_keys.on(config='yank_from_buffer_key')
def yank_prev_killed_text(cursor_offset, line, cut_buffer):
    return cursor_offset+len(cut_buffer), line[:cursor_offset] + cut_buffer + line[cursor_offset:]

@edit_keys.on('<Ctrl-t>')
def transpose_character_before_cursor(cursor_offset, line):
    return (min(len(line), cursor_offset + 1),
            line[:cursor_offset-1] +
            (line[cursor_offset] if len(line) > cursor_offset else '') +
            line[cursor_offset - 1] +
            line[cursor_offset+1:])

@edit_keys.on('<Esc+t>')
def transpose_word_before_cursor(cursor_offset, line):
    return cursor_offset, line #TODO Not implemented

# bonus functions (not part of readline)

@edit_keys.on('<Esc+r>')
def delete_line(cursor_offset, line):
    return 0, ""

@edit_keys.on('<Esc+u>')
def uppercase_next_word(cursor_offset, line):
    return cursor_offset, line #TODO Not implemented

@edit_keys.on('<Ctrl-k>')
@kills_ahead
def delete_from_cursor_forward(cursor_offset, line):
    return cursor_offset, line[:cursor_offset], line[cursor_offset:]

@edit_keys.on('<Esc+c>')
def titlecase_next_word(cursor_offset, line):
    return cursor_offset, line #TODO Not implemented

@edit_keys.on('<Esc+BACKSPACE>')
@edit_keys.on('<Meta-BACKSPACE>')
@kills_behind
def delete_word_from_cursor_back(cursor_offset, line):
    """Whatever my option-delete does in bash on my mac"""
    if not line:
        return cursor_offset, line, ''
    starts = [m.start() for m in list(re.finditer(r'\b\w', line)) if m.start() < cursor_offset]
    if starts:
        return starts[-1], line[:starts[-1]] + line[cursor_offset:], line[starts[-1]:cursor_offset]
    return cursor_offset, line, ''


