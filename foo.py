# coding: utf-8

# The MIT License
#
# Copyright (c) 2009-2015 the bpython authors.
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
#

from __future__ import unicode_literals

import __main__
import abc
import glob
import keyword
import os
import re
import rlcompleter
import sys
from six.moves import range, builtins
from six import string_types, iteritems

from bpython import inspection
from bpython import importcompletion
from bpython import line as lineparts
from bpython.line import LinePart
from bpython._py3compat import py3, try_decode
from bpython.lazyre import LazyReCompile

if not py3:
    from types import InstanceType, ClassType


# Autocomplete modes
SIMPLE = 'simple'
SUBSTRING = 'substring'
FUZZY = 'fuzzy'

ALL_MODES = (SIMPLE, SUBSTRING, FUZZY)

MAGIC_METHODS = tuple("__%s__" % s for s in (
    "init", "repr", "str", "lt", "le", "eq", "ne", "gt", "ge", "cmp", "hash",
    "nonzero", "unicode", "getattr", "setattr", "get", "set", "call", "len",
    "getitem", "setitem", "iter", "reversed", "contains", "add", "sub", "mul",
    "floordiv", "mod", "divmod", "pow", "lshift", "rshift", "and", "xor", "or",
    "div", "truediv", "neg", "pos", "abs", "invert", "complex", "int", "float",
    "oct", "hex", "index", "coerce", "enter", "exit"))

if py3:
    KEYWORDS = frozenset(keyword.kwlist)
else:
    KEYWORDS = frozenset(name.decode('ascii') for name in keyword.kwlist)


def after_last_dot(name):
    return name.rstrip('.').rsplit('.')[-1]


def method_match_simple(word, size, text):
    return word[:size] == text


def method_match_substring(word, size, text):
    return text in word


def method_match_fuzzy(word, size, text):
    s = r'.*%s.*' % '.*'.join(list(text))
    return re.search(s, word)


MODES_MAP = {
    SIMPLE: method_match_simple,
    SUBSTRING: method_match_substring,
    FUZZY: method_match_fuzzy
}


class BaseCompletionType(object):
    """Describes different completion types"""

    def __init__(self, shown_before_tab=True, mode=SIMPLE):
        self._shown_before_tab = shown_before_tab
        self.method_match = MODES_MAP[mode]

    def matches(self, cursor_offset, line, **kwargs):
        """Returns a list of possible matches given a line and cursor, or None
        if this completion type isn't applicable.

        ie, import completion doesn't make sense if there cursor isn't after
        an import or from statement, so it ought to return None.

        Completion types are used to:
            * `locate(cur, line)` their initial target word to replace given a
              line and cursor
            * find `matches(cur, line)` that might replace that word
            * `format(match)` matches to be displayed to the user
            * determine whether suggestions should be `shown_before_tab`
            * `substitute(cur, line, match)` in a match for what's found with
              `target`
            """
        raise NotImplementedError

    def locate(self, cursor_offset, line):
        """Returns a start, stop, and word given a line and cursor, or None
        if no target for this type of completion is found under the cursor"""
        raise NotImplementedError

    def format(self, word):
        return word

    def substitute(self, cursor_offset, line, match):
        """Returns a cursor offset and line with match swapped in"""
        lpart = self.locate(cursor_offset, line)
        offset = lpart.start + len(match)
        changed_line = line[:lpart.start] + match + line[lpart.end:]
        return offset, changed_line

    @property
    def shown_before_tab(self):
        """Whether suggestions should be shown before the user hits tab, or only
        once that has happened."""
        return self._shown_before_tab


class CumulativeCompleter(BaseCompletionType):
    """Returns combined matches from several completers"""

    def __init__(self, completers, mode=SIMPLE):
        if not completers:
            raise ValueError(
                "CumulativeCompleter requires at least one completer")
        self._completers = completers

        super(CumulativeCompleter, self).__init__(True, mode)

    def locate(self, current_offset, line):
        return self._completers[0].locate(current_offset, line)

    def format(self, word):
        return self._completers[0].format(word)

    def matches(self, cursor_offset, line, **kwargs):
        all_matches = set()
        for completer in self._completers:
            # these have to be explicitely listed to deal with the different
            # signatures of various matches() methods of completers
            matches = completer.matches(cursor_offset=cursor_offset,
                                        line=line,
                                        **kwargs)
            if matches is not None:
                all_matches.update(matches)

        return all_matches


