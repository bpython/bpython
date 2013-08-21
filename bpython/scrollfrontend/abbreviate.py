ABBR = {
        'improt' : 'import',
        'imprt'  : 'import',
        'impotr' : 'import',
        'form'   : 'from',
        }

import re

def substitute_abbreviations(cursor_offset, line):
    """This should be much better"""
    new_line = ''.join([ABBR.get(word, word) for word in re.split(r'(\w+)', line)])
    cursor_offset = cursor_offset + len(new_line) - len(line)
    return cursor_offset, new_line

if __name__ == '__main__':
    print(substitute_abbreviations(0, 'improt asdf'))
    print(substitute_abbreviations(0, 'foo(x, y() - 2.3242) + "asdf"'))
