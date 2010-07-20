#!/usr/bin/env python
# -*- coding: utf-8 -*-


import glob
import os
import os.path
import platform
import re
import sys

from distutils import cmd
from distutils.command.build import build

from bpython import __version__

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
    import msgfmt
except ImportError:
    pass

if platform.system() == 'FreeBSD':
    man_dir = 'man'
else:
    man_dir = 'share/man'



class build_translation(cmd.Command):
    """Internationalization suport for bpython.
    Compile .po files into .mo files"""

    description = __doc__
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        for src in glob.iglob(os.path.join('po', '[a-z][a-z]_[A-Z][A-Z].po')):

            # remove 'po/' (the directory) and '.po' (the extension)
            lang = src[3:-3]
            dest_path = os.path.join('build', 'share', 'locale',
                                     lang, 'LC_MESSAGES', '')
            dest = dest_path + 'bpython.mo'

            if not os.path.exists(dest_path):
                os.makedirs(dest_path)
            if (not os.path.exists(dest) or
                os.stat(src)[8] > os.stat(dest)[8]):
                print ('Adding translation: %s' % lang)
                msgfmt.make(src, dest)

build.sub_commands.insert(0, ('build_translation', None))


data_files = [
        # man pages
        (os.path.join(man_dir, 'man1'), ['doc/bpython.1']),
        (os.path.join(man_dir, 'man5'), ['doc/bpython-config.5']),
        # desktop shorcut
        (os.path.join('share', 'applications'), ['data/bpython.desktop']),
]
# localization
for langfile in glob.iglob(os.path.join('po', '[a-z][a-z]_[A-Z][A-Z].po')):
    lang_path = os.path.join('share', 'locale', langfile[3:-3], 'LC_MESSAGES')
    data_files.append((lang_path, ['build/%s/bpython.mo' % lang_path]))


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
    packages = ["bpython"],
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
    cmdclass=dict(build_py=build_py,
                  build = build,
                  build_translation = build_translation)
)

# vim: encoding=utf-8 sw=4 ts=4 sts=4 ai et sta