class ImportCompletion(BaseCompletionType):

    def matches(self, cursor_offset, line, **kwargs):
        return importcompletion.complete(cursor_offset, line)

    def locate(self, current_offset, line):
        return lineparts.current_word(current_offset, line)

    def format(self, word):
        return after_last_dot(word)


class FilenameCompletion(BaseCompletionType):

    def __init__(self, mode=SIMPLE):
        super(FilenameCompletion, self).__init__(False, mode)

    if sys.version_info[:2] >= (3, 4):
        def safe_glob(self, pathname):
            return glob.iglob(glob.escape(pathname) + '*')
    else:
        def safe_glob(self, pathname):
            try:
                return glob.glob(pathname + '*')
            except re.error:
                # see #491
                return tuple()

    def matches(self, cursor_offset, line, **kwargs):
        cs = lineparts.current_string(cursor_offset, line)
        if cs is None:
            return None
        matches = set()
        username = cs.word.split(os.path.sep, 1)[0]
        user_dir = os.path.expanduser(username)
        for filename in self.safe_glob(os.path.expanduser(cs.word)):
            if os.path.isdir(filename):
                filename += os.path.sep
            if cs.word.startswith('~'):
                filename = username + filename[len(user_dir):]
            matches.add(filename)
        return matches

    def locate(self, current_offset, line):
        return lineparts.current_string(current_offset, line)

    def format(self, filename):
        filename.rstrip(os.sep).rsplit(os.sep)[-1]
        if os.sep in filename[:-1]:
            return filename[filename.rindex(os.sep, 0, -1)+1:]
        else:
            return filename


class AttrCompletion(BaseCompletionType):

    attr_matches_re = LazyReCompile(r"(\w+(\.\w+)*)\.(\w*)")

    def matches(self, cursor_offset, line, **kwargs):
        if 'locals_' not in kwargs:
            return None
        locals_ = kwargs['locals_']

        r = self.locate(cursor_offset, line)
        if r is None:
            return None

        if locals_ is None:
            locals_ = __main__.__dict__

        assert '.' in r.word

        for i in range(1, len(r.word) + 1):
            if r.word[-i] == '[':
                i -= 1
                break
        methodtext = r.word[-i:]
        matches = set(''.join([r.word[:-i], m])
                      for m in self.attr_matches(methodtext, locals_))

        # TODO add open paren for methods via _callable_prefix (or decide not
        # to) unless the first character is a _ filter out all attributes
        # starting with a _
        if r.word.split('.')[-1].startswith('__'):
            pass
        elif r.word.split('.')[-1].startswith('_'):
            matches = set(match for match in matches
                          if not match.split('.')[-1].startswith('__'))
        else:
            matches = set(match for match in matches
                          if not match.split('.')[-1].startswith('_'))
        return matches

    def locate(self, current_offset, line):
        return lineparts.current_dotted_attribute(current_offset, line)

    def format(self, word):
        return after_last_dot(word)

    def attr_matches(self, text, namespace):
        """Taken from rlcompleter.py and bent to my will.
        """

        # Gna, Py 2.6's rlcompleter searches for __call__ inside the
        # instance instead of the type, so we monkeypatch to prevent
        # side-effects (__getattr__/__getattribute__)
        m = self.attr_matches_re.match(text)
        if not m:
            return []

        expr, attr = m.group(1, 3)
        if expr.isdigit():
            # Special case: float literal, using attrs here will result in
            # a SyntaxError
            return []
        try:
            obj = safe_eval(expr, namespace)
        except EvaluationError:
            return []
        with inspection.AttrCleaner(obj):
            matches = self.attr_lookup(obj, expr, attr)
        return matches

    def attr_lookup(self, obj, expr, attr):
        """Second half of original attr_matches method factored out so it can
        be wrapped in a safe try/finally block in case anything bad happens to
        restore the original __getattribute__ method."""
        words = self.list_attributes(obj)
        if hasattr(obj, '__class__'):
            words.append('__class__')
            words = words + rlcompleter.get_class_members(obj.__class__)
            if not isinstance(obj.__class__, abc.ABCMeta):
                try:
                    words.remove('__abstractmethods__')
                except ValueError:
                    pass

        if not py3 and isinstance(obj, (InstanceType, ClassType)):
            # Account for the __dict__ in an old-style class.
            words.append('__dict__')

        matches = []
        n = len(attr)
        for word in words:
            if self.method_match(word, n, attr) and word != "__builtins__":
                matches.append("%s.%s" % (expr, word))
        return matches

    if py3:
        def list_attributes(self, obj):
            return dir(obj)
    else:
        def list_attributes(self, obj):
            if isinstance(obj, InstanceType):
                try:
                    return dir(obj)
                except Exception:
                    # This is a case where we can not prevent user code from
                    # running. We return a default list attributes on error
                    # instead. (#536)
                    return ['__doc__', '__module__']
            else:
                return dir(obj)


