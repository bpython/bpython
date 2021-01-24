#!/usr/bin/env python3

import os
import platform
import re
import subprocess

from distutils.command.build import build
from setuptools import setup

try:
    from babel.messages import frontend as babel

    using_translations = True
except ImportError:
    using_translations = False

try:
    import sphinx
    from sphinx.setup_command import BuildDoc

    # Sphinx 1.5 and newer support Python 3.6
    using_sphinx = sphinx.__version__ >= "1.5"
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
    stdout = stdout.decode("ascii")

    if proc.returncode == 0:
        version = git_describe_to_python_version(stdout)
except OSError:
    pass

if version == "unknown":
    try:
        # get version from existing version file
        with open(version_file) as vf:
            version = (
                vf.read()
                .strip()
                .split("=")[-1]
                .replace("'", "")
                .replace('"', "")
            )
        version = version.strip()
    except OSError:
        pass

if version == "unknown":
    # get version from directory name (tarballs downloaded from tags)
    # directories are named bpython-X.Y-release in this case
    basename = os.path.basename(os.path.dirname(__file__))
    basename_components = basename.split("-")
    if (
        len(basename_components) == 3
        and basename_components[0] == "bpython"
        and basename_components[2] == "release"
    ):
        version = basename_components[1]

with open(version_file, "w") as vf:
    vf.write("# Auto-generated file, do not edit!\n")
    vf.write(f'__version__ = "{version}"\n')


cmdclass = {"build": build}

from bpython import package_dir, __author__

translations_dir = os.path.join(package_dir, "translations")

# localization options
if using_translations:
    build.sub_commands.insert(0, ("compile_catalog", None))

    cmdclass["compile_catalog"] = babel.compile_catalog
    cmdclass["extract_messages"] = babel.extract_messages
    cmdclass["update_catalog"] = babel.update_catalog
    cmdclass["init_catalog"] = babel.init_catalog

if using_sphinx:
    build.sub_commands.insert(0, ("build_sphinx_man", None))
    cmdclass["build_sphinx_man"] = BuildDoc

    if platform.system() in ("FreeBSD", "OpenBSD"):
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
    "Programming Language :: Python :: 3",
]

install_requires = [
    "pygments",
    "requests",
    "curtsies >=0.3.5",
    "greenlet",
    "cwcwidth",
    "pyxdg",
]

extras_require = {
    "urwid": ["urwid"],
    "watch": ["watchdog"],
    "jedi": ["jedi >=0.16"],
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

# translations
mo_files = []
for language in os.listdir(translations_dir):
    mo_subpath = os.path.join(language, "LC_MESSAGES", "bpython.mo")
    if os.path.exists(os.path.join(translations_dir, mo_subpath)):
        mo_files.append(mo_subpath)

setup(
    name="bpython",
    version=version,
    author=__author__,
    author_email="robertanthonyfarrell@gmail.com",
    description="Fancy Interface to the Python Interpreter",
    license="MIT/X",
    url="https://www.bpython-interpreter.org/",
    long_description="""bpython is a fancy interface to the Python
    interpreter for Unix-like operating systems.""",
    classifiers=classifiers,
    python_requires=">=3.6",
    install_requires=install_requires,
    extras_require=extras_require,
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
