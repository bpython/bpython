from bpython.importcompletion import find_modules
import os

foo = find_modules(os.path.abspath("./importtestfolder"))

for thing in foo:
    print("YIELD:", thing)