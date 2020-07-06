from bpython.importcompletion import find_modules
import os, sys, tempfile

with tempfile.TemporaryDirectory() as import_test_folder:
    try:
        os.chdir(import_test_folder)
    except:
        print("Can't change the Current Working Directory")
        sys.exit()

    os.mkdir(os.path.join(os.getcwd(), "Level0")
    try:
        os.chdir(Level0)
        open("__init__.py", w)
    except OSError:
        print("Can't change the Current Working Directory")
        sys.exit()

    os.mkdir(os.path.join(os.getcwd(), "Level1")
    try:
        os.chdir(Level1)
        open("__init__.py", w)
    except OSError:
        print("Can't change the Current Working Directory")
        sys.exit()

    os.mkdir(os.path.join(os.getcwd(), "Level2")
    try:
        os.chdir(Level2)
        open("__init__.py", w)
    except OSError:
        print("Can't change the Current Working Directory")
        sys.exit()

    os.symlink(
        "import_test_folder/Level0/Level1",
        os.path.join(os.getcwd, "Level3"),
        True,
    )

    foo = find_modules(os.path.abspath("import_test_folder"))

    for thing in foo:
        print("YIELD:", thing)
