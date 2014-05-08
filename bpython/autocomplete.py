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
import rlcompleter
import line
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

class Autocomplete(rlcompleter.Completer):
    """
#TOMHERE TODO This doesn't need to be a class anymore - we're overriding every single method
    We're not really using it for the right thing anyway - we're hacking it to produce
    self.matches then stealing them instead of following the expected interface of calling
    complete each time.
    """

    def __init__(self, namespace = None, config = None):
        rlcompleter.Completer.__init__(self, namespace)
        self.locals = namespace
        if hasattr(config, 'autocomplete_mode'):
            self.autocomplete_mode = config.autocomplete_mode
        else:
            self.autocomplete_mode = SUBSTRING

    def complete(self, text, state):
        """Return the next possible completion for 'text'.

        This is called successively with state == 0, 1, 2, ... until it
        returns None.  The completion should begin with 'text'.

        """
        if self.use_main_ns:
            self.namespace = __main__.__dict__

        dictpattern = re.compile('[^\[\]]+\[$')
        def complete_dict(text):
            lastbracket_index = text.rindex('[')
            dexpr = text[:lastbracket_index].lstrip()
            obj = eval(dexpr, self.locals)
            if obj and isinstance(obj, type({})) and obj.keys():
                self.matches = [dexpr + "[{!r}]".format(k) for k in obj.keys()]
            else:
                # empty dictionary
                self.matches = []

        if state == 0:
            if "." in text:
                if dictpattern.match(text):
                    complete_dict(text)
                else:
                    # Examples: 'foo.b' or 'foo[bar.'
                    for i in range(1, len(text) + 1):
                        if text[-i] == '[':
                            i -= 1
                            break
                    methodtext = text[-i:]
                    self.matches = [''.join([text[:-i], m]) for m in
                                    self.attr_matches(methodtext)]
            elif dictpattern.match(text):
                complete_dict(text)
            else:
                self.matches = self.global_matches(text)
        try:
            return self.matches[state]
        except IndexError:
            return None

    def attr_matches(self, text):
        """Taken from rlcompleter.py and bent to my will.
        """

        # Gna, Py 2.6's rlcompleter searches for __call__ inside the
        # instance instead of the type, so we monkeypatch to prevent
        # side-effects (__getattr__/__getattribute__)
        m = re.match(r"(\w+(\.\w+)*)\.(\w*)", text)
        if not m:
            return []

        expr, attr = m.group(1, 3)
        if expr.isdigit():
            # Special case: float literal, using attrs here will result in
            # a SyntaxError
            return []
        obj = eval(expr, self.locals)
        with inspection.AttrCleaner(obj):
            matches = self.attr_lookup(obj, expr, attr)
        return matches

    def attr_lookup(self, obj, expr, attr):
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
            if self.method_match(word, n, attr) and word != "__builtins__":
                matches.append("%s.%s" % (expr, word))
        return matches

    def _callable_postfix(self, value, word):
        """rlcompleter's _callable_postfix done right."""
        with inspection.AttrCleaner(value):
            if inspection.is_callable(value):
                word += '('
        return word

    def global_matches(self, text):
        """Compute matches when text is a simple name.
        Return a list of all keywords, built-in functions and names currently
        defined in self.namespace that match.
        """

        hash = {}
        n = len(text)
        import keyword
        for word in keyword.kwlist:
            if self.method_match(word, n, text):
                hash[word] = 1
        for nspace in [__builtin__.__dict__, self.namespace]:
            for word, val in nspace.items():
                if self.method_match(word, len(text), text) and word != "__builtins__":
                    hash[self._callable_postfix(val, word)] = 1
        matches = hash.keys()
        matches.sort()
        return matches

    def method_match(self, word, size, text):
        if self.autocomplete_mode == SIMPLE:
            return word[:size] == text
        elif self.autocomplete_mode == SUBSTRING:
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
    return cs

def find_matches(cursor_offset, current_line, locals_, current_string_callback, completer, magic_methods, argspec):
    """Returns a list of matches and function to use for replacing words on tab"""

    if line.current_string(cursor_offset, current_line):
        matches = filename_matches(line.current_string(cursor_offset, current_line))
        return matches, line.current_string

    if line.current_word(cursor_offset, current_line) is None:
        return [], None

    matches = importcompletion.complete(cursor_offset, current_line)
    return matches, line.current_word

    cw = line.current_word(cursor_offset, current_line)[2]

    try:
        completer.complete(cw, 0)
    #except Exception:
    #    # This sucks, but it's either that or list all the exceptions that could
    #    # possibly be raised here, so if anyone wants to do that, feel free to send me
    #    # a patch. XXX: Make sure you raise here if you're debugging the completion
    #    # stuff !
    #    e = True
    #else:
        e = False
        matches = completer.matches
        matches.extend(magic_methods(cw))
    except KeyboardInterrupt:
        pass

    if not e and argspec:
        matches.extend(name + '=' for name in argspec[1][0]
                       if isinstance(name, basestring) and name.startswith(cw))
        if py3:
            matches.extend(name + '=' for name in argspec[1][4]
                           if name.startswith(cw))

    # unless the first character is a _ filter out all attributes starting with a _
    if not e and not cw.split('.')[-1].startswith('_'):
        matches = [match for match in matches
                   if not match.split('.')[-1].startswith('_')]

    return sorted(set(matches)), line.current_word
