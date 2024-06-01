#!/usr/bin/env python3

import os
import platform
import re
import subprocess

from setuptools import setup, Command
from setuptools.command.build import build

try:
    from babel.messages import frontend as babel

    using_translations = True
except ImportError:
    using_translations = False

try:
    import sphinx

    # Sphinx 1.5 and newer support Python 3.6
    using_sphinx = sphinx.__version__ >= "1.5"
except ImportError:
    using_sphinx = False


if using_sphinx:
    import sys
    from io import StringIO

    from setuptools.errors import ExecError
    from sphinx.application import Sphinx
    from sphinx.cmd.build import handle_exception
    from sphinx.util.console import color_terminal, nocolor
    from sphinx.util.docutils import docutils_namespace, patch_docutils
    from sphinx.util.osutil import abspath

    class BuildDoc(Command):
        """
        Distutils command to build Sphinx documentation.
        The Sphinx build can then be triggered from distutils, and some Sphinx
        options can be set in ``setup.py`` or ``setup.cfg`` instead of Sphinx's
        own configuration file.
        For instance, from `setup.py`::
           # this is only necessary when not using setuptools/distribute
           from sphinx.setup_command import BuildDoc
           cmdclass = {'build_sphinx': BuildDoc}
           name = 'My project'
           version = '1.2'
           release = '1.2.0'
           setup(
               name=name,
               author='Bernard Montgomery',
               version=release,
               cmdclass=cmdclass,
               # these are optional and override conf.py settings
               command_options={
                   'build_sphinx': {
                       'project': ('setup.py', name),
                       'version': ('setup.py', version),
                       'release': ('setup.py', release)}},
           )
        Or add this section in ``setup.cfg``::
           [build_sphinx]
           project = 'My project'
           version = 1.2
           release = 1.2.0
        """

        description = "Build Sphinx documentation"
        user_options = [
            ("fresh-env", "E", "discard saved environment"),
            ("all-files", "a", "build all files"),
            ("source-dir=", "s", "Source directory"),
            ("build-dir=", None, "Build directory"),
            ("config-dir=", "c", "Location of the configuration directory"),
            (
                "builder=",
                "b",
                "The builder (or builders) to use. Can be a comma- "
                'or space-separated list. Defaults to "html"',
            ),
            ("warning-is-error", "W", "Turn warning into errors"),
            ("project=", None, "The documented project's name"),
            ("version=", None, "The short X.Y version"),
            (
                "release=",
                None,
                "The full version, including alpha/beta/rc tags",
            ),
            (
                "today=",
                None,
                "How to format the current date, used as the "
                "replacement for |today|",
            ),
            ("link-index", "i", "Link index.html to the master doc"),
            ("copyright", None, "The copyright string"),
            ("pdb", None, "Start pdb on exception"),
            ("verbosity", "v", "increase verbosity (can be repeated)"),
            (
                "nitpicky",
                "n",
                "nit-picky mode, warn about all missing references",
            ),
            ("keep-going", None, "With -W, keep going when getting warnings"),
        ]
        boolean_options = [
            "fresh-env",
            "all-files",
            "warning-is-error",
            "link-index",
            "nitpicky",
        ]

        def initialize_options(self) -> None:
            self.fresh_env = self.all_files = False
            self.pdb = False
            self.source_dir: str = None
            self.build_dir: str = None
            self.builder = "html"
            self.warning_is_error = False
            self.project = ""
            self.version = ""
            self.release = ""
            self.today = ""
            self.config_dir: str = None
            self.link_index = False
            self.copyright = ""
            # Link verbosity to distutils' (which uses 1 by default).
            self.verbosity = self.distribution.verbose - 1  # type: ignore
            self.traceback = False
            self.nitpicky = False
            self.keep_going = False

        def _guess_source_dir(self) -> str:
            for guess in ("doc", "docs"):
                if not os.path.isdir(guess):
                    continue
                for root, dirnames, filenames in os.walk(guess):
                    if "conf.py" in filenames:
                        return root
            return os.curdir

        def finalize_options(self) -> None:
            self.ensure_string_list("builder")

            if self.source_dir is None:
                self.source_dir = self._guess_source_dir()
                self.announce("Using source directory %s" % self.source_dir)

            self.ensure_dirname("source_dir")

            if self.config_dir is None:
                self.config_dir = self.source_dir

            if self.build_dir is None:
                build = self.get_finalized_command("build")
                self.build_dir = os.path.join(abspath(build.build_base), "sphinx")  # type: ignore

            self.doctree_dir = os.path.join(self.build_dir, "doctrees")

            self.builder_target_dirs = [
                (builder, os.path.join(self.build_dir, builder))
                for builder in self.builder
            ]

        def run(self) -> None:
            if not color_terminal():
                nocolor()
            if not self.verbose:  # type: ignore
                status_stream = StringIO()
            else:
                status_stream = sys.stdout  # type: ignore
            confoverrides = {}
            if self.project:
                confoverrides["project"] = self.project
            if self.version:
                confoverrides["version"] = self.version
            if self.release:
                confoverrides["release"] = self.release
            if self.today:
                confoverrides["today"] = self.today
            if self.copyright:
                confoverrides["copyright"] = self.copyright
            if self.nitpicky:
                confoverrides["nitpicky"] = self.nitpicky

            for builder, builder_target_dir in self.builder_target_dirs:
                app = None

                try:
                    confdir = self.config_dir or self.source_dir
                    with patch_docutils(confdir), docutils_namespace():
                        app = Sphinx(
                            self.source_dir,
                            self.config_dir,
                            builder_target_dir,
                            self.doctree_dir,
                            builder,
                            confoverrides,
                            status_stream,
                            freshenv=self.fresh_env,
                            warningiserror=self.warning_is_error,
                            verbosity=self.verbosity,
                            keep_going=self.keep_going,
                        )
                        app.build(force_all=self.all_files)
                        if app.statuscode:
                            raise ExecError(
                                "caused by %s builder." % app.builder.name
                            )
                except Exception as exc:
                    handle_exception(app, self, exc, sys.stderr)
                    if not self.pdb:
                        raise SystemExit(1) from exc

                if not self.link_index:
                    continue

                src = app.config.root_doc + app.builder.out_suffix  # type: ignore
                dst = app.builder.get_outfilename("index")  # type: ignore
                os.symlink(src, dst)


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
        ["git", "describe", "--tags", "--first-parent"],
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


