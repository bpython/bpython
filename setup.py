#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import platform
import re
import subprocess
import sys

from distutils.command.build import build
from setuptools import setup
from setuptools.command.install import install as _install

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

    # Sphinx 1.1.2 is buggy and building bpython with that version fails.
    # See #241.
    using_sphinx = sphinx.__version__ >= "1.1.3"
except ImportError:
    using_sphinx = False


# version handling


def git_describe_to_python_version(version):
    """Convert output from git describe to PEP 440 conforming versions."""

    version_info = version.split("-")
    if len(version_info) < 2:
        return "unknown"

    # we always have $version-$release
    release_type = version_info[1]

    version_data = {
        "version": version_info[0],
        "release_type": release_type,
    }
    if len(version_info) == 4:
        version_data["commits"] = version_info[2]
    else:
        version_data["commits"] = 0

    if release_type == "release":
        if len(version_info) == 2:
            # format: $version-release
            # This is the case at time of the release.
            fmt = "{version}"
        elif len(version_info) == 4:
            # format: $version-release-$commits-$hash
            # This is the case after a release.
            fmt = "{version}-{commits}"
    elif release_type == "dev":
        # format: $version-dev-$commits-$hash or $version-dev
        fmt = "{version}.dev{commits}"
    else:
        match = re.match(r"^(alpha|beta|rc)(\d*)$", release_type)
        if match is None:
            return "unknown"

        if len(version_info) == 2:
            fmt = "{version}{release_type}"
        elif len(version_info) == 4:
            fmt = "{version}{release_type}-{commits}"

    return fmt.format(**version_data)


version_file = "bpython/_version.py"
version = "unknown"

