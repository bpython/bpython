#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import os.path
import platform
import re
import sys
from fnmatch import fnmatch

from distutils import cmd
from distutils.command.build import build

from bpython import __version__, package_dir

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

try:
    from babel.messages.frontend import compile_catalog as _compile_catalog
    from babel.messages.frontend import extract_messages

    translations_dir = os.path.join(package_dir, 'translations')

    class compile_catalog(_compile_catalog):
        def initialize_options(self):
            """Simply set default domain and directory attributes to the
            correct path for bpython."""
            _compile_catalog.initialize_options(self)

            self.domain = 'bpython'
            self.directory = translations_dir
            self.use_fuzzy = True

    build.sub_commands.append(('compile_catalog', None))
    using_translations = True
except ImportError:
    using_translations = False

if platform.system() == 'FreeBSD':
    man_dir = 'man'
else:
    man_dir = 'share/man'


data_files = [
        # man pages
        (os.path.join(man_dir, 'man1'), ['doc/bpython.1']),
        (os.path.join(man_dir, 'man5'), ['doc/bpython-config.5']),
        # desktop shorcut
        (os.path.join('share', 'applications'), ['data/bpython.desktop']),
]
# localization
if using_translations:
    for lang in os.listdir(translations_dir):
        if fnmatch(lang, '??_??'):
            data_files.append((os.path.join('share', 'locale', lang, 'LC_MESSAGES'),
                               ['%s/%s/LC_MESSAGES/bpython.mo' %
                                (translations_dir, lang)]))

cmdclass = dict(build_py=build_py,
                build = build)
# localization options
if using_translations:
    cmdclass['compile_catalog'] = compile_catalog
    cmdclass['extract_messages'] = extract_messages

setup(
    name="bpython",
    version = __version__,
    author = "Bob Farrell, Andreas Stuehrk et al.",
    author_email = "robertanthonyfarrell@gmail.com",
    description = "Fancy Interface to the Python Interpreter",
    license = "MIT/X",
    url = "http://www.bpython-interpreter.org/",
    long_description = """bpython is a fancy interface to the Python
    interpreter for Unix-like operating systems.""",
    install_requires = [
        'pygments'
    ],
    packages = ["bpython", "bpython.translations", "bpdb"],
    data_files = data_files,
    package_data = {'bpython': ['logo.png']},
    entry_points = {
        'console_scripts': [
            'bpython = bpython.cli:main',
            'bpython-gtk = bpython.gtk_:main',
        ],
    },
    scripts = ([] if using_setuptools else ['data/bpython',
                                            'data/bpython-gtk']),
    cmdclass = cmdclass
)

# vim: encoding=utf-8 sw=4 ts=4 sts=4 ai et sta
