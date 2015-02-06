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

import __main__
import abc
import keyword
import os
import rlcompleter
from six.moves import range, builtins
from six import string_types

from glob import glob

from bpython import inspection
from bpython import importcompletion
from bpython import line as lineparts
from bpython._py3compat import py3
from bpython.lazyre import LazyReCompile


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


def after_last_dot(name):
    return name.rstrip('.').rsplit('.')[-1]


class BaseCompletionType(object):
    """Describes different completion types"""

    def __init__(self, shown_before_tab=True):
        self._shown_before_tab = shown_before_tab

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
        start, end, word = self.locate(cursor_offset, line)
        result = start + len(match), line[:start] + match + line[end:]
        return result

    @property
    def shown_before_tab(self):
        """Whether suggestions should be shown before the user hits tab, or only
        once that has happened."""
        return self._shown_before_tab


class CumulativeCompleter(BaseCompletionType):
    """Returns combined matches from several completers"""

    def __init__(self, completers):
        if not completers:
            raise ValueError(
                "CumulativeCompleter requires at least one completer")
        self._completers = completers

        super(CumulativeCompleter, self).__init__(True)

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

    def __init__(self):
        super(FilenameCompletion, self).__init__(False)

    def matches(self, cursor_offset, line, **kwargs):
        cs = lineparts.current_string(cursor_offset, line)
        if cs is None:
            return None
        start, end, text = cs
        matches = set()
        username = text.split(os.path.sep, 1)[0]
        user_dir = os.path.expanduser(username)
        for filename in glob(os.path.expanduser(text + '*')):
            if os.path.isdir(filename):
                filename += os.path.sep
            if text.startswith('~'):
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

    def matches(self, cursor_offset, line, **kwargs):
        if 'locals_' not in kwargs:
            return None
        locals_ = kwargs['locals_']

        r = self.locate(cursor_offset, line)
        if r is None:
            return None
        text = r[2]

        if locals_ is None:
            locals_ = __main__.__dict__

        assert '.' in text

        for i in range(1, len(text) + 1):
            if text[-i] == '[':
                i -= 1
                break
        methodtext = text[-i:]
        matches = set(''.join([text[:-i], m])
                      for m in attr_matches(methodtext, locals_))

        # TODO add open paren for methods via _callable_prefix (or decide not
        # to) unless the first character is a _ filter out all attributes
        # starting with a _
        if not text.split('.')[-1].startswith('_'):
            matches = set(match for match in matches
                          if not match.split('.')[-1].startswith('_'))
        return matches

    def locate(self, current_offset, line):
        return lineparts.current_dotted_attribute(current_offset, line)

    def format(self, word):
        return after_last_dot(word)


class DictKeyCompletion(BaseCompletionType):

    def matches(self, cursor_offset, line, **kwargs):
        if 'locals_' not in kwargs:
            return None
        locals_ = kwargs['locals_']

        r = self.locate(cursor_offset, line)
        if r is None:
            return None
        start, end, orig = r
        _, _, dexpr = lineparts.current_dict(cursor_offset, line)
        try:
            obj = safe_eval(dexpr, locals_)
        except EvaluationError:
            return set()
        if isinstance(obj, dict) and obj.keys():
            return set("{0!r}]".format(k) for k in obj.keys()
                       if repr(k).startswith(orig))
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
        start, end, word = r
        return set(name for name in MAGIC_METHODS if name.startswith(word))

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
        start, end, text = r

        matches = set()
        n = len(text)
        for word in keyword.kwlist:
            if method_match(word, n, text):
                matches.add(word)
        for nspace in [builtins.__dict__, locals_]:
            for word, val in nspace.items():
                if (method_match(word, len(text), text) and
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
        start, end, word = r
        if argspec:
            matches = set(name + '=' for name in argspec[1][0]
                          if isinstance(name, string_types) and
                          name.startswith(word))
            if py3:
                matches.update(name + '=' for name in argspec[1][4]
                               if name.startswith(word))
        return matches

    def locate(self, current_offset, line):
        return lineparts.current_word(current_offset, line)


class StringLiteralAttrCompletion(BaseCompletionType):

    def matches(self, cursor_offset, line, **kwargs):
        r = self.locate(cursor_offset, line)
        if r is None:
            return None
        start, end, word = r
        attrs = dir('')
        matches = set(att for att in attrs if att.startswith(word))
        if not word.startswith('_'):
            return set(match for match in matches if not match.startswith('_'))
        return matches

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
            except jedi.NotFoundError:
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
            return start, end, line[start:end]

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
        matches = completer.matches(
            cursor_offset, line, **kwargs)
        if matches is not None:
            return sorted(matches), (completer if matches else None)
    return [], None


BPYTHON_COMPLETER = (
    DictKeyCompletion(),
    StringLiteralAttrCompletion(),
    ImportCompletion(),
    FilenameCompletion(),
    MagicMethodCompletion(),
    MultilineJediCompletion(),
    GlobalCompletion(),
    CumulativeCompleter((AttrCompletion(), ParameterNameCompletion()))
)


def get_completer_bpython(cursor_offset, line, **kwargs):
    """"""
    return get_completer(BPYTHON_COMPLETER, cursor_offset, line, **kwargs)


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


attr_matches_re = LazyReCompile(r"(\w+(\.\w+)*)\.(\w*)")


def attr_matches(text, namespace):
    """Taken from rlcompleter.py and bent to my will.
    """

    # Gna, Py 2.6's rlcompleter searches for __call__ inside the
    # instance instead of the type, so we monkeypatch to prevent
    # side-effects (__getattr__/__getattribute__)
    m = attr_matches_re.match(text)
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
        matches = attr_lookup(obj, expr, attr)
    return matches


def attr_lookup(obj, expr, attr):
    """Second half of original attr_matches method factored out so it can
    be wrapped in a safe try/finally block in case anything bad happens to
    restore the original __getattribute__ method."""
    words = dir(obj)
    if hasattr(obj, '__class__'):
        words.append('__class__')
        words = words + rlcompleter.get_class_members(obj.__class__)
        if not isinstance(obj.__class__, abc.ABCMeta):
            try:
                words.remove('__abstractmethods__')
            except ValueError:
                pass

    matches = []
    n = len(attr)
    for word in words:
        if method_match(word, n, attr) and word != "__builtins__":
            matches.append("%s.%s" % (expr, word))
    return matches


def _callable_postfix(value, word):
    """rlcompleter's _callable_postfix done right."""
    with inspection.AttrCleaner(value):
        if inspection.is_callable(value):
            word += '('
    return word


def method_match(word, size, text):
    return word[:size] == text
