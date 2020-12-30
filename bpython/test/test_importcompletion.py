import unittest

from bpython.importcompletion import ModuleGatherer


class TestSimpleComplete(unittest.TestCase):
    def setUp(self):
        self.module_gatherer = ModuleGatherer()
        self.module_gatherer.modules = [
            "zzabc",
            "zzabd",
            "zzefg",
            "zzabc.e",
            "zzabc.f",
        ]

    def test_simple_completion(self):
        self.assertSetEqual(
            self.module_gatherer.complete(10, "import zza"), {"zzabc", "zzabd"}
        )

    def test_package_completion(self):
        self.assertSetEqual(
            self.module_gatherer.complete(13, "import zzabc."),
            {"zzabc.e", "zzabc.f"},
        )


class TestRealComplete(unittest.TestCase):
    def setUp(self):
        self.module_gatherer = ModuleGatherer()
        while self.module_gatherer.find_coroutine():
            pass
        __import__("sys")
        __import__("os")

    def test_from_attribute(self):
        self.assertSetEqual(
            self.module_gatherer.complete(19, "from sys import arg"), {"argv"}
        )

    def test_from_attr_module(self):
        self.assertSetEqual(
            self.module_gatherer.complete(9, "from os.p"), {"os.path"}
        )

    def test_from_package(self):
        self.assertSetEqual(
            self.module_gatherer.complete(17, "from xml import d"), {"dom"}
        )
