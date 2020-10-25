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

import code
import importlib.util
import os
import sys
from optparse import OptionParser, OptionGroup

from . import __version__, __copyright__
from .config import default_config_path, loadini, Struct
from .translations import _


class OptionParserFailed(ValueError):
    """Raised by the RaisingOptionParser for a bogus commandline."""


class RaisingOptionParser(OptionParser):
    def error(self, msg):
        raise OptionParserFailed()


def version_banner(base="bpython"):
    return "{} version {} on top of Python {} {}".format(
        base,
        __version__,
        sys.version.split()[0],
        sys.executable,
    )


def copyright_banner():
    return "{} See AUTHORS for details.".format(__copyright__)


def parse(args, extras=None, ignore_stdin=False):
    """Receive an argument list - if None, use sys.argv - parse all args and
    take appropriate action. Also receive optional extra options: this should
    be a tuple of (title, description, options)
        title:          The title for the option group
        description:    A full description of the option group
        callback:       A callback that adds options to the option group

    e.g.:

    def callback(group):
        group.add_option('-f', action='store_true', dest='f', help='Explode')
        group.add_option('-l', action='store_true', dest='l', help='Love')

    parse(
        ['-i', '-m', 'foo.py'],
        ('Front end-specific options',
        'A full description of what these options are for',
        callback))


    Return a tuple of (config, options, exec_args) wherein "config" is the
    config object either parsed from a default/specified config file or default
    config options, "options" is the parsed options from
    OptionParser.parse_args, and "exec_args" are the args (if any) to be parsed
    to the executed file (if any).
    """
    if args is None:
        args = sys.argv[1:]

    parser = RaisingOptionParser(
        usage=_(
            "Usage: %prog [options] [file [args]]\n"
            "NOTE: If bpython sees an argument it does "
            "not know, execution falls back to the "
            "regular Python interpreter."
        )
    )
    # This is not sufficient if bpython gains its own -m support
    # (instead of falling back to Python itself for that).
    # That's probably fixable though, for example by having that
    # option swallow all remaining arguments in a callback.
    parser.disable_interspersed_args()
    parser.add_option(
        "--config",
        default=default_config_path(),
        help=_("Use CONFIG instead of default config file."),
    )
    parser.add_option(
        "--interactive",
        "-i",
        action="store_true",
        help=_("Drop to bpython shell after running file instead of exiting."),
    )
    parser.add_option(
        "--quiet",
        "-q",
        action="store_true",
        help=_("Don't flush the output to stdout."),
    )
    parser.add_option(
        "--version",
        "-V",
        action="store_true",
        help=_("Print version and exit."),
    )

    if extras is not None:
        extras_group = OptionGroup(parser, extras[0], extras[1])
        extras[2](extras_group)
        parser.add_option_group(extras_group)

    try:
        options, args = parser.parse_args(args)
    except OptionParserFailed:
        # Just let Python handle this
        os.execv(sys.executable, [sys.executable] + args)

    if options.version:
        print(version_banner())
        print(copyright_banner())
        raise SystemExit

    if not ignore_stdin and not (sys.stdin.isatty() and sys.stdout.isatty()):
        interpreter = code.InteractiveInterpreter()
        interpreter.runsource(sys.stdin.read())
        raise SystemExit

    config = Struct()
    loadini(config, options.config)

    return config, options, args


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