class ArrayItemMembersCompletion(BaseCompletionType):

    def matches(self, cursor_offset, line, **kwargs):
        if 'locals_' not in kwargs:
            return None
        locals_ = kwargs['locals_']

        r = self.locate(cursor_offset, line)
        if r is None:
            return None
        _, _, dexpr = lineparts.current_array_with_indexer(cursor_offset, line)
        try:
            obj = safe_eval(dexpr, locals_)  # TODO
            # obj = eval(dexpr)
        except EvaluationError:
            return set()

        attrs = dir('')
        if not py3:
            # decode attributes
            attrs = (att.decode('ascii') for att in attrs)

        matches = set(att for att in attrs if att.startswith(r.word))
        if not r.word.startswith('_'):
            return set(match for match in matches if not match.startswith('_'))
        return matches

    def locate(self, current_offset, line):
        return lineparts.current_array_item_member_name(current_offset, line)

    def format(self, match):
        return match[:-1]


class DictKeyCompletion(BaseCompletionType):

    def matches(self, cursor_offset, line, **kwargs):
        if 'locals_' not in kwargs:
            return None
        locals_ = kwargs['locals_']

        r = self.locate(cursor_offset, line)
        if r is None:
            return None
        _, _, dexpr = lineparts.current_dict(cursor_offset, line)
        try:
            obj = safe_eval(dexpr, locals_)
        except EvaluationError:
            return set()
        if isinstance(obj, dict) and obj.keys():
            return set("{0!r}]".format(k) for k in obj.keys()
                       if repr(k).startswith(r.word))
        else:
            return set()

    def locate(self, current_offset, line):
        return lineparts.current_dict_key(current_offset, line)

    def format(self, match):
        return match[:-1]


class MagicMethodCompletion(BaseCompletionType):

    def matches(self, cursor_offset, line, **kwargs):
        if 'current_block' not in kwargs:
            return None
        current_block = kwargs['current_block']

        r = self.locate(cursor_offset, line)
        if r is None:
            return None
        if 'class' not in current_block:
            return None
        return set(name for name in MAGIC_METHODS if name.startswith(r.word))

    def locate(self, current_offset, line):
        return lineparts.current_method_definition_name(current_offset, line)


class GlobalCompletion(BaseCompletionType):

    def matches(self, cursor_offset, line, **kwargs):
        """Compute matches when text is a simple name.
        Return a list of all keywords, built-in functions and names currently
        defined in self.namespace that match.
        """
        if 'locals_' not in kwargs:
            return None
        locals_ = kwargs['locals_']

        r = self.locate(cursor_offset, line)
        if r is None:
            return None

        matches = set()
        n = len(r.word)
        for word in KEYWORDS:
            if self.method_match(word, n, r.word):
                matches.add(word)
        for nspace in (builtins.__dict__, locals_):
            for word, val in iteritems(nspace):
                word = try_decode(word, 'ascii')
                # if identifier isn't ascii, don't complete (syntax error)
                if word is None:
                    continue
                if (self.method_match(word, n, r.word) and
                        word != "__builtins__"):
                    matches.add(_callable_postfix(val, word))
        return matches

    def locate(self, current_offset, line):
        return lineparts.current_single_word(current_offset, line)


class ParameterNameCompletion(BaseCompletionType):

    def matches(self, cursor_offset, line, **kwargs):
        if 'argspec' not in kwargs:
            return None
        argspec = kwargs['argspec']

        if not argspec:
            return None
        r = self.locate(cursor_offset, line)
        if r is None:
            return None
        if argspec:
            matches = set(name + '=' for name in argspec[1][0]
                          if isinstance(name, string_types) and
                          name.startswith(r.word))
            if py3:
                matches.update(name + '=' for name in argspec[1][4]
                               if name.startswith(r.word))
        return matches

    def locate(self, current_offset, line):
        return lineparts.current_word(current_offset, line)


