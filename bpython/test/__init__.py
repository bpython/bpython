# -*- coding: utf-8 -*-

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from mock import MagicMock, Mock

from bpython.translations import init
from bpython._py3compat import py3


class FixLanguageTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init(languages=['en'])


class MagicIterMock(MagicMock):

    if py3:
        __next__ = Mock(return_value=None)
    else:
        next = Mock(return_value=None)
