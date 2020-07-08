from bpython.test import unittest
from bpython.importcompletion import find_modules
import os, sys, tempfile


class TestAvoidSymbolicLinks(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as import_test_folder:
            try:
                os.chdir(import_test_folder)
            except:
                print("Can't change the Current Working Directory")
                import_test_folder.cleanup()
                sys.exit()

            os.mkdir(os.path.join(os.getcwd(), "Level0"))
            os.mkdir(os.path.join(os.getcwd(), "Right"))
            os.mkdir(os.path.join(os.getcwd(), "Left"))
            try:
                os.chdir("Level0")
                with open("__init__.py", "w") as init_file:
                    init_file.close()
            except OSError:
                print("Can't change the Current Working Directory")
                sys.exit()

            os.mkdir(os.path.join(os.getcwd(), "Level1"))
            try:
                os.chdir("Level1")
                with open("__init__.py", "w") as init_file:
                    init_file.close()
            except OSError:
                print("Can't change the Current Working Directory")
                sys.exit()

            os.mkdir(os.path.join(os.getcwd(), "Level2"))
            try:
                os.chdir("Level2")
                with open("__init__.py", "w") as init_file:
                    init_file.close()
            except OSError:
                print("Can't change the Current Working Directory")
                sys.exit()

            os.symlink(
                "import_test_folder/Level0/Level1",
                os.path.join(os.getcwd(), "Level3"),
                True,
            )

            try:
                os.chdir(import_test_folder)
            except:
                print("Can't change the Current Working Directory")
                sys.exit()

            try:
                os.chdir("Right")
                with open("__init__.py", "w") as init_file:
                    init_file.close()
            except OSError:
                print("Can't change the Current Working Directory")
                sys.exit()

            os.symlink(
                "import_test_folder/Left",
                os.path.join(os.getcwd(), "toLeft"),
                True,
            )

            try:
                os.chdir(import_test_folder)
            except:
                print("Can't change the Current Working Directory")
                sys.exit()

            try:
                os.chdir("Left")
                with open("__init__.py", "w") as init_file:
                    init_file.close()
            except OSError:
                print("Can't change the Current Working Directory")
                sys.exit()

            os.symlink(
                "import_test_folder/Right",
                os.path.join(os.getcwd(), "toRight"),
                True,
            )

            self.foo = list(find_modules(os.path.abspath(import_test_folder)))
            self.counter = 0
            self.filepaths = [
                "Left",
                "Level0.Level1.Level2",
                "Level0.Level1",
                "Level0",
                "Right",
            ]

    def test_simple_symbolic_link_loop(self):
        for thing in self.foo:
            self.assertEqual(thing, self.filepaths[self.counter])
            self.counter = self.counter + 1


if __name__ == "__main__":
    unittest.main()
