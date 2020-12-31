# The MIT License
#
# Copyright (c) 2009-2015 the bpython authors.
# Copyright (c) 2015-2020 Sebastian Ramacher
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


import __main__
import abc
import glob
import keyword
import logging
import os
import re
import rlcompleter
import builtins

from enum import Enum
from . import inspection
from . import line as lineparts
from .line import LinePart
from .lazyre import LazyReCompile
from .simpleeval import safe_eval, evaluate_current_expression, EvaluationError


# Autocomplete modes
class AutocompleteModes(Enum):
    SIMPLE = "simple"
    SUBSTRING = "substring"
    FUZZY = "fuzzy"

    @classmethod
    def from_string(cls, value):
        if value in cls.__members__:
            return cls.__members__[value]
        return None


MAGIC_METHODS = tuple(
    f"__{s}__"
    for s in (
        "new",
        "init",
        "del",
        "repr",
        "str",
        "bytes",
        "format",
        "lt",
        "le",
        "eq",
        "ne",
        "gt",
        "ge",
        "hash",
        "bool",
        "getattr",
        "getattribute",
        "setattr",
        "delattr",
        "dir",
        "get",
        "set",
        "delete",
        "set_name",
        "init_subclass",
        "instancecheck",
        "subclasscheck",
        "class_getitem",
        "call",
        "len",
        "length_hint",
        "getitem",
        "setitem",
        "delitem",
        "missing",
        "iter",
        "reversed",
        "contains",
        "add",
        "sub",
        "mul",
        "matmul",
        "truediv",
        "floordiv",
        "mod",
        "divmod",
        "pow",
        "lshift",
        "rshift",
        "and",
        "xor",
        "or",
        "radd",
        "rsub",
        "rmul",
        "rmatmul",
        "rtruediv",
        "rfloordiv",
        "rmod",
        "rdivmod",
        "rpow",
        "rlshift",
        "rrshift",
        "rand",
        "rxor",
        "ror",
        "iadd",
        "isub",
        "imul",
        "imatmul",
        "itruediv",
        "ifloordiv",
        "imod",
        "ipow",
        "ilshift",
        "irshift",
        "iand",
        "ixor",
        "ixor",
        "neg",
        "pos",
        "abs",
        "invert",
        "complex",
        "int",
        "float",
        "index",
        "round",
        "trunc",
        "floor",
        "ceil",
        "enter",
        "exit",
        "await",
        "aiter",
        "anext",
        "aenter",
        "aexit",
    )
)

KEYWORDS = frozenset(keyword.kwlist)


def after_last_dot(name):
    return name.rstrip(".").rsplit(".")[-1]


def few_enough_underscores(current, match):
    """Returns whether match should be shown based on current

    if current is _, True if match starts with 0 or 1 underscore
    if current is __, True regardless of match
    otherwise True if match does not start with any underscore
    """
    if current.startswith("__"):
        return True
    elif current.startswith("_") and not match.startswith("__"):
        return True
    elif match.startswith("_"):
        return False
    else:
        return True


def method_match_simple(word, size, text):
    return word[:size] == text


def method_match_substring(word, size, text):
    return text in word


def method_match_fuzzy(word, size, text):
    s = r".*%s.*" % ".*".join(list(text))
    return re.search(s, word)


MODES_MAP = {
    AutocompleteModes.SIMPLE: method_match_simple,
    AutocompleteModes.SUBSTRING: method_match_substring,
    AutocompleteModes.FUZZY: method_match_fuzzy,
}


class BaseCompletionType:
    """Describes different completion types"""

    def __init__(self, shown_before_tab=True, mode=AutocompleteModes.SIMPLE):
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
        """Returns a Linepart namedtuple instance or None given cursor and line

        A Linepart namedtuple contains a start, stop, and word. None is
        returned if no target for this type of completion is found under
        the cursor."""
        raise NotImplementedError

    def format(self, word):
        return word

    def substitute(self, cursor_offset, line, match):
        """Returns a cursor offset and line with match swapped in"""
        lpart = self.locate(cursor_offset, line)
        offset = lpart.start + len(match)
        changed_line = line[: lpart.start] + match + line[lpart.end :]
        return offset, changed_line

    @property
    def shown_before_tab(self):
        """Whether suggestions should be shown before the user hits tab, or only
        once that has happened."""
        return self._shown_before_tab


class CumulativeCompleter(BaseCompletionType):
    """Returns combined matches from several completers"""

    def __init__(self, completers, mode=AutocompleteModes.SIMPLE):
        if not completers:
            raise ValueError(
                "CumulativeCompleter requires at least one completer"
            )
        self._completers = completers

        super().__init__(True, mode)

    def locate(self, current_offset, line):
        return self._completers[0].locate(current_offset, line)

    def format(self, word):
        return self._completers[0].format(word)

    def matches(self, cursor_offset, line, **kwargs):
        return_value = None
        all_matches = set()
        for completer in self._completers:
            matches = completer.matches(
                cursor_offset=cursor_offset, line=line, **kwargs
            )
            if matches is not None:
                all_matches.update(matches)
                return_value = all_matches

        return return_value


