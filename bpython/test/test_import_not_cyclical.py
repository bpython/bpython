import os
import tempfile

from bpython.test import unittest
from bpython.importcompletion import find_modules


class TestAvoidSymbolicLinks(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as import_test_folder:
            os.mkdir(os.path.join(import_test_folder, "Level0"))
            os.mkdir(os.path.join(import_test_folder, "Right"))
            os.mkdir(os.path.join(import_test_folder, "Left"))

            current_path = os.path.join(import_test_folder, "Level0")
            with open(
                os.path.join(current_path, "__init__.py"), "x"
            ) as init_file:
                pass

            current_path = os.path.join(current_path, "Level1")
            os.mkdir(current_path)
            with open(
                os.path.join(current_path, "__init__.py"), "x"
            ) as init_file:
                pass

            current_path = os.path.join(current_path, "Level2")
            os.mkdir(current_path)
            with open(
                os.path.join(current_path, "__init__.py"), "x"
            ) as init_file:
                pass

            os.symlink(
                os.path.join(import_test_folder, "Level0/Level1"),
                os.path.join(current_path, "Level3"),
                True,
            )

            current_path = os.path.join(import_test_folder, "Right")
            with open(
                os.path.join(current_path, "__init__.py"), "x"
            ) as init_file:
                pass

            os.symlink(
                os.path.join(import_test_folder, "Left"),
                os.path.join(current_path, "toLeft"),
                True,
            )

            current_path = os.path.join(import_test_folder, "Left")
            with open(
                os.path.join(current_path, "__init__.py"), "x"
            ) as init_file:
                pass

            os.symlink(
                os.path.join(import_test_folder, "Right"),
                os.path.join(current_path, "toRight"),
                True,
            )

            self.modules = list(
                find_modules(os.path.abspath(import_test_folder))
            )
            self.filepaths = [
                "Left.toRight.toLeft",
                "Left.toRight",
                "Left",
                "Level0.Level1.Level2.Level3",
                "Level0.Level1.Level2",
                "Level0.Level1",
                "Level0",
                "Right",
                "Right.toLeft",
                "Right.toLeft.toRight",
            ]

    def test_simple_symbolic_link_loop(self):
        for thing in self.modules:
            self.assertTrue(thing in self.filepaths)
            if thing == "Left.toRight.toLeft":
                self.filepaths.remove("Right.toLeft")
                self.filepaths.remove("Right.toLeft.toRight")
            if thing == "Right.toLeft.toRight":
                self.filepaths.remove("Left.toRight.toLeft")
                self.filepaths.remove("Left.toRight")
            self.filepaths.remove(thing)
        self.assertFalse(self.filepaths)


if __name__ == "__main__":
    unittest.main()
