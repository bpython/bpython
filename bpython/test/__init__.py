try:
    import unittest2 as unittest
except ImportError:
    import unittest

from bpython.translations import init

class FixLanguageTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init(languages=['en'])