class ImportCompletion(BaseCompletionType):
    def __init__(self, module_gatherer, mode=AutocompleteModes.SIMPLE):
        super().__init__(False, mode)
        self.module_gatherer = module_gatherer

    def matches(self, cursor_offset, line, **kwargs):
        return self.module_gatherer.complete(cursor_offset, line)

    def locate(self, current_offset, line):
        return lineparts.current_word(current_offset, line)

    def format(self, word):
        return after_last_dot(word)


class FilenameCompletion(BaseCompletionType):
    def __init__(self, mode=AutocompleteModes.SIMPLE):
        super().__init__(False, mode)

    def safe_glob(self, pathname):
        return glob.iglob(glob.escape(pathname) + "*")

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
            if cs.word.startswith("~"):
                filename = username + filename[len(user_dir) :]
            matches.add(filename)
        return matches

    def locate(self, current_offset, line):
        return lineparts.current_string(current_offset, line)

    def format(self, filename):
        filename.rstrip(os.sep).rsplit(os.sep)[-1]
        if os.sep in filename[:-1]:
            return filename[filename.rindex(os.sep, 0, -1) + 1 :]
        else:
            return filename


class AttrCompletion(BaseCompletionType):

    attr_matches_re = LazyReCompile(r"(\w+(\.\w+)*)\.(\w*)")

    def matches(self, cursor_offset, line, **kwargs):
        if "locals_" not in kwargs:
            return None
        locals_ = kwargs["locals_"]

        r = self.locate(cursor_offset, line)
        if r is None:
            return None

        if locals_ is None:  # TODO add a note about why
            locals_ = __main__.__dict__

        assert "." in r.word

        for i in range(1, len(r.word) + 1):
            if r.word[-i] == "[":
                i -= 1
                break
        methodtext = r.word[-i:]
        matches = {
            "".join([r.word[:-i], m])
            for m in self.attr_matches(methodtext, locals_)
        }

        return {
            m
            for m in matches
            if few_enough_underscores(r.word.split(".")[-1], m.split(".")[-1])
        }

    def locate(self, current_offset, line):
        return lineparts.current_dotted_attribute(current_offset, line)

    def format(self, word):
        return after_last_dot(word)

    def attr_matches(self, text, namespace):
        """Taken from rlcompleter.py and bent to my will."""

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
        matches = self.attr_lookup(obj, expr, attr)
        return matches

    def attr_lookup(self, obj, expr, attr):
        """Second half of attr_matches."""
        words = self.list_attributes(obj)
        if inspection.hasattr_safe(obj, "__class__"):
            words.append("__class__")
            klass = inspection.getattr_safe(obj, "__class__")
            words = words + rlcompleter.get_class_members(klass)
            if not isinstance(klass, abc.ABCMeta):
                try:
                    words.remove("__abstractmethods__")
                except ValueError:
                    pass

        matches = []
        n = len(attr)
        for word in words:
            if self.method_match(word, n, attr) and word != "__builtins__":
                matches.append(f"{expr}.{word}")
        return matches

    def list_attributes(self, obj):
        # TODO: re-implement dir using getattr_static to avoid using
        # AttrCleaner here?
        with inspection.AttrCleaner(obj):
            return dir(obj)


class DictKeyCompletion(BaseCompletionType):
    def matches(self, cursor_offset, line, **kwargs):
        if "locals_" not in kwargs:
            return None
        locals_ = kwargs["locals_"]

        r = self.locate(cursor_offset, line)
        if r is None:
            return None
        _, _, dexpr = lineparts.current_dict(cursor_offset, line)
        try:
            obj = safe_eval(dexpr, locals_)
        except EvaluationError:
            return None
        if isinstance(obj, dict) and obj.keys():
            matches = {
                f"{k!r}]" for k in obj.keys() if repr(k).startswith(r.word)
            }
            return matches if matches else None
        else:
            return None

    def locate(self, current_offset, line):
        return lineparts.current_dict_key(current_offset, line)

    def format(self, match):
        return match[:-1]


class MagicMethodCompletion(BaseCompletionType):
    def matches(self, cursor_offset, line, **kwargs):
        if "current_block" not in kwargs:
            return None
        current_block = kwargs["current_block"]

        r = self.locate(cursor_offset, line)
        if r is None:
            return None
        if "class" not in current_block:
            return None
        return {name for name in MAGIC_METHODS if name.startswith(r.word)}

    def locate(self, current_offset, line):
        return lineparts.current_method_definition_name(current_offset, line)


