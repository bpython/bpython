# The MIT License
#
# Copyright (c) 2009 Andreas Stuehrk
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import imp
import os
import sys


# The cached list of all known modules
modules = set()
fully_loaded = False


def complete(line, cw):
    """Construct a full list of possibly completions for imports."""
    if not cw:
        return None

    tokens = line.split()
    if tokens[0] not in ['from', 'import']:
        return None

    completing_from = False
    if tokens[0] == 'from':
        if len(tokens) > 3:
            if '.' in cw:
                # This will result in a SyntaxError, so do not return
                # any matches
                return None
            completing_from = True
            cw = '%s.%s' % (tokens[1], cw)
        elif len(tokens) == 3:
            return ['import']

    matches = list()
    for name in modules:
        if not (name.startswith(cw) and name.find('.', len(cw)) == -1):
            continue
        if completing_from:
            name = name[len(tokens[1]) + 1:]
        matches.append(name)
    if not matches:
        return []
    return matches


def find_modules(path):
    """Find all modules (and packages) for a given directory."""
    if not os.path.isdir(path):
        # Perhaps a zip file
        return

    for name in os.listdir(path):
        if not any(name.endswith(suffix[0]) for suffix in imp.get_suffixes()):
            # Possibly a package
            if '.' in name:
                continue
        name = os.path.splitext(name)[0]
        try:
            fo, pathname, _ = imp.find_module(name, [path])
        except (ImportError, SyntaxError):
            continue
        else:
            if fo is not None:
                fo.close()
            else:
                # Yay, package
                for subname in find_modules(pathname):
                    if subname != '__init__':
                        yield '%s.%s' % (name, subname)
            yield name


def find_all_modules(path=None):
    """Return a list with all modules in `path`, which should be a list of
    directory names. If path is not given, sys.path will be used."""
    if path is None:
        modules.update(sys.builtin_module_names)
        path = sys.path

    for p in path:
        for module in find_modules(p):
            modules.add(module)
            yield


def find_coroutine():
    global fully_loaded

    if fully_loaded:
        return None

    try:
        find_iterator.next()
    except StopIteration:
        fully_loaded = True

    return True


def reload():
    """Refresh the list of known modules."""
    modules.clear()
    for _ in find_all_modules():
        pass

find_iterator = find_all_modules()
