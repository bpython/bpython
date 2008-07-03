#!/usr/bin/env python
from distutils.command.install_data import install_data
from distutils.sysconfig import get_python_lib
from distutils.core import setup, Extension
from distutils.dep_util import newer
from distutils.log import info
from distutils import sysconfig
import distutils.file_util
import distutils.dir_util
import sys, os
import glob
import re

# Make distutils copy bpython.py to bpython
copy_file_orig = distutils.file_util.copy_file
copy_tree_orig = distutils.dir_util.copy_tree
def copy_file(src, dst, *args, **kwargs):
    if dst.endswith("bin/bpython.py"):
        dst = dst[:-3]
    return copy_file_orig(src, dst, *args, **kwargs)
def copy_tree(*args, **kwargs):
    outputs = copy_tree_orig(*args, **kwargs)
    for i in range(len(outputs)):
        if outputs[i].endswith("bin/bpython.py"):
            outputs[i] = outputs[i][:-3]
    return outputs
distutils.file_util.copy_file = copy_file
distutils.dir_util.copy_tree = copy_tree

PYTHONLIB = os.path.join(get_python_lib(standard_lib=1, prefix=""),
                         "site-packages")

setup(name="bpython",
      version = "0.6.4",
      description = "Fancy Interface to the Python Interpreter",
      author = "Robert Anthony Farrell",
      author_email = "robertanthonyfarrell@gmail.com",
      license = "MIT/X",
		url = "http://www.noiseforfree.com/bpython/",
      long_description =
"""\
bpython is a fancy interface to the Python interpreter for Unix-like operating systems.
""",
      packages = ["bpython"],
      scripts = ["bpython.py"],
      )


