# encoding: utf-8

# The MIT License
#
# Copyright (c) 2009-2011 the bpython authors.
# Copyright (c) 2015 Sebastian Ramacher
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

from __future__ import absolute_import

import inspect
import io
import keyword
import pydoc
from collections import namedtuple
from six.moves import range

from pygments.token import Token

from ._py3compat import PythonLexer, py3
from .lazyre import LazyReCompile

if not py3:
    import types

    _name = LazyReCompile(r'[a-zA-Z_]\w*$')

ArgSpec = namedtuple('ArgSpec', ['args', 'varargs', 'varkwargs', 'defaults',
                                 'kwonly', 'kwonly_defaults', 'annotations'])

FuncProps = namedtuple('FuncProps', ['func', 'argspec', 'is_bound_method'])


class AttrCleaner(object):
    """A context manager that tries to make an object not exhibit side-effects
       on attribute lookup."""

    def __init__(self, obj):
        self.obj = obj

    def __enter__(self):
        """Try to make an object not exhibit side-effects on attribute
        lookup."""
        type_ = type(self.obj)
        __getattribute__ = None
        __getattr__ = None
        # Dark magic:
        # If __getattribute__ doesn't exist on the class and __getattr__ does
        # then __getattr__ will be called when doing
        #   getattr(type_, '__getattribute__', None)
        # so we need to first remove the __getattr__, then the
        # __getattribute__, then look up the attributes and then restore the
        # original methods. :-(
        # The upshot being that introspecting on an object to display its
        # attributes will avoid unwanted side-effects.
        if is_new_style(self.obj):
            __getattr__ = getattr(type_, '__getattr__', None)
            if __getattr__ is not None:
                try:
                    setattr(type_, '__getattr__', (lambda *_, **__: None))
                except TypeError:
                    __getattr__ = None
            __getattribute__ = getattr(type_, '__getattribute__', None)
            if __getattribute__ is not None:
                try:
                    setattr(type_, '__getattribute__', object.__getattribute__)
                except TypeError:
                    # XXX: This happens for e.g. built-in types
                    __getattribute__ = None
        self.attribs = (__getattribute__, __getattr__)
        # /Dark magic

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore an object's magic methods."""
        type_ = type(self.obj)
        __getattribute__, __getattr__ = self.attribs
        # Dark magic:
        if __getattribute__ is not None:
            setattr(type_, '__getattribute__', __getattribute__)
        if __getattr__ is not None:
            setattr(type_, '__getattr__', __getattr__)
        # /Dark magic


if py3:
    def is_new_style(obj):
        return True
else:
    def is_new_style(obj):
        """Returns True if obj is a new-style class or object"""
        return type(obj) not in [types.InstanceType, types.ClassType]


class _Repr(object):
    """
    Helper for `fixlongargs()`: Returns the given value in `__repr__()`.
    """

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return self.value

    __str__ = __repr__


def parsekeywordpairs(signature):
    tokens = PythonLexer().get_tokens(signature)
    preamble = True
    stack = []
    substack = []
    parendepth = 0
    for token, value in tokens:
        if preamble:
            if token is Token.Punctuation and value == u"(":
                preamble = False
            continue

        if token is Token.Punctuation:
            if value in [u'(', u'{', u'[']:
                parendepth += 1
            elif value in [u')', u'}', u']']:
                parendepth -= 1
            elif value == ':' and parendepth == -1:
                # End of signature reached
                break
            if ((value == ',' and parendepth == 0) or
                    (value == ')' and parendepth == -1)):
                stack.append(substack)
                substack = []
                continue

        if value and (parendepth > 0 or value.strip()):
            substack.append(value)

    d = {}
    for item in stack:
        if len(item) >= 3:
            d[item[0]] = ''.join(item[2:])
    return d


def fixlongargs(f, argspec):
    """Functions taking default arguments that are references to other objects
    whose str() is too big will cause breakage, so we swap out the object
    itself with the name it was referenced with in the source by parsing the
    source itself !"""
    if argspec[3] is None:
        # No keyword args, no need to do anything
        return
    values = list(argspec[3])
    if not values:
        return
    keys = argspec[0][-len(values):]
    try:
        src = inspect.getsourcelines(f)
    except (IOError, IndexError):
        # IndexError is raised in inspect.findsource(), can happen in
        # some situations. See issue #94.
        return
    signature = ''.join(src[0])
    kwparsed = parsekeywordpairs(signature)

    for i, (key, value) in enumerate(zip(keys, values)):
        if len(repr(value)) != len(kwparsed[key]):
            values[i] = _Repr(kwparsed[key])

    argspec[3] = values


