# encoding: utf-8
"""simple evaluation of side-effect free code

In order to provide fancy completion, some code can be executed safely.

"""

import ast
from six import string_types
from six.moves import builtins

from bpython import line as line_properties

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

# taken from Python 2 stdlib ast.literal_eval
def simple_eval(node_or_string, namespace=None):
    """
    Safely evaluate an expression node or a string containing a Python
    expression.  The string or node provided may only consist of:
    * the following Python literal structures: strings, numbers, tuples,
        lists, and dicts
    * variable names causing lookups in the passed in namespace or builtins
    * getitem calls using the [] syntax on objects of the types above

    The optional namespace dict-like ought not to cause side effects on lookup
    """
    # Based heavily on stdlib ast.literal_eval
    if namespace is None:
        namespace = {}
    if isinstance(node_or_string, string_types):
        node_or_string = ast.parse(node_or_string, mode='eval')
    if isinstance(node_or_string, ast.Expression):
        node_or_string = node_or_string.body
    def _convert(node):
        if isinstance(node, ast.Str):
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
        elif isinstance(node, ast.Name):
            try:
                return namespace[node.id]
            except KeyError:
                return getattr(builtins, node.id)
        elif isinstance(node, ast.BinOp) and \
             isinstance(node.op, (ast.Add, ast.Sub)) and \
             isinstance(node.right, ast.Num) and \
             isinstance(node.right.n, complex) and \
             isinstance(node.left, ast.Num) and \
             isinstance(node.left.n, (int, long, float)):
            left = node.left.n
            right = node.right.n
            if isinstance(node.op, ast.Add):
                return left + right
            else:
                return left - right
        elif isinstance(node, ast.Subscript) and \
             isinstance(node.slice, ast.Index):
            obj = _convert(node.value)
            index = _convert(node.slice.value)
            return safe_getitem(obj, index)

        raise ValueError('malformed string')
    return _convert(node_or_string)


def safe_getitem(obj, index):
    if type(obj) in (list, tuple, dict, bytes) + string_types:
        return obj[index]
    raise ValueError('unsafe to lookup on object of type %s' % (type(obj), ))


def find_attribute_with_name(node, name):
    """Based on ast.NodeVisitor"""
    if isinstance(node, ast.Attribute) and node.attr == name:
        return node
    for field, value in ast.iter_fields(node):
        if isinstance(value, list):
            for item in value:
               if isinstance(item, ast.AST):
                    r = find_attribute_with_name(item, name)
                    if r:
                        return r
        elif isinstance(value, ast.AST):
            r = find_attribute_with_name(value, name)
            if r:
                return r


def evaluate_current_expression(cursor_offset, line, namespace={}):
    """
    Return evaluted expression to the right of the dot of current attribute.

    build asts from with increasing numbers of characters.
    Find the biggest valid ast.
    Once our attribute access is a subtree, stop
    """

    # in case attribute is blank, e.g. foo.| -> foo.xxx|
    temp_line = line[:cursor_offset] + 'xxx' + line[cursor_offset:]
    temp_cursor = cursor_offset + 3
    temp_attribute = line_properties.current_expression_attribute(
            temp_cursor, temp_line)
    if temp_attribute is None:
        raise EvaluationError("No current attribute")
    attr_before_cursor = temp_line[temp_attribute.start:temp_cursor]

    def parse_trees(cursor_offset, line):
        for i in range(cursor_offset-1, -1, -1):
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
        raise EvaluationError("Corresponding ASTs to right of cursor are invalid")
    try:
        return simple_eval(largest_ast, namespace)
    except (ValueError, KeyError, IndexError, AttributeError):
        raise EvaluationError("Could not safely evaluate")
