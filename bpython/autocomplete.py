# The MIT License
#
# Copyright (c) 2009-2012 the bpython authors.
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

from __future__ import with_statement
import __builtin__
import __main__
import rlcompleter
import line as lineparts
import re
import os
from glob import glob
from bpython import inspection
from bpython import importcompletion
from bpython._py3compat import py3

# Needed for special handling of __abstractmethods__
# abc only exists since 2.6, so check both that it exists and that it's
# the one we're expecting
try:
    import abc
    abc.ABCMeta
    has_abc = True
except (ImportError, AttributeError):
    has_abc = False

# Autocomplete modes
SIMPLE = 'simple'
SUBSTRING = 'substring'
FUZZY = 'fuzzy'

def attr_complete(text, namespace=None, config=None):
    """Return list of matches """
    if namespace is None:
        namespace = __main__.__dict__ #TODO figure out if this __main__ still makes sense

    if hasattr(config, 'autocomplete_mode'):
        autocomplete_mode = config.autocomplete_mode
    else:
        autocomplete_mode = SUBSTRING

    if "." in text:
        # Examples: 'foo.b' or 'foo[bar.'
        for i in range(1, len(text) + 1):
            if text[-i] == '[':
                i -= 1
                break
        methodtext = text[-i:]
        return [''.join([text[:-i], m]) for m in
                            attr_matches(methodtext, namespace, autocomplete_mode)]
    else:
        return global_matches(text, namespace, autocomplete_mode)

class SafeEvalFailed(Exception):
    """If this object is returned, safe_eval failed"""
    # Because every normal Python value is a possible return value of safe_eval

def safe_eval(expr, namespace):
    """Not all that safe, just catches some errors"""
    if expr.isdigit():
        # Special case: float literal, using attrs here will result in
        # a SyntaxError
        return SafeEvalFailed
    try:
        obj = eval(expr, namespace)
        return obj
    except (NameError,) as e:
        # If debugging safe_eval, raise this!
        # raise e
        return SafeEvalFailed

def attr_matches(text, namespace, autocomplete_mode):
    """Taken from rlcompleter.py and bent to my will.
    """

    # Gna, Py 2.6's rlcompleter searches for __call__ inside the
    # instance instead of the type, so we monkeypatch to prevent
    # side-effects (__getattr__/__getattribute__)
    m = re.match(r"(\w+(\.\w+)*)\.(\w*)", text)
    if not m:
        return []

    expr, attr = m.group(1, 3)
    obj = safe_eval(expr, namespace)
    if obj is SafeEvalFailed:
        return []
    with inspection.AttrCleaner(obj):
        matches = attr_lookup(obj, expr, attr, autocomplete_mode)
    return matches

def attr_lookup(obj, expr, attr, autocomplete_mode):
    """Second half of original attr_matches method factored out so it can
    be wrapped in a safe try/finally block in case anything bad happens to
    restore the original __getattribute__ method."""
    words = dir(obj)
    if hasattr(obj, '__class__'):
        words.append('__class__')
        words = words + rlcompleter.get_class_members(obj.__class__)
        if has_abc and not isinstance(obj.__class__, abc.ABCMeta):
            try:
                words.remove('__abstractmethods__')
            except ValueError:
                pass

    matches = []
    n = len(attr)
    for word in words:
        if method_match(word, n, attr, autocomplete_mode) and word != "__builtins__":
            matches.append("%s.%s" % (expr, word))
    return matches

def _callable_postfix(value, word):
    """rlcompleter's _callable_postfix done right."""
    with inspection.AttrCleaner(value):
        if inspection.is_callable(value):
            word += '('
    return word

def global_matches(text, namespace, autocomplete_mode):
    """Compute matches when text is a simple name.
    Return a list of all keywords, built-in functions and names currently
    defined in self.namespace that match.
    """

    hash = {}
    n = len(text)
    import keyword
    for word in keyword.kwlist:
        if method_match(word, n, text, autocomplete_mode):
            hash[word] = 1
    for nspace in [__builtin__.__dict__, namespace]:
        for word, val in nspace.items():
            if method_match(word, len(text), text, autocomplete_mode) and word != "__builtins__":
                hash[_callable_postfix(val, word)] = 1
    matches = hash.keys()
    matches.sort()
    return matches

def method_match(word, size, text, autocomplete_mode):
    if autocomplete_mode == SIMPLE:
        return word[:size] == text
    elif autocomplete_mode == SUBSTRING:
        s = r'.*%s.*' % text
        return re.search(s, word)
    else:
        s = r'.*%s.*' % '.*'.join(list(text))
        return re.search(s, word)

def filename_matches(cs):
    matches = []
    username = cs.split(os.path.sep, 1)[0]
    user_dir = os.path.expanduser(username)
    for filename in glob(os.path.expanduser(cs + '*')):
        if os.path.isdir(filename):
            filename += os.path.sep
        if cs.startswith('~'):
            filename = username + filename[len(user_dir):]
        matches.append(filename)
    return matches