getpydocspec_re = LazyReCompile(r'([a-zA-Z_][a-zA-Z0-9_]*?)\((.*?)\)')


def getpydocspec(f, func):
    try:
        argspec = pydoc.getdoc(f)
    except NameError:
        return None

    s = getpydocspec_re.search(argspec)
    if s is None:
        return None

    if not hasattr(f, '__name__') or s.groups()[0] != f.__name__:
        return None

    args = list()
    defaults = list()
    varargs = varkwargs = None
    kwonly_args = list()
    kwonly_defaults = dict()
    for arg in s.group(2).split(','):
        arg = arg.strip()
        if arg.startswith('**'):
            varkwargs = arg[2:]
        elif arg.startswith('*'):
            varargs = arg[1:]
        else:
            arg, _, default = arg.partition('=')
            if varargs is not None:
                kwonly_args.append(arg)
                if default:
                    kwonly_defaults[arg] = default
            else:
                args.append(arg)
                if default:
                    defaults.append(default)

    return ArgSpec(args, varargs, varkwargs, defaults, kwonly_args,
                   kwonly_defaults, None)


def getfuncprops(func, f):
    # Check if it's a real bound method or if it's implicitly calling __init__
    # (i.e. FooClass(...) and not FooClass.__init__(...) -- the former would
    # not take 'self', the latter would:
    try:
        func_name = getattr(f, '__name__', None)
    except:
        # if calling foo.__name__ would result in an error
        func_name = None

    try:
        is_bound_method = ((inspect.ismethod(f) and f.__self__ is not None) or
                           (func_name == '__init__' and not
                            func.endswith('.__init__')) or
                           (func_name == '__new__' and not
                            func.endswith('.__new__')))
    except:
        # if f is a method from a xmlrpclib.Server instance, func_name ==
        # '__init__' throws xmlrpclib.Fault (see #202)
        return None
    try:
        if py3:
            argspec = inspect.getfullargspec(f)
        else:
            argspec = inspect.getargspec(f)

        argspec = list(argspec)
        fixlongargs(f, argspec)
        if len(argspec) == 4:
            argspec = argspec + [list(), dict(), None]
        argspec = ArgSpec(*argspec)
        fprops = FuncProps(func, argspec, is_bound_method)
    except (TypeError, KeyError):
        with AttrCleaner(f):
            argspec = getpydocspec(f, func)
        if argspec is None:
            return None
        if inspect.ismethoddescriptor(f):
            argspec.args.insert(0, 'obj')
        fprops = FuncProps(func, argspec, is_bound_method)
    return fprops


def is_eval_safe_name(string):
    if py3:
        return all(part.isidentifier() and not keyword.iskeyword(part)
                   for part in string.split('.'))
    else:
        return all(_name.match(part) and not keyword.iskeyword(part)
                   for part in string.split('.'))


def is_callable(obj):
    return callable(obj)


get_encoding_line_re = LazyReCompile(r'^.*coding[:=]\s*([-\w.]+).*$')


def get_encoding(obj):
    """Try to obtain encoding information of the source of an object."""
    for line in inspect.findsource(obj)[0][:2]:
        m = get_encoding_line_re.search(line)
        if m:
            return m.group(1)
    return 'ascii'


def get_encoding_comment(source):
    """Returns encoding line without the newline, or None is not found"""
    for line in source.splitlines()[:2]:
        m = get_encoding_line_re.search(line)
        if m:
            return m.group(0)
    return None


def get_encoding_file(fname):
    """Try to obtain encoding information from a Python source file."""
    with io.open(fname, 'rt', encoding='ascii', errors='ignore') as f:
        for unused in range(2):
            line = f.readline()
            match = get_encoding_line_re.search(line)
            if match:
                return match.group(1)
    return 'ascii'


if py3:
    def get_source_unicode(obj):
        """Returns a decoded source of object"""
        return inspect.getsource(obj)
else:
    def get_source_unicode(obj):
        """Returns a decoded source of object"""
        return inspect.getsource(obj).decode(get_encoding(obj))
