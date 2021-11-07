import inspect
import os
import sys
import unittest

from bpython import inspection
from bpython.test.fodder import encoding_ascii
from bpython.test.fodder import encoding_latin1
from bpython.test.fodder import encoding_utf8

pypy = "PyPy" in sys.version

try:
    import numpy
except ImportError:
    numpy = None  # type: ignore


foo_ascii_only = '''def foo():
    """Test"""
    pass
'''

foo_non_ascii = '''def foo():
    """Test äöü"""
    pass
'''


class Callable:
    def __call__(self):
        pass


class Noncallable:
    pass


def spam():
    pass


class CallableMethod:
    def method(self):
        pass


class TestInspection(unittest.TestCase):
    def test_parsekeywordpairs(self):
        # See issue #109
        def fails(spam=["-a", "-b"]):
            pass

        default_arg_repr = "['-a', '-b']"
        self.assertEqual(
            str(["-a", "-b"]),
            default_arg_repr,
            "This test is broken (repr does not match), fix me.",
        )

        argspec = inspection.getfuncprops("fails", fails)
        defaults = argspec.argspec.defaults
        self.assertEqual(str(defaults[0]), default_arg_repr)

    def test_pasekeywordpairs_string(self):
        def spam(eggs="foo, bar"):
            pass

        defaults = inspection.getfuncprops("spam", spam).argspec.defaults
        self.assertEqual(repr(defaults[0]), "'foo, bar'")

    def test_parsekeywordpairs_multiple_keywords(self):
        def spam(eggs=23, foobar="yay"):
            pass

        defaults = inspection.getfuncprops("spam", spam).argspec.defaults
        self.assertEqual(repr(defaults[0]), "23")
        self.assertEqual(repr(defaults[1]), "'yay'")

    def test_get_encoding_ascii(self):
        self.assertEqual(inspection.get_encoding(encoding_ascii), "ascii")
        self.assertEqual(inspection.get_encoding(encoding_ascii.foo), "ascii")

    def test_get_encoding_latin1(self):
        self.assertEqual(inspection.get_encoding(encoding_latin1), "latin1")
        self.assertEqual(inspection.get_encoding(encoding_latin1.foo), "latin1")

    def test_get_encoding_utf8(self):
        self.assertEqual(inspection.get_encoding(encoding_utf8), "utf-8")
        self.assertEqual(inspection.get_encoding(encoding_utf8.foo), "utf-8")

    def test_get_source_ascii(self):
        self.assertEqual(inspect.getsource(encoding_ascii.foo), foo_ascii_only)

    def test_get_source_utf8(self):
        self.assertEqual(inspect.getsource(encoding_utf8.foo), foo_non_ascii)

    def test_get_source_latin1(self):
        self.assertEqual(inspect.getsource(encoding_latin1.foo), foo_non_ascii)

    def test_get_source_file(self):
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "fodder"
        )

        encoding = inspection.get_encoding_file(
            os.path.join(path, "encoding_ascii.py")
        )
        self.assertEqual(encoding, "ascii")
        encoding = inspection.get_encoding_file(
            os.path.join(path, "encoding_latin1.py")
        )
        self.assertEqual(encoding, "latin1")
        encoding = inspection.get_encoding_file(
            os.path.join(path, "encoding_utf8.py")
        )
        self.assertEqual(encoding, "utf-8")

    @unittest.skipIf(pypy, "pypy builtin signatures aren't complete")
    def test_getfuncprops_print(self):
        props = inspection.getfuncprops("print", print)

        self.assertEqual(props.func, "print")
        self.assertIn("end", props.argspec.kwonly)
        self.assertIn("file", props.argspec.kwonly)
        self.assertIn("flush", props.argspec.kwonly)
        self.assertIn("sep", props.argspec.kwonly)
        self.assertEqual(props.argspec.kwonly_defaults["file"], "sys.stdout")
        self.assertEqual(props.argspec.kwonly_defaults["flush"], "False")

    @unittest.skipUnless(
        numpy is not None and numpy.__version__ >= "1.18",
        "requires numpy >= 1.18",
    )
    def test_getfuncprops_numpy_array(self):
        props = inspection.getfuncprops("array", numpy.array)

        self.assertEqual(props.func, "array")
        # This check might need an update in the future, but at least numpy >= 1.18 has
        # np.array(object, dtype=None, *, ...).
        self.assertEqual(props.argspec.args, ["object", "dtype"])


