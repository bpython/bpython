# The MIT License
#
# Copyright (c) 2009-2011 Andreas Stuehrk
# Copyright (c) 2020-2021 Sebastian Ramacher
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
import importlib.machinery
import sys
import warnings
from pathlib import Path

from .line import (
    current_word,
    current_import,
    current_from_import_from,
    current_from_import_import,
)

SUFFIXES = importlib.machinery.all_suffixes()
LOADERS = (
    (
        importlib.machinery.ExtensionFileLoader,
        importlib.machinery.EXTENSION_SUFFIXES,
    ),
    (
        importlib.machinery.SourceFileLoader,
        importlib.machinery.SOURCE_SUFFIXES,
    ),
)


class ModuleGatherer:
    def __init__(self, path=None, skiplist=None):
        # The cached list of all known modules
        self.modules = set()
        # List of (st_dev, st_ino) to compare against so that paths are not repeated
        self.paths = set()
        # Patterns to skip
        self.skiplist = skiplist if skiplist is not None else tuple()
        self.fully_loaded = False
        self.find_iterator = self.find_all_modules(path)

    def module_matches(self, cw, prefix=""):
        """Modules names to replace cw with"""

        full = f"{prefix}.{cw}" if prefix else cw
        matches = (
            name
            for name in self.modules
            if (name.startswith(full) and name.find(".", len(full)) == -1)
        )
        if prefix:
            return {match[len(prefix) + 1 :] for match in matches}
        else:
            return set(matches)

    def attr_matches(self, cw, prefix="", only_modules=False):
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

    def module_attr_matches(self, name):
        """Only attributes which are modules to replace name with"""
        return self.attr_matches(name, prefix="", only_modules=True)

    def complete(self, cursor_offset, line):
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
                matches = self.module_matches(
                    import_import[2], from_import_from[2]
                )
                matches.update(
                    self.attr_matches(import_import[2], from_import_from[2])
                )
            else:
                # `from <a|>` completion
                matches = self.module_attr_matches(from_import_from[2])
                matches.update(self.module_matches(from_import_from[2]))
            return matches

        cur_import = current_import(cursor_offset, line)
        if cur_import is not None:
            # `import <a|>` completion
            matches = self.module_matches(cur_import[2])
            matches.update(self.module_attr_matches(cur_import[2]))
            return matches
        else:
            return None

    def find_modules(self, path):
        """Find all modules (and packages) for a given directory."""
        if not path.is_dir():
            # Perhaps a zip file
            return
        if any(fnmatch.fnmatch(path.name, entry) for entry in self.skiplist):
            # Path is on skiplist
            return

        try:
            # https://bugs.python.org/issue34541
            # Once we migrate to Python 3.8, we can change it back to directly iterator over
            # path.iterdir().
            children = tuple(path.iterdir())
        except OSError:
            # Path is not readable
            return

        finder = importlib.machinery.FileFinder(str(path), *LOADERS)
        for p in children:
            if any(fnmatch.fnmatch(p.name, entry) for entry in self.skiplist):
                # Path is on skiplist
                continue
            elif not any(p.name.endswith(suffix) for suffix in SUFFIXES):
                # Possibly a package
                if "." in p.name:
                    continue
            elif p.is_dir():
                # Unfortunately, CPython just crashes if there is a directory
                # which ends with a python extension, so work around.
                continue
            name = p.name
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
                    path_real = Path(pathname).resolve()
                    stat = path_real.stat()
                    if (stat.st_dev, stat.st_ino) not in self.paths:
                        self.paths.add((stat.st_dev, stat.st_ino))
                        for subname in self.find_modules(path_real):
                            if subname != "__init__":
                                yield f"{name}.{subname}"
                yield name

    def find_all_modules(self, path=None):
        """Return a list with all modules in `path`, which should be a list of
        directory names. If path is not given, sys.path will be used."""

        if path is None:
            self.modules.update(sys.builtin_module_names)
            path = sys.path

        for p in path:
            p = Path(p).resolve() if p else Path.cwd()
            for module in self.find_modules(p):
                self.modules.add(module)
                yield

    def find_coroutine(self):
        if self.fully_loaded:
            return None

        try:
            next(self.find_iterator)
        except StopIteration:
            self.fully_loaded = True

        return True