try:
    # get version from git describe
    proc = subprocess.Popen(
        ["git", "describe", "--tags"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout = proc.communicate()[0].strip()
    if sys.version_info[0] > 2:
        stdout = stdout.decode("ascii")

    if proc.returncode == 0:
        version = git_describe_to_python_version(stdout)
except OSError:
    pass

if version == "unknown":
    try:
        # get version from existing version file
        with open(version_file) as vf:
            version = vf.read().strip().split("=")[-1].replace("'", "")
        version = version.strip()
    except IOError:
        pass

with open(version_file, "w") as vf:
    vf.write("# Auto-generated file, do not edit!\n")
    vf.write("__version__ = '%s'\n" % (version,))


class install(_install):
    """Force install to run build target."""

    def run(self):
        self.run_command("build")
        _install.run(self)


cmdclass = {"build": build, "install": install}

from bpython import package_dir

translations_dir = os.path.join(package_dir, "translations")

# localization options
if using_translations:

    class compile_catalog(_compile_catalog):
        def initialize_options(self):
            """Simply set default domain and directory attributes to the
            correct path for bpython."""
            _compile_catalog.initialize_options(self)

            self.domain = "bpython"
            self.directory = translations_dir
            self.use_fuzzy = True

    class update_catalog(_update_catalog):
        def initialize_options(self):
            """Simply set default domain and directory attributes to the
            correct path for bpython."""
            _update_catalog.initialize_options(self)

            self.domain = "bpython"
            self.output_dir = translations_dir
            self.input_file = os.path.join(translations_dir, "bpython.pot")

    class extract_messages(_extract_messages):
        def initialize_options(self):
            """Simply set default domain and output file attributes to the
            correct values for bpython."""
            _extract_messages.initialize_options(self)

            self.domain = "bpython"
            self.output_file = os.path.join(translations_dir, "bpython.pot")

    class init_catalog(_init_catalog):
        def initialize_options(self):
            """Simply set default domain, input file and output directory
            attributes to the correct values for bpython."""
            _init_catalog.initialize_options(self)

            self.domain = "bpython"
            self.output_dir = translations_dir
            self.input_file = os.path.join(translations_dir, "bpython.pot")

    build.sub_commands.insert(0, ("compile_catalog", None))

    cmdclass["compile_catalog"] = compile_catalog
    cmdclass["extract_messages"] = extract_messages
    cmdclass["update_catalog"] = update_catalog
    cmdclass["init_catalog"] = init_catalog

if using_sphinx:

    class BuildDocMan(BuildDoc):
        def initialize_options(self):
            BuildDoc.initialize_options(self)
            self.builder = "man"
            self.source_dir = "doc/sphinx/source"
            self.build_dir = "build"

    build.sub_commands.insert(0, ("build_sphinx_man", None))
    cmdclass["build_sphinx_man"] = BuildDocMan

    if platform.system() in ["FreeBSD", "OpenBSD"]:
        man_dir = "man"
    else:
        man_dir = "share/man"

    # manual pages
    man_pages = [
        (os.path.join(man_dir, "man1"), ["build/man/bpython.1"]),
        (os.path.join(man_dir, "man5"), ["build/man/bpython-config.5"]),
    ]
else:
    man_pages = []

data_files = [
    # desktop shortcut
    (
        os.path.join("share", "applications"),
        ["data/org.bpython-interpreter.bpython.desktop"],
    ),
    # AppData
    (
        os.path.join("share", "appinfo"),
        ["data/org.bpython-interpreter.bpython.appdata.xml"],
    ),
    # icon
    (os.path.join("share", "pixmaps"), ["data/bpython.png"]),
]
data_files.extend(man_pages)

classifiers = [
    "Programming Language :: Python :: 2",
    "Programming Language :: Python :: 3",
]

install_requires = [
    "pygments",
    "requests",
    "curtsies >=0.3.0",
    "greenlet",
    "six >=1.5",
    "wcwidth",
]

extras_require = {
    "urwid": ["urwid"],
    "watch": ["watchdog"],
    "jedi": ["jedi"],
    # need requests[security] for SNI support (only before 2.7.7)
    ':python_full_version == "2.7.0" or '
    'python_full_version == "2.7.1" or '
    'python_full_version == "2.7.2" or '
    'python_full_version == "2.7.3" or '
    'python_full_version == "2.7.4" or '
    'python_full_version == "2.7.5" or '
    'python_full_version == "2.7.6"': [
        "pyOpenSSL",
        "pyasn1",
        "ndg-httpsclient",
    ],
}

packages = [
    "bpython",
    "bpython.curtsiesfrontend",
    "bpython.test",
    "bpython.test.fodder",
    "bpython.translations",
    "bpdb",
]

entry_points = {
    "console_scripts": [
        "bpython = bpython.curtsies:main",
        "bpython-curses = bpython.cli:main",
        "bpython-urwid = bpython.urwid:main [urwid]",
        "bpdb = bpdb:main",
    ]
}

tests_require = []
if sys.version_info[0] == 2:
    tests_require.append("mock")

# translations
mo_files = []
for language in os.listdir(translations_dir):
    mo_subpath = os.path.join(language, "LC_MESSAGES", "bpython.mo")
    if os.path.exists(os.path.join(translations_dir, mo_subpath)):
        mo_files.append(mo_subpath)

setup(
    name="bpython",
    version=version,
    author="Bob Farrell, Andreas Stuehrk et al.",
    author_email="robertanthonyfarrell@gmail.com",
    description="Fancy Interface to the Python Interpreter",
    license="MIT/X",
    url="https://www.bpython-interpreter.org/",
    long_description="""bpython is a fancy interface to the Python
    interpreter for Unix-like operating systems.""",
    classifiers=classifiers,
    install_requires=install_requires,
    extras_require=extras_require,
    tests_require=tests_require,
    packages=packages,
    data_files=data_files,
    package_data={
        "bpython": ["sample-config"],
        "bpython.translations": mo_files,
        "bpython.test": ["test.config", "test.theme"],
    },
    entry_points=entry_points,
    cmdclass=cmdclass,
    test_suite="bpython.test",
)

# vim: fileencoding=utf-8 sw=4 ts=4 sts=4 ai et sta
