#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import platform
import sys

from distutils.command.build import build

from bpython import __version__, package_dir

try:
    from setuptools import setup
    from setuptools.command.install import install as _install
    using_setuptools = True
except ImportError:
    from distutils.core import setup
    from distutils.command.install import install as _install
    using_setuptools = False

try:
    from distutils.command.build_py import build_py_2to3 as build_py
except ImportError:
    from distutils.command.build_py import build_py

try:
    from babel.messages.frontend import compile_catalog as _compile_catalog
    from babel.messages.frontend import extract_messages as _extract_messages
    from babel.messages.frontend import update_catalog as _update_catalog
    from babel.messages.frontend import init_catalog as _init_catalog
    using_translations = True
except ImportError:
    using_translations = False

try:
    import sphinx
    from sphinx.setup_command import BuildDoc
    if sphinx.__version__ == '1.1.2':
        # Sphinx 1.1.2 is buggy and building bpython with that version fails.
        # See #241.
        using_sphinx = False
    else:
        using_sphinx = True
except ImportError:
    using_sphinx = False

class install(_install):
    """Force install to run build target."""

    def run(self):
        self.run_command('build')
        _install.run(self)

cmdclass = dict(build_py=build_py, build=build, install=install)
translations_dir = os.path.join(package_dir, 'translations')

# localization options
if using_translations:
    class compile_catalog(_compile_catalog):
        def initialize_options(self):
            """Simply set default domain and directory attributes to the
            correct path for bpython."""
            _compile_catalog.initialize_options(self)

            self.domain = 'bpython'
            self.directory = translations_dir
            self.use_fuzzy = True

    class update_catalog(_update_catalog):
        def initialize_options(self):
            """Simply set default domain and directory attributes to the
            correct path for bpython."""
            _update_catalog.initialize_options(self)

            self.domain = 'bpython'
            self.output_dir = translations_dir
            self.input_file = os.path.join(translations_dir, 'bpython.pot')

    class extract_messages(_extract_messages):
        def initialize_options(self):
            """Simply set default domain and output file attributes to the
            correct values for bpython."""
            _extract_messages.initialize_options(self)

            self.domain = 'bpython'
            self.output_file = os.path.join(translations_dir, 'bpython.pot')

    class init_catalog(_init_catalog):
        def initialize_options(self):
            """Simply set default domain, input file and output directory
            attributes to the correct values for bpython."""
            _init_catalog.initialize_options(self)

            self.domain = 'bpython'
            self.output_dir = translations_dir
            self.input_file = os.path.join(translations_dir, 'bpython.pot')

    build.sub_commands.insert(0, ('compile_catalog', None))

    cmdclass['compile_catalog'] = compile_catalog
    cmdclass['extract_messages'] = extract_messages
    cmdclass['update_catalog'] = update_catalog
    cmdclass['init_catalog'] = init_catalog

if using_sphinx:
    class BuildDocMan(BuildDoc):
        def initialize_options(self):
            BuildDoc.initialize_options(self)
            self.builder = 'man'
            self.source_dir = 'doc/sphinx/source'
            self.build_dir = 'build'

    build.sub_commands.insert(0, ('build_sphinx_man', None))
    cmdclass['build_sphinx_man'] = BuildDocMan

    if platform.system() in ['FreeBSD', 'OpenBSD']:
        man_dir = 'man'
    else:
        man_dir = 'share/man'

    # manual pages
    man_pages = [
        (os.path.join(man_dir, 'man1'), ['build/man/bpython.1']),
        (os.path.join(man_dir, 'man5'), ['build/man/bpython-config.5']),
    ]
else:
    man_pages = []

data_files = [
    # desktop shortcut
    (os.path.join('share', 'applications'), ['data/bpython.desktop'])
]
data_files.extend(man_pages)

install_requires = [
    'pygments',
    'requests'
]

extras_require = {
    'urwid' : ['urwid']
}

packages = ['bpython', 'bpython.test', 'bpython.translations', 'bpdb']

entry_points = {
    'console_scripts': [
        'bpython = bpython.cli:main',
        'bpython-urwid = bpython.urwid:main [urwid]'
    ],
    'gui_scripts': [
        'bpython-gtk = bpython.gtk_:main'
    ]
}

scripts = [] if using_setuptools else ['data/bpython',
                                       'data/bpython-gtk',
                                       'data/bpython-urwid']

if sys.version_info[:2] >= (2, 6):
    # curtsies only supports 2.6 and onwards
    extras_require['curtsies'] = ['curtsies >=0.0.34, <0.1.0', 'greenlet']
    packages.append("bpython.curtsiesfrontend")
    entry_points['console_scripts'].append(
        'bpython-curtsies = bpython.curtsies:main [curtsies]')
    if not using_setuptools:
        scripts.append('data/bpython-curtsies')

if sys.version_info[0] == 2 and sys.platform == "darwin":
    # need PyOpenSSL for SNI support (only 2.X and on Darwin)
    # list of packages taken from
    # https://github.com/kennethreitz/requests/blob/master/requests/packages/urllib3/contrib/pyopenssl.py
    install_requires.append('PyOpenSSL')
    install_requires.append('ndg-httpsclient')
    install_requires.append('pyasn1')

tests_require = ['mock']
if sys.version_info[0] == 2 and sys.version_info[1] < 7:
    tests_require.append('unittest2')

# translations
mo_files = list()
for language in os.listdir(translations_dir):
    mo_subpath = os.path.join(language, 'LC_MESSAGES', 'bpython.mo')
    if os.path.exists(os.path.join(translations_dir, mo_subpath)):
        mo_files.append(mo_subpath)

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
    install_requires = install_requires,
    extras_require = extras_require,
    tests_require = tests_require,
    packages = packages,
    data_files = data_files,
    package_data = {
        'bpython': ['logo.png'],
        'bpython.translations': mo_files,
        'bpython.test': ['test.config', 'test.theme']
    },
    entry_points = entry_points,
    scripts = scripts,
    cmdclass = cmdclass,
    test_suite = 'bpython.test'
)

# vim: fileencoding=utf-8 sw=4 ts=4 sts=4 ai et sta
