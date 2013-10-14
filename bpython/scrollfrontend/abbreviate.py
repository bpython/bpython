import os
from subprocess import Popen
import tempfile
import shutil
import re

ABBR = {
        'improt' : 'import',
        'imprt'  : 'import',
        'impotr' : 'import',
        'form'   : 'from',
        }

def substitute_abbreviations(cursor_offset, line):
    """This should be much better"""
    new_line = ''.join([ABBR.get(word, word) for word in re.split(r'(\w+)', line)])
    cursor_offset = cursor_offset + len(new_line) - len(line)
    return cursor_offset, new_line


def python_vim_abbreviations():
    fn = tempfile.mkdtemp()
    mock_python_filename = os.path.join(fn, 'python.py')
    abbreviations_filename = os.path.join(fn, 'abbrs')

    p = Popen(['vim', '-c', 'redir > %s|abbreviate|redir END|q' % abbreviations_filename, mock_python_filename])
    p.communicate()
    s = open(abbreviations_filename).read()
    shutil.rmtree(fn)

    def clean_line(line):
        m = re.search(r'[!]\W*(\w+)\W*[@]?(\w+)\W*', line)
        return m.groups()

    return dict([clean_line(line) for line in s.split('\n') if line.strip()])

def update_abbrs_with_vim_abbrs():
    abbrs = python_vim_abbreviations()
    ABBR.update(abbrs)

