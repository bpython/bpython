# encoding: utf-8

# The MIT License
#
# Copyright (c) 2015 the bpython authors.
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
"""simple evaluation of side-effect free code

In order to provide fancy completion, some code can be executed safely.

"""

import ast
import inspect
from six import string_types
from six.moves import builtins
import sys
import types

from bpython import line as line_properties
from bpython._py3compat import py3
from bpython.inspection import is_new_style, AttrCleaner

_string_type_nodes = (ast.Str, ast.Bytes) if py3 else (ast.Str,)
_numeric_types = (int, float, complex) + (() if py3 else (long,))

# added in Python 3.4
if hasattr(ast, 'NameConstant'):
    _name_type_nodes = (ast.Name, ast.NameConstant)
else:
    _name_type_nodes = (ast.Name,)


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


# This function is under the Python License, Version 2
# This license requires modifications to the code be reported.
# Based on ast.literal_eval in Python 2 and Python 3
# Modifications:
# * Python 2 and Python 3 versions of the function are combined
# * checks that objects used as operands of + and - are numbers
#   instead of checking they are constructed with number literals
# * new docstring describing different functionality
# * looks up names from namespace
# * indexing syntax is allowed
def simple_eval(node_or_string, namespace=None):
    """
    Safely evaluate an expression node or a string containing a Python
    expression without triggering any user code.

    The string or node provided may only consist of:
    * the following Python literal structures: strings, numbers, tuples,
        lists, and dicts
    * variable names causing lookups in the passed in namespace or builtins
    * getitem calls using the [] syntax on objects of the types above

    Like the Python 3 (and unlike the Python 2) literal_eval, unary and binary
    + and - operations are allowed on all builtin numeric types.

    The optional namespace dict-like ought not to cause side effects on lookup
    """
    if namespace is None:
        namespace = {}
    if isinstance(node_or_string, string_types):
        node_or_string = ast.parse(node_or_string, mode='eval')
    if isinstance(node_or_string, ast.Expression):
        node_or_string = node_or_string.body

    def _convert(node):
        if isinstance(node, _string_type_nodes):
            return node.s
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Tuple):
            return tuple(map(_convert, node.elts))
        elif isinstance(node, ast.List):
            return list(map(_convert, node.elts))
        elif isinstance(node, ast.Dict):
            return dict((_convert(k), _convert(v)) for k, v
                        in zip(node.keys, node.values))

        # this is a deviation from literal_eval: we allow non-literals
        elif isinstance(node, _name_type_nodes):
            try:
                return namespace[node.id]
            except KeyError:
                try:
                    return getattr(builtins, node.id)
                except AttributeError:
                    raise EvaluationError("can't lookup %s" % node.id)

        # unary + and - are allowed on any type
        elif (isinstance(node, ast.UnaryOp) and
              isinstance(node.op, (ast.UAdd, ast.USub))):
            # ast.literal_eval does ast typechecks here, we use type checks
            operand = _convert(node.operand)
            if not type(operand) in _numeric_types:
                raise ValueError("unary + and - only allowed on builtin nums")
            if isinstance(node.op, ast.UAdd):
                return + operand
            else:
                return - operand
        elif (isinstance(node, ast.BinOp) and
              isinstance(node.op, (ast.Add, ast.Sub))):
            # ast.literal_eval does ast typechecks here, we use type checks
            left = _convert(node.left)
            right = _convert(node.right)
            if not (type(left) in _numeric_types and
                    type(right) in _numeric_types):
                raise ValueError("binary + and - only allowed on builtin nums")
            if isinstance(node.op, ast.Add):
                return left + right
            else:
                return left - right

        # this is a deviation from literal_eval: we allow indexing
        elif (isinstance(node, ast.Subscript) and
              isinstance(node.slice, ast.Index)):
            obj = _convert(node.value)
            index = _convert(node.slice.value)
            return safe_getitem(obj, index)

        # this is a deviation from literal_eval: we allow attribute access
        if isinstance(node, ast.Attribute):
            obj = _convert(node.value)
            attr = node.attr
            return safe_get_attribute(obj, attr)

        raise ValueError('malformed string')
    return _convert(node_or_string)


