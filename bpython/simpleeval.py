# encoding: utf-8
"""simple evaluation of side-effect free code

In order to provide fancy completion, some code can be executed safely.

"""

from ast import *
from six import string_types

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

def simple_eval(node_or_string, namespace={}):
    """
    Safely evaluate an expression node or a string containing a Python
    expression.  The string or node provided may only consist of:
    * the following Python literal structures: strings, numbers, tuples,
        lists, dicts, booleans, and None.
    * variable names causing lookups in the passed in namespace or builtins
    * getitem calls using the [] syntax on objects of the types above
    * getitem calls on subclasses of the above types if they do not override
        the __getitem__ method and do not override __getattr__ or __getattribute__
        (or maybe we'll try to clean those up?)

    The optional namespace dict-like ought not to cause side effects on lookup
    """
    if isinstance(node_or_string, string_types):
        node_or_string = parse(node_or_string, mode='eval')
    if isinstance(node_or_string, Expression):
        node_or_string = node_or_string.body
    def _convert(node):
        if isinstance(node, Str):
            return node.s
        elif isinstance(node, Num):
            return node.n
        elif isinstance(node, Tuple):
            return tuple(map(_convert, node.elts))
        elif isinstance(node, List):
            return list(map(_convert, node.elts))
        elif isinstance(node, Dict):
            return dict((_convert(k), _convert(v)) for k, v
                        in zip(node.keys, node.values))
        elif isinstance(node, Name):
            try:
                return namespace[node.id]
            except KeyError:
                return __builtins__[node.id]
        elif isinstance(node, BinOp) and \
             isinstance(node.op, (Add, Sub)) and \
             isinstance(node.right, Num) and \
             isinstance(node.right.n, complex) and \
             isinstance(node.left, Num) and \
             isinstance(node.left.n, (int, long, float)):
            left = node.left.n
            right = node.right.n
            if isinstance(node.op, Add):
                return left + right
            else:
                return left - right
        elif isinstance(node, Subscript) and \
             isinstance(node.slice, Index):
            obj = _convert(node.value)
            index = _convert(node.slice.value)
            return safe_getitem(obj, index)

        raise ValueError('malformed string')
    return _convert(node_or_string)

def safe_getitem(obj, index):
    if type(obj) in (list, tuple, dict, bytes) + string_types:
        return obj[index]
    raise ValueError('unsafe to lookup on object of type %s' % (type(obj), ))


class AttributeSearcher(NodeVisitor):
    """Search for a Load of an Attribute at col_offset"""
    def visit_attribute(self, node):
        print node.attribute

def _current_simple_expression(cursor_offset, line):
    """
    Returns the current "simple expression" being attribute accessed

    build asts from with increasing numbers of characters.
    Find the biggest valid ast.
    Once our attribute access is a subtree, stop


    """

    # in case attribute is blank, e.g. foo.| -> foo.xxx|
    temp_line = line[:cursor_offset] + 'xxx' + line[cursor_offset:]
    temp_cursor = cursor_offset + 3

    for i in range(temp_cursor-1, -1, -1):
        try:
            tree = parse(temp_line[i:temp_cursor])
        except SyntaxError:
            return None
        


