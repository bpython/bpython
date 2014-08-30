import os
import sys
import unittest
from mock import Mock, MagicMock
try:
    from unittest import skip
except ImportError:
    def skip(f):
        return lambda self: None

from bpython import config, repl, cli, autocomplete

class TestFutureImports(unittest.TestCase):

    def test_interactive(self):
        pass

