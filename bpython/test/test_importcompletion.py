from bpython import importcompletion
from bpython.test import unittest


class TestSimpleComplete(unittest.TestCase):
    def setUp(self):
        self.original_modules = importcompletion.modules
        importcompletion.modules = [
            "zzabc",
            "zzabd",
            "zzefg",
            "zzabc.e",
            "zzabc.f",
        ]

    def tearDown(self):
        importcompletion.modules = self.original_modules

    def test_simple_completion(self):
        self.assertSetEqual(
            importcompletion.complete(10, "import zza"), {"zzabc", "zzabd"}
        )

    def test_package_completion(self):
        self.assertSetEqual(
            importcompletion.complete(13, "import zzabc."),
            {"zzabc.e", "zzabc.f"},
        )


class TestRealComplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for _ in importcompletion.find_iterator:
            pass
        __import__("sys")
        __import__("os")

    @classmethod
    def tearDownClass(cls):
        importcompletion.find_iterator = importcompletion.find_all_modules()
        importcompletion.modules = set()

    def test_from_attribute(self):
        self.assertSetEqual(
            importcompletion.complete(19, "from sys import arg"), {"argv"}
        )

    def test_from_attr_module(self):
        self.assertSetEqual(
            importcompletion.complete(9, "from os.p"), {"os.path"}
        )

    def test_from_package(self):
        self.assertSetEqual(
            importcompletion.complete(17, "from xml import d"), {"dom"}
        )
