# -*- coding: utf-8 -*-

try:
    import unittest2 as unittest
except ImportError:
    import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from bpython.translations import init
from bpython._py3compat import py3
from six.moves import builtins


class FixLanguageTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init(languages=['en'])


class MagicIterMock(mock.MagicMock):

    if py3:
        __next__ = mock.Mock(return_value=None)
    else:
        next = mock.Mock(return_value=None)


def builtin_target(obj):
    """Returns mock target string of a builtin"""
    return '%s.%s' % (builtins.__name__, obj.__name__)
