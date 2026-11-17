import unittest
import unittest.mock
from pathlib import Path


class MagicIterMock(unittest.mock.MagicMock):
    __next__ = unittest.mock.Mock(return_value=None)


TEST_CONFIG = Path(__file__).parent / "test.config"