class custom_build(build):
    def run(self):
        if using_translations:
            self.run_command("compile_catalog")
        if using_sphinx:
            self.run_command("build_sphinx_man")


cmdclass = {"build": custom_build}


translations_dir = os.path.join("bpython", "translations")

# localization options
if using_translations:
    cmdclass["compile_catalog"] = babel.compile_catalog
    cmdclass["extract_messages"] = babel.extract_messages
    cmdclass["update_catalog"] = babel.update_catalog
    cmdclass["init_catalog"] = babel.init_catalog

if using_sphinx:
    cmdclass["build_sphinx"] = BuildDoc
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
        os.path.join("share", "metainfo"),
        ["data/org.bpython-interpreter.bpython.metainfo.xml"],
    ),
    # icon
    (os.path.join("share", "pixmaps"), ["data/bpython.png"]),
]
data_files.extend(man_pages)

# translations
mo_files = []
for language in os.listdir(translations_dir):
    mo_subpath = os.path.join(language, "LC_MESSAGES", "bpython.mo")
    if os.path.exists(os.path.join(translations_dir, mo_subpath)):
        mo_files.append(mo_subpath)


setup(
    version=version,
    data_files=data_files,
    package_data={
        "bpython": ["sample-config"],
        "bpython.translations": mo_files,
        "bpython.test": ["test.config", "test.theme"],
    },
    cmdclass=cmdclass,
    test_suite="bpython.test",
    zip_safe=False,
)

# vim: fileencoding=utf-8 sw=4 ts=4 sts=4 ai et sta