class GlobalCompletion(BaseCompletionType):
    def matches(self, cursor_offset, line, **kwargs):
        """Compute matches when text is a simple name.
        Return a list of all keywords, built-in functions and names currently
        defined in self.namespace that match.
        """
        if "locals_" not in kwargs:
            return None
        locals_ = kwargs["locals_"]

        r = self.locate(cursor_offset, line)
        if r is None:
            return None

        matches = set()
        n = len(r.word)
        for word in KEYWORDS:
            if self.method_match(word, n, r.word):
                matches.add(word)
        for nspace in (builtins.__dict__, locals_):
            for word, val in nspace.items():
                # if identifier isn't ascii, don't complete (syntax error)
                if word is None:
                    continue
                if (
                    self.method_match(word, n, r.word)
                    and word != "__builtins__"
                ):
                    matches.add(_callable_postfix(val, word))
        return matches if matches else None

    def locate(self, current_offset, line):
        return lineparts.current_single_word(current_offset, line)


class ParameterNameCompletion(BaseCompletionType):
    def matches(self, cursor_offset, line, **kwargs):
        if "argspec" not in kwargs:
            return None
        argspec = kwargs["argspec"]

        if not argspec:
            return None
        r = self.locate(cursor_offset, line)
        if r is None:
            return None
        if argspec:
            matches = {
                name + "="
                for name in argspec[1][0]
                if isinstance(name, str) and name.startswith(r.word)
            }
            matches.update(
                name + "=" for name in argspec[1][4] if name.startswith(r.word)
            )
        return matches if matches else None

    def locate(self, current_offset, line):
        return lineparts.current_word(current_offset, line)


class ExpressionAttributeCompletion(AttrCompletion):
    # could replace attr completion as a more general case with some work
    def locate(self, current_offset, line):
        return lineparts.current_expression_attribute(current_offset, line)

    def matches(self, cursor_offset, line, **kwargs):
        if "locals_" not in kwargs:
            return None
        locals_ = kwargs["locals_"]

        if locals_ is None:
            locals_ = __main__.__dict__

        attr = self.locate(cursor_offset, line)

        try:
            obj = evaluate_current_expression(cursor_offset, line, locals_)
        except EvaluationError:
            return set()

        #        strips leading dot
        matches = [m[1:] for m in self.attr_lookup(obj, "", attr.word)]
        return {m for m in matches if few_enough_underscores(attr.word, m)}


try:
    import jedi
except ImportError:

    class MultilineJediCompletion(BaseCompletionType):
        def matches(self, cursor_offset, line, **kwargs):
            return None


else:

    class JediCompletion(BaseCompletionType):
        def matches(self, cursor_offset, line, **kwargs):
            if "history" not in kwargs:
                return None
            history = kwargs["history"]

            if not lineparts.current_word(cursor_offset, line):
                return None
            history = "\n".join(history) + "\n" + line

            try:
                script = jedi.Script(history, path="fake.py")
                completions = script.complete(
                    len(history.splitlines()), cursor_offset
                )
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

            first_letter = line[self._orig_start : self._orig_start + 1]

            matches = [c.name for c in completions]
            if any(
                not m.lower().startswith(matches[0][0].lower()) for m in matches
            ):
                # Too general - giving completions starting with multiple
                # letters
                return None
            else:
                # case-sensitive matches only
                return {m for m in matches if m.startswith(first_letter)}

        def locate(self, cursor_offset, line):
            start = self._orig_start
            end = cursor_offset
            return LinePart(start, end, line[start:end])

    class MultilineJediCompletion(JediCompletion):
        def matches(self, cursor_offset, line, **kwargs):
            if "current_block" not in kwargs or "history" not in kwargs:
                return None
            current_block = kwargs["current_block"]
            history = kwargs["history"]

            if "\n" in current_block:
                assert cursor_offset <= len(line), "{!r} {!r}".format(
                    cursor_offset,
                    line,
                )
                results = super().matches(cursor_offset, line, history=history)
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
        try:
            matches = completer.matches(cursor_offset, line, **kwargs)
        except Exception as e:
            # Instead of crashing the UI, log exceptions from autocompleters.
            logger = logging.getLogger(__name__)
            logger.debug(
                "Completer {} failed with unhandled exception: {}".format(
                    completer, e
                )
            )
            continue
        if matches is not None:
            return sorted(matches), (completer if matches else None)

    return [], None


def get_default_completer(mode=AutocompleteModes.SIMPLE, module_gatherer=None):
    return (
        DictKeyCompletion(mode=mode),
        ImportCompletion(module_gatherer, mode=mode),
        FilenameCompletion(mode=mode),
        MagicMethodCompletion(mode=mode),
        MultilineJediCompletion(mode=mode),
        CumulativeCompleter(
            (GlobalCompletion(mode=mode), ParameterNameCompletion(mode=mode)),
            mode=mode,
        ),
        AttrCompletion(mode=mode),
        ExpressionAttributeCompletion(mode=mode),
    )


def _callable_postfix(value, word):
    """rlcompleter's _callable_postfix done right."""
    if callable(value):
        word += "("
    return word
