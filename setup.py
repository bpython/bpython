#!/usr/bin/env python
# -*- coding: utf-8 -*-


import glob
import os
import platform
import re
import sys
try:
    from setuptools import setup
    using_setuptools = True
except ImportError:
    from distutils.core import setup
    using_setuptools = False

try:
    from distutils.command.build_py import build_py_2to3 as build_py
except ImportError:
    from distutils.command.build_py import build_py

from bpython import __version__


if platform.system() == 'FreeBSD':
    man_dir = 'man'
else:
    man_dir = 'share/man'

setup(
    name="bpython",
    version = __version__,
    author = "Robert Anthony Farrell et al.",
    author_email = "robertanthonyfarrell@gmail.com",
    description = "Fancy Interface to the Python Interpreter",
    license = "MIT/X",
    url = "http://www.bpython-interpreter.org/",
    long_description = """bpython is a fancy interface to the Python
    interpreter for Unix-like operating systems.""",
    install_requires = [
        'pygments'
    ],
    packages = ["bpython"],
    data_files = [
        (os.path.join(man_dir, 'man1'), ['doc/bpython.1']),
        (os.path.join(man_dir, 'man5'), ['doc/bpython-config.5']),
        ('share/applications', ['data/bpython.desktop'])
    ],
    entry_points = {
        'console_scripts': [
            'bpython = bpython.cli:main',
        ],
    },
    scripts = ([] if using_setuptools else ['data/bpython']),
    cmdclass=dict(build_py=build_py)
)

# vim: encoding=utf-8 sw=4 ts=4 sts=4 ai et sta