def last_part_of_filename(filename):
    filename.rstrip(os.sep).rsplit(os.sep)[-1]
    if os.sep in filename[:-1]:
        return filename[filename.rindex(os.sep, 0, -1)+1:]
    else:
        return filename

def after_last_dot(name):
    return name.rstrip('.').rsplit('.')[-1]

def dict_key_format(filename):
    # dictionary key suggestions
    #items = [x.rstrip(']') for x in items]
    #if current_item:
    #    current_item = current_item.rstrip(']')
    pass

def get_completer(cursor_offset, current_line, locals_, argspec, config, magic_methods):
    """Returns a list of matches and a class for what kind of completion is happening

    If no completion type is relevant, returns None, None"""

    #TODO use the smarter current_string() in Repl that knows about the buffer
    #TODO don't pass in config, pass in the settings themselves

    matches = ImportCompletion.matches(cursor_offset, current_line)
    if matches is not None:
        return sorted(set(matches)), ImportCompletion

    matches = FilenameCompletion.matches(cursor_offset, current_line)
    if matches is not None:
        return sorted(set(matches)), FilenameCompletion

    matches = DictKeyCompletion.matches(cursor_offset, current_line, locals_=locals_, config=config)
    if matches:
        return sorted(set(matches)), DictKeyCompletion

    matches = AttrCompletion.matches(cursor_offset, current_line, locals_=locals_, config=config)
    if matches is not None:
        cw = AttrCompletion.locate(cursor_offset, current_line)[2]
        matches.extend(magic_methods(cw))
        if argspec:
            matches.extend(name + '=' for name in argspec[1][0]
                           if isinstance(name, basestring) and name.startswith(cw))
            if py3:
                matches.extend(name + '=' for name in argspec[1][4]
                               if name.startswith(cw))

        # unless the first character is a _ filter out all attributes starting with a _
        if not cw.split('.')[-1].startswith('_'):
            matches = [match for match in matches
                       if not match.split('.')[-1].startswith('_')]

        return sorted(set(matches)), AttrCompletion

    return None, None


class BaseCompletionType(object):
    """Describes different completion types"""
    def matches(cls, cursor_offset, line):
        """Returns a list of possible matches given a line and cursor, or None
        if this completion type isn't applicable.

        ie, import completion doesn't make sense if there cursor isn't after
        an import or from statement

        Completion types are used to:
            * `locate(cur, line)` their target word to replace given a line and cursor
            * find `matches(cur, line)` that might replace that word
            * `format(match)` matches to be displayed to the user
            * determine whether suggestions should be `shown_before_tab`
            * `substitute(cur, line, match)` in a match for what's found with `target`
            """
        raise NotImplementedError
    def locate(cls, cursor_offset, line):
        """Returns a start, stop, and word given a line and cursor, or None
        if no target for this type of completion is found under the cursor"""
        raise NotImplementedError
    def format(cls, word):
        return word
    shown_before_tab = True # whether suggestions should be shown before the
                           # user hits tab, or only once that has happened
    def substitute(cls, cursor_offset, line, match):
        """Returns a cursor offset and line with match swapped in"""
        start, end, word = cls.locate(cursor_offset, line)
        result = start + len(match), line[:start] + match + line[end:]
        return result

class ImportCompletion(BaseCompletionType):
    matches = staticmethod(importcompletion.complete)
    locate = staticmethod(lineparts.current_word)
    format = staticmethod(after_last_dot)

class FilenameCompletion(BaseCompletionType):
    shown_before_tab = False
    @classmethod
    def matches(cls, cursor_offset, current_line):
        cs = lineparts.current_string(cursor_offset, current_line)
        if cs is None:
            return None
        return filename_matches(cs[2])
    locate = staticmethod(lineparts.current_string)
    format = staticmethod(last_part_of_filename)

class AttrCompletion(BaseCompletionType):
    @classmethod
    def matches(cls, cursor_offset, line, locals_, config):
        r = cls.locate(cursor_offset, line)
        if r is None:
            return None
        cw = r[2]
        return attr_complete(cw, namespace=locals_, config=config)
    locate = staticmethod(lineparts.current_word)
    format = staticmethod(after_last_dot)

class DictKeyCompletion(BaseCompletionType):
    locate = staticmethod(lineparts.current_dict_key)
    @classmethod
    def matches(cls, cursor_offset, line, locals_, config):
        r = cls.locate(cursor_offset, line)
        if r is None:
            return None
        start, end, orig = r
        _, _, dexpr = lineparts.current_dict(cursor_offset, line)
        obj = safe_eval(dexpr, locals_)
        if obj is SafeEvalFailed:
            return []
        if obj and isinstance(obj, type({})) and obj.keys():
            return ["{!r}]".format(k) for k in obj.keys() if repr(k).startswith(orig)]
        else:
            return []
    @classmethod
    def format(cls, match):
        return match[:-1]
