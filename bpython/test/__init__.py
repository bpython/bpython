import unittest
import builtins
from unittest import mock

from bpython.translations import init
import os


class FixLanguageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init(languages=["en"])


class MagicIterMock(mock.MagicMock):

    __next__ = mock.Mock(return_value=None)


def builtin_target(obj):
    """Returns mock target string of a builtin"""
    return f"{builtins.__name__}.{obj.__name__}"


TEST_CONFIG = os.path.join(os.path.dirname(__file__), "test.config")
