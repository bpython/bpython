# The MIT License
#
# Copyright (c) 2009-2011 Andreas Stuehrk
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

from __future__ import with_statement

from bpython import line as lineparts
import imp
import os
import sys
import warnings
try:
    from warnings import catch_warnings
except ImportError:
    import contextlib
    @contextlib.contextmanager
    def catch_warnings():
        """Stripped-down version of `warnings.catch_warnings()`
        (available in Py >= 2.6)."""
        filters = warnings.filters
        warnings.filters = list(filters)
        try:
            yield
        finally:
            warnings.filters = filters

from bpython._py3compat import py3

# The cached list of all known modules
modules = set()
fully_loaded = False


def complete(cursor_offset, line):
    """Construct a full list of possibly completions for imports."""
    # TODO if this is done in a thread (as it prob will be in Windows) we'll need this
    # if not fully_loaded:
    #     return []
    tokens = line.split()
    if 'from' not in tokens and 'import' not in tokens:
        return None

    result = lineparts.current_word(cursor_offset, line)
    if result is None:
        return None

    def module_matches(cw, prefix=''):
        """Modules names to replace cw with"""
        full = '%s.%s' % (prefix, cw) if prefix else cw
        matches = [name for name in modules
                   if (name.startswith(full) and
                       name.find('.', len(full)) == -1)]
        if prefix:
            return [match[len(prefix)+1:] for match in matches]
        else:
            return matches

    def attr_matches(cw, prefix='', only_modules=False):
        """Attributes to replace name with"""
        full = '%s.%s' % (prefix, cw) if prefix else cw
        module_name, _, name_after_dot = full.rpartition('.')
        if module_name not in sys.modules:
            return []
        module = sys.modules[module_name]
        if only_modules:
            matches = [name for name in dir(module)
                    if name.startswith(name_after_dot) and
                    '%s.%s' % (module_name, name) in sys.modules]
        else:
            matches = [name for name in dir(module) if name.startswith(name_after_dot)]
        module_part, _, _ = cw.rpartition('.')
        if module_part:
            return ['%s.%s' % (module_part, m) for m in matches]
        return matches

    def module_attr_matches(name):
        """Only attributes which are modules to replace name with"""
        return attr_matches(name, prefix='', only_modules=True)

    if lineparts.current_from_import_from(cursor_offset, line) is not None:
        if lineparts.current_from_import_import(cursor_offset, line) is not None:
            # `from a import <b|>` completion
            return (module_matches(lineparts.current_from_import_import(cursor_offset, line)[2],
                                   lineparts.current_from_import_from(cursor_offset, line)[2]) +
                    attr_matches(lineparts.current_from_import_import(cursor_offset, line)[2],
                                 lineparts.current_from_import_from(cursor_offset, line)[2]))
        else:
            # `from <a|>` completion
            return (module_attr_matches(lineparts.current_from_import_from(cursor_offset, line)[2]) +
                    module_matches(lineparts.current_from_import_from(cursor_offset, line)[2]))
    elif lineparts.current_import(cursor_offset, line):
        # `import <a|>` completion
        return (module_matches(lineparts.current_import(cursor_offset, line)[2]) +
                module_attr_matches(lineparts.current_import(cursor_offset, line)[2]))
    else:
        return None

def find_modules(path):
    """Find all modules (and packages) for a given directory."""
    if not os.path.isdir(path):
        # Perhaps a zip file
        return

    try:
        filenames = os.listdir(path)
    except EnvironmentError:
        filenames = []
    for name in filenames:
        if not any(name.endswith(suffix[0]) for suffix in imp.get_suffixes()):
            # Possibly a package
            if '.' in name:
                continue
        elif os.path.isdir(os.path.join(path, name)):
            # Unfortunately, CPython just crashes if there is a directory
            # which ends with a python extension, so work around.
            continue
        for suffix in imp.get_suffixes():
            if name.endswith(suffix[0]):
                name = name[:-len(suffix[0])]
                break
        if py3 and name == "badsyntax_pep3120":
            # Workaround for issue #166
            continue
        try:
            with catch_warnings():
                warnings.simplefilter("ignore", ImportWarning)
                fo, pathname, _ = imp.find_module(name, [path])
        except (ImportError, IOError, SyntaxError):
            continue
        except UnicodeEncodeError:
            # Happens with Python 3 when there is a filename in some
            # invalid encoding
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
        if not p:
            p = os.curdir
        for module in find_modules(p):
            if not py3 and not isinstance(module, unicode):
                try:
                    module = module.decode(sys.getfilesystemencoding())
                except UnicodeDecodeError:
                    # Not importable anyway, ignore it
                    continue
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
