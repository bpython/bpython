#!/usr/bin/env python
# -*- coding: utf-8 -*-


import glob
import os
import os.path
import platform
import re
import sys

from distutils import cmd
from distutils.command.install_data import install_data as _install_data
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
        src_path = os.path.join(os.path.realpath(''), 'po')
        for filename in os.listdir(src_path):
            if (not os.path.isfile(os.path.join(src_path, filename)) or
                not filename.endswith('.po')):
                continue

            lang = filename[:-3]
            dest_path = os.path.join('build', 'locale', lang, 'LC_MESSAGES')

            src = os.path.join(src_path, filename)
            dest = os.path.join(dest_path, 'bpython.mo')

            if not os.path.exists(dest_path):
                os.makedirs(dest_path)
            if (not os.path.exists(dest) or
                os.stat(src)[8] > os.stat(dest)[8]):
                print ('Adding translation: %s' % lang)
                msgfmt.make(src, dest)

build.sub_commands.append(('build_translation', None))


class install_data(_install_data):
    """Append to data_files l10n .mo files. Then continue with normal install."""

    def run(self):
        for lang in os.listdir('po'):
            if not lang.endswith('.mo'):
                continue

            lang_dir = os.path.join('share', 'locale', lang[:-3], 'LC_MESSAGES')
            lang_file = os.path.join('po', lang)
            self.data_files.append((lang_dir, [lang_file]))

        _install_data.run(self)

build.sub_commands.append(('install_data', None))


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
    data_files = [
        # man pages
        (os.path.join(man_dir, 'man1'), ['doc/bpython.1']),
        (os.path.join(man_dir, 'man5'), ['doc/bpython-config.5']),
        # desktop shorcut
        (os.path.join('share', 'applications'), ['data/bpython.desktop'])
    ],
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
                  build_translation = build_translation,
                  install_data = install_data)
)

# vim: encoding=utf-8 sw=4 ts=4 sts=4 ai et sta
