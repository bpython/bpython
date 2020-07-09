from bpython.test import unittest
from bpython.importcompletion import find_modules
import os, sys, tempfile

if sys.version_info[0] > 2:
    class TestAvoidSymbolicLinks(unittest.TestCase):
        def setUp(self):
            with tempfile.TemporaryDirectory() as import_test_folder:
                os.chdir(import_test_folder)

                os.mkdir(os.path.join(os.getcwd(), "Level0"))
                os.mkdir(os.path.join(os.getcwd(), "Right"))
                os.mkdir(os.path.join(os.getcwd(), "Left"))
                
                os.chdir("Level0")
                with open("__init__.py", "w") as init_file:
                    pass

                os.mkdir(os.path.join(os.getcwd(), "Level1"))
                os.chdir("Level1")
                with open("__init__.py", "w") as init_file:
                    pass

                os.mkdir(os.path.join(os.getcwd(), "Level2"))
                os.chdir("Level2")
                with open("__init__.py", "w") as init_file:
                    pass

                os.symlink(
                    "import_test_folder/Level0/Level1",
                    os.path.join(os.getcwd(), "Level3"),
                    True,
                )

                os.chdir(import_test_folder)

                os.chdir("Right")
                with open("__init__.py", "w") as init_file:
                    pass

                os.symlink(
                    "import_test_folder/Left",
                    os.path.join(os.getcwd(), "toLeft"),
                    True,
                )

                os.chdir(import_test_folder)

                os.chdir("Left")
                with open("__init__.py", "w") as init_file:
                    pass

                os.symlink(
                    "import_test_folder/Right",
                    os.path.join(os.getcwd(), "toRight"),
                    True,
                )

                self.foo = list(find_modules(os.path.abspath(import_test_folder)))
                self.filepaths = [
                    "Left",
                    "Level0.Level1.Level2",
                    "Level0.Level1",
                    "Level0",
                    "Right"
                ]

        def test_simple_symbolic_link_loop(self):
            for thing in self.foo:
                self.assertTrue(thing in self.filepaths)
                self.filepaths.remove(thing)

else:
    @unittest.skip("test doesn't work in python 2")
    def test_skip():
        pass


if __name__ == "__main__":
    unittest.main()