def safe_getitem(obj, index):
    if type(obj) in (list, tuple, dict, bytes) + string_types:
        try:
            return obj[index]
        except (KeyError, IndexError):
            raise EvaluationError("can't lookup key %r on %r" % (index, obj))
    raise ValueError('unsafe to lookup on object of type %s' % (type(obj), ))


def find_attribute_with_name(node, name):
    if isinstance(node, ast.Attribute) and node.attr == name:
        return node
    for item in ast.iter_child_nodes(node):
        r = find_attribute_with_name(item, name)
        if r:
            return r


def evaluate_current_expression(cursor_offset, line, namespace=None):
    """
    Return evaluated expression to the right of the dot of current attribute.

    Only evaluates builtin objects, and do any attribute lookup.
    """
    # Builds asts from with increasing numbers of characters back from cursor.
    # Find the biggest valid ast.
    # Once our attribute access is found, return its .value subtree

    if namespace is None:
        namespace = {}

    # in case attribute is blank, e.g. foo.| -> foo.xxx|
    temp_line = line[:cursor_offset] + 'xxx' + line[cursor_offset:]
    temp_cursor = cursor_offset + 3
    temp_attribute = line_properties.current_expression_attribute(
            temp_cursor, temp_line)
    if temp_attribute is None:
        raise EvaluationError("No current attribute")
    attr_before_cursor = temp_line[temp_attribute.start:temp_cursor]

    def parse_trees(cursor_offset, line):
        for i in range(cursor_offset - 1, -1, -1):
            try:
                tree = ast.parse(line[i:cursor_offset])
                yield tree
            except SyntaxError:
                continue

    largest_ast = None
    for tree in parse_trees(temp_cursor, temp_line):
        attribute_access = find_attribute_with_name(tree, attr_before_cursor)
        if attribute_access:
            largest_ast = attribute_access.value

    if largest_ast is None:
        raise EvaluationError(
                "Corresponding ASTs to right of cursor are invalid")
    try:
        return simple_eval(largest_ast, namespace)
    except ValueError:
        raise EvaluationError("Could not safely evaluate")


def evaluate_current_attribute(cursor_offset, line, namespace=None):
    """Safely evaluates the expression having an attributed accessed"""
    # this function runs user code in case of custom descriptors,
    # so could fail in any way

    obj = evaluate_current_expression(cursor_offset, line, namespace)
    attr = line_properties.current_expression_attribute(cursor_offset, line)
    if attr is None:
        raise EvaluationError("No attribute found to look up")
    try:
        return getattr(obj, attr.word)
    except AttributeError:
        raise EvaluationError(
                "can't lookup attribute %s on %r" % (attr.word, obj))


def safe_get_attribute(obj, attr):
    """Gets attributes without triggering descriptors on new-style classes"""
    if is_new_style(obj):
        with AttrCleaner(obj):
            result = safe_get_attribute_new_style(obj, attr)
            if isinstance(result, member_descriptor):
                # will either be the same slot descriptor or the value
                return getattr(obj, attr)
            return result
    return getattr(obj, attr)


class _ClassWithSlots(object):
    __slots__ = ['a']
member_descriptor = type(_ClassWithSlots.a)


def safe_get_attribute_new_style(obj, attr):
    """Returns approximately the attribute returned by getattr(obj, attr)

    The object returned ought to be callable if getattr(obj, attr) was.
    Fake callable objects may be returned instead, in order to avoid executing
    arbitrary code in descriptors.

    If the object is an instance of a class that uses __slots__, will return
    the member_descriptor object instead of the value.
    """
    if not is_new_style(obj):
        raise ValueError("%r is not a new-style class or object" % obj)
    to_look_through = (obj.__mro__
                       if inspect.isclass(obj)
                       else (obj,) + type(obj).__mro__)

    for cls in to_look_through:
        if hasattr(cls, '__dict__') and attr in cls.__dict__:
            return cls.__dict__[attr]

    raise AttributeError()
