import unittest
import unittest.mock
import os

from bpython.translations import init


class FixLanguageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init(languages=["en"])


class MagicIterMock(unittest.mock.MagicMock):

    __next__ = unittest.mock.Mock(return_value=None)


TEST_CONFIG = os.path.join(os.path.dirname(__file__), "test.config")
