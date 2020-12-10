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

import fnmatch
import os
import sys
import warnings
import importlib.machinery

from .line import (
    current_word,
    current_import,
    current_from_import_from,
    current_from_import_import,
)

SUFFIXES = importlib.machinery.all_suffixes()

# The cached list of all known modules
modules = set()
# List of stored paths to compare against so that real paths are not repeated
# handles symlinks not mount points
paths = set()
# Patterns to skip
# TODO: This skiplist should be configurable.
skiplist = (
    # version tracking
    ".git", ".svn", ".hg"
    # XDG
    ".config", ".local", ".share",
    # nodejs
    "node_modules",
    # PlayOnLinux
    "PlayOnLinux's virtual drives",
    # wine
    "dosdevices",
)
fully_loaded = False


def module_matches(cw, prefix=""):
    """Modules names to replace cw with"""
    full = f"{prefix}.{cw}" if prefix else cw
    matches = (
        name
        for name in modules
        if (name.startswith(full) and name.find(".", len(full)) == -1)
    )
    if prefix:
        return {match[len(prefix) + 1 :] for match in matches}
    else:
        return set(matches)


def attr_matches(cw, prefix="", only_modules=False):
    """Attributes to replace name with"""
    full = f"{prefix}.{cw}" if prefix else cw
    module_name, _, name_after_dot = full.rpartition(".")
    if module_name not in sys.modules:
        return set()
    module = sys.modules[module_name]
    if only_modules:
        matches = {
            name
            for name in dir(module)
            if name.startswith(name_after_dot)
            and f"{module_name}.{name}" in sys.modules
        }
    else:
        matches = {
            name for name in dir(module) if name.startswith(name_after_dot)
        }
    module_part, _, _ = cw.rpartition(".")
    if module_part:
        matches = {f"{module_part}.{m}" for m in matches}

    return matches


def module_attr_matches(name):
    """Only attributes which are modules to replace name with"""
    return attr_matches(name, prefix="", only_modules=True)


def complete(cursor_offset, line):
    """Construct a full list of possibly completions for imports."""
    tokens = line.split()
    if "from" not in tokens and "import" not in tokens:
        return None

    result = current_word(cursor_offset, line)
    if result is None:
        return None

    from_import_from = current_from_import_from(cursor_offset, line)
    if from_import_from is not None:
        import_import = current_from_import_import(cursor_offset, line)
        if import_import is not None:
            # `from a import <b|>` completion
            matches = module_matches(import_import[2], from_import_from[2])
            matches.update(attr_matches(import_import[2], from_import_from[2]))
        else:
            # `from <a|>` completion
            matches = module_attr_matches(from_import_from[2])
            matches.update(module_matches(from_import_from[2]))
        return matches

    cur_import = current_import(cursor_offset, line)
    if cur_import is not None:
        # `import <a|>` completion
        matches = module_matches(cur_import[2])
        matches.update(module_attr_matches(cur_import[2]))
        return matches
    else:
        return None


def find_modules(path):
    """Find all modules (and packages) for a given directory."""
    if not os.path.isdir(path):
        # Perhaps a zip file
        return
    basepath = os.path.basename(path)
    if any(fnmatch.fnmatch(basepath, entry) for entry in skiplist):
        # Path is on skiplist
        return

    try:
        filenames = os.listdir(path)
    except OSError:
        filenames = []

    finder = importlib.machinery.FileFinder(path)

    for name in filenames:
        if any(fnmatch.fnmatch(name, entry) for entry in skiplist):
            # Path is on skiplist
            continue
        elif not any(name.endswith(suffix) for suffix in SUFFIXES):
            # Possibly a package
            if "." in name:
                continue
        elif os.path.isdir(os.path.join(path, name)):
            # Unfortunately, CPython just crashes if there is a directory
            # which ends with a python extension, so work around.
            continue
        for suffix in SUFFIXES:
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        if name == "badsyntax_pep3120":
            # Workaround for issue #166
            continue
        try:
            is_package = False
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ImportWarning)
                spec = finder.find_spec(name)
                if spec is None:
                    continue
                if spec.submodule_search_locations is not None:
                    pathname = spec.submodule_search_locations[0]
                    is_package = True
                else:
                    pathname = spec.origin
        except (ImportError, OSError, SyntaxError):
            continue
        except UnicodeEncodeError:
            # Happens with Python 3 when there is a filename in some
            # invalid encoding
            continue
        else:
            if is_package:
                path_real = os.path.realpath(pathname)
                if path_real not in paths:
                    paths.add(path_real)
                    for subname in find_modules(pathname):
                        if subname != "__init__":
                            yield f"{name}.{subname}"
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
            modules.add(module)
            yield


def find_coroutine():
    global fully_loaded

    if fully_loaded:
        return None

    try:
        next(find_iterator)
    except StopIteration:
        fully_loaded = True

    return True


def reload():
    """Refresh the list of known modules."""
    modules.clear()
    for _ in find_all_modules():
        pass


find_iterator = find_all_modules()