class StringLiteralAttrCompletion(BaseCompletionType):

    @staticmethod
    def complete_string(cursor_offset, line, r):
        attrs = dir('')
        if not py3:
            # decode attributes
            attrs = (att.decode('ascii') for att in attrs)

        matches = set(att for att in attrs if att.startswith(r.word))
        if not r.word.startswith('_'):
            return set(match for match in matches if not match.startswith('_'))
        return matches

    def matches(self, cursor_offset, line, **kwargs):
        r = self.locate(cursor_offset, line)
        if r is None:
            return None

        return StringLiteralAttrCompletion.complete_string(cursor_offset, line, r)

    def locate(self, current_offset, line):
        return lineparts.current_string_literal_attr(current_offset, line)


try:
    import jedi
except ImportError:
    class MultilineJediCompletion(BaseCompletionType):
        def matches(self, cursor_offset, line, **kwargs):
            return None
else:
    class JediCompletion(BaseCompletionType):

        def matches(self, cursor_offset, line, **kwargs):
            if 'history' not in kwargs:
                return None
            history = kwargs['history']

            if not lineparts.current_word(cursor_offset, line):
                return None
            history = '\n'.join(history) + '\n' + line

            try:
                script = jedi.Script(history, len(history.splitlines()),
                                     cursor_offset, 'fake.py')
                completions = script.completions()
            except (jedi.NotFoundError, IndexError, KeyError):
                # IndexError for #483
                # KeyError for #544
                self._orig_start = None
                return None

            if completions:
                diff = len(completions[0].name) - len(completions[0].complete)
                self._orig_start = cursor_offset - diff
            else:
                self._orig_start = None
                return None

            first_letter = line[self._orig_start:self._orig_start+1]

            matches = [c.name for c in completions]
            if any(not m.lower().startswith(matches[0][0].lower())
                   for m in matches):
                # Too general - giving completions starting with multiple
                # letters
                return None
            else:
                # case-sensitive matches only
                return set(m for m in matches if m.startswith(first_letter))

        def locate(self, cursor_offset, line):
            start = self._orig_start
            end = cursor_offset
            return LinePart(start, end, line[start:end])

    class MultilineJediCompletion(JediCompletion):
        def matches(self, cursor_offset, line, **kwargs):
            if 'current_block' not in kwargs or 'history' not in kwargs:
                return None
            current_block = kwargs['current_block']
            history = kwargs['history']

            if '\n' in current_block:
                assert cursor_offset <= len(line), "%r %r" % (cursor_offset,
                                                              line)
                results = super(MultilineJediCompletion,
                                self).matches(cursor_offset, line,
                                              history=history)
                return results
            else:
                return None


def get_completer(completers, cursor_offset, line, **kwargs):
    """Returns a list of matches and an applicable completer

    If no matches available, returns a tuple of an empty list and None

    cursor_offset is the current cursor column
    line is a string of the current line
    kwargs (all optional):
        locals_ is a dictionary of the environment
        argspec is an inspect.ArgSpec instance for the current function where
            the cursor is
        current_block is the possibly multiline not-yet-evaluated block of
            code which the current line is part of
        complete_magic_methods is a bool of whether we ought to complete
            double underscore methods like __len__ in method signatures
    """

    for completer in completers:
        matches = completer.matches(cursor_offset, line, **kwargs)
        if matches is not None:
            return sorted(matches), (completer if matches else None)
    return [], None


def get_default_completer(mode=SIMPLE):
    return (
        DictKeyCompletion(mode=mode),
        StringLiteralAttrCompletion(mode=mode),
        ImportCompletion(mode=mode),
        FilenameCompletion(mode=mode),
        MagicMethodCompletion(mode=mode),
        MultilineJediCompletion(mode=mode),
        GlobalCompletion(mode=mode),
        ArrayItemMembersCompletion(mode=mode),
        CumulativeCompleter((AttrCompletion(mode=mode),
                             ParameterNameCompletion(mode=mode)),
                            mode=mode)
    )


def get_completer_bpython(cursor_offset, line, **kwargs):
    """"""
    return get_completer(get_default_completer(),
                         cursor_offset, line, **kwargs)


class EvaluationError(Exception):
    """Raised if an exception occurred in safe_eval."""


def safe_eval(expr, namespace):
    """Not all that safe, just catches some errors"""
    try:
        return eval(expr, namespace)
    except (NameError, AttributeError, SyntaxError):
        # If debugging safe_eval, raise this!
        # raise
        raise EvaluationError


def _callable_postfix(value, word):
    """rlcompleter's _callable_postfix done right."""
    with inspection.AttrCleaner(value):
        if inspection.is_callable(value):
            word += '('
    return word
