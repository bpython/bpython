# The MIT License
#
# Copyright (c) 2008 Bob Farrell
# Copyright (c) 2012-2020 Sebastian Ramacher
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
Module to handle command line argument parsing, for all front-ends.
"""

import importlib.util
import os
import sys
import argparse

from . import __version__, __copyright__
from .config import default_config_path, loadini, Struct
from .translations import _


class ArgumentParserFailed(ValueError):
    """Raised by the RaisingOptionParser for a bogus commandline."""


class RaisingArgumentParser(argparse.ArgumentParser):
    def error(self, msg):
        raise ArgumentParserFailed()


def version_banner(base="bpython"):
    return "{} version {} on top of Python {} {}".format(
        base,
        __version__,
        sys.version.split()[0],
        sys.executable,
    )


def copyright_banner():
    return "{} See AUTHORS.rst for details.".format(__copyright__)


def parse(args, extras=None, ignore_stdin=False):
    """Receive an argument list - if None, use sys.argv - parse all args and
    take appropriate action. Also receive optional extra argument: this should
    be a tuple of (title, description, callback)
        title:          The title for the argument group
        description:    A full description of the argument group
        callback:       A callback that adds argument to the argument group

    e.g.:

    def callback(group):
        group.add_argument('-f', action='store_true', dest='f', help='Explode')
        group.add_argument('-l', action='store_true', dest='l', help='Love')

    parse(
        ['-i', '-m', 'foo.py'],
        ('Front end-specific options',
        'A full description of what these options are for',
        callback))


    Return a tuple of (config, options, exec_args) wherein "config" is the
    config object either parsed from a default/specified config file or default
    config options, "options" is the parsed options from
    ArgumentParser.parse_args, and "exec_args" are the args (if any) to be parsed
    to the executed file (if any).
    """
    if args is None:
        args = sys.argv[1:]

    parser = RaisingArgumentParser(
        usage=_(
            "Usage: %(prog)s [options] [file [args]]\n"
            "NOTE: If bpython sees an argument it does "
            "not know, execution falls back to the "
            "regular Python interpreter."
        )
    )
    parser.add_argument(
        "--config",
        default=default_config_path(),
        help=_("Use CONFIG instead of default config file."),
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help=_("Drop to bpython shell after running file instead of exiting."),
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help=_("Don't flush the output to stdout."),
    )
    parser.add_argument(
        "--version",
        "-V",
        action="store_true",
        help=_("Print version and exit."),
    )

    if extras is not None:
        extras_group = parser.add_argument_group(extras[0], extras[1])
        extras[2](extras_group)

    # collect all the remaining arguments into a list
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help=_(
            "File to extecute and additional arguments passed on to the executed script."
        ),
    )

    try:
        options = parser.parse_args(args)
    except ArgumentParserFailed:
        # Just let Python handle this
        os.execv(sys.executable, [sys.executable] + args)

    if options.version:
        print(version_banner())
        print(copyright_banner())
        raise SystemExit

    if not ignore_stdin and not (sys.stdin.isatty() and sys.stdout.isatty()):
        # Just let Python handle this
        os.execv(sys.executable, [sys.executable] + args)

    config = Struct()
    loadini(config, options.config)

    return config, options, options.args


def exec_code(interpreter, args):
    """
    Helper to execute code in a given interpreter. args should be a [faked]
    sys.argv
    """
    with open(args[0]) as sourcefile:
        source = sourcefile.read()
    old_argv, sys.argv = sys.argv, args
    sys.path.insert(0, os.path.abspath(os.path.dirname(args[0])))
    spec = importlib.util.spec_from_loader("__console__", loader=None)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["__console__"] = mod
    interpreter.locals = mod.__dict__
    interpreter.locals["__file__"] = args[0]
    interpreter.runsource(source, args[0], "exec")
    sys.argv = old_argv