class A:
    a = "a"


class B(A):
    b = "b"


class Property:
    @property
    def prop(self):
        raise AssertionError("Property __get__ executed")


class Slots:
    __slots__ = ["s1", "s2", "s3"]


class SlotsSubclass(Slots):
    @property
    def s4(self):
        raise AssertionError("Property __get__ executed")


class OverriddenGetattr:
    def __getattr__(self, attr):
        raise AssertionError("custom __getattr__ executed")

    a = 1


class OverriddenGetattribute:
    def __getattribute__(self, attr):
        raise AssertionError("custom __getattribute__ executed")

    a = 1


class OverriddenMRO:
    def __mro__(self):
        raise AssertionError("custom mro executed")

    a = 1


member_descriptor = type(Slots.s1)  # type: ignore


class TestSafeGetAttribute(unittest.TestCase):
    def test_lookup_on_object(self):
        a = A()
        a.x = 1
        self.assertEqual(inspection.getattr_safe(a, "x"), 1)
        self.assertEqual(inspection.getattr_safe(a, "a"), "a")
        b = B()
        b.y = 2
        self.assertEqual(inspection.getattr_safe(b, "y"), 2)
        self.assertEqual(inspection.getattr_safe(b, "a"), "a")
        self.assertEqual(inspection.getattr_safe(b, "b"), "b")

        self.assertEqual(inspection.hasattr_safe(b, "y"), True)
        self.assertEqual(inspection.hasattr_safe(b, "b"), True)

    def test_avoid_running_properties(self):
        p = Property()
        self.assertEqual(inspection.getattr_safe(p, "prop"), Property.prop)
        self.assertEqual(inspection.hasattr_safe(p, "prop"), True)

    def test_lookup_with_slots(self):
        s = Slots()
        s.s1 = "s1"
        self.assertEqual(inspection.getattr_safe(s, "s1"), "s1")
        with self.assertRaises(AttributeError):
            inspection.getattr_safe(s, "s2")

        self.assertEqual(inspection.hasattr_safe(s, "s1"), True)
        self.assertEqual(inspection.hasattr_safe(s, "s2"), False)

    def test_lookup_on_slots_classes(self):
        sga = inspection.getattr_safe
        s = SlotsSubclass()
        self.assertIsInstance(sga(Slots, "s1"), member_descriptor)
        self.assertIsInstance(sga(SlotsSubclass, "s1"), member_descriptor)
        self.assertIsInstance(sga(SlotsSubclass, "s4"), property)
        self.assertIsInstance(sga(s, "s4"), property)

        self.assertEqual(inspection.hasattr_safe(s, "s1"), False)
        self.assertEqual(inspection.hasattr_safe(s, "s4"), True)

    def test_lookup_on_overridden_methods(self):
        sga = inspection.getattr_safe
        self.assertEqual(sga(OverriddenGetattr(), "a"), 1)
        self.assertEqual(sga(OverriddenGetattribute(), "a"), 1)
        self.assertEqual(sga(OverriddenMRO(), "a"), 1)
        with self.assertRaises(AttributeError):
            sga(OverriddenGetattr(), "b")
        with self.assertRaises(AttributeError):
            sga(OverriddenGetattribute(), "b")
        with self.assertRaises(AttributeError):
            sga(OverriddenMRO(), "b")

        self.assertEqual(
            inspection.hasattr_safe(OverriddenGetattr(), "b"), False
        )
        self.assertEqual(
            inspection.hasattr_safe(OverriddenGetattribute(), "b"), False
        )
        self.assertEqual(inspection.hasattr_safe(OverriddenMRO(), "b"), False)


if __name__ == "__main__":
    unittest.main()
