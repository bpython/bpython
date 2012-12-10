"""
Module to handle command line argument parsing, for all front-ends.
"""

from __future__ import with_statement
import os
import sys
import code
from optparse import OptionParser, OptionGroup

from bpython import __version__
from bpython.config import default_config_path, loadini, Struct
from bpython.translations import _


class OptionParserFailed(ValueError):
    """Raised by the RaisingOptionParser for a bogus commandline."""


class RaisingOptionParser(OptionParser):
    def error(self, msg):
        raise OptionParserFailed()


def parse(args, extras=None, ignore_stdin=False):
    """Receive an argument list - if None, use sys.argv - parse all args and
    take appropriate action. Also receive optional extra options: this should
    be a tuple of (title, description, options)
        title:          The title for the option group
        description:    A full description of the option group
        options:        A list of optparse.Option objects to be added to the
                        group

    e.g.:

    parse(['-i', '-m', 'foo.py'],
          ('Front end-specific options',
          'A full description of what these options are for',
          [optparse.Option('-f', action='store_true', dest='f', help='Explode'),
           optparse.Option('-l', action='store_true', dest='l', help='Love')]))


    Return a tuple of (config, options, exec_args) wherein "config" is the
    config object either parsed from a default/specified config file or default
    config options, "options" is the parsed options from
    OptionParser.parse_args, and "exec_args" are the args (if any) to be parsed
    to the executed file (if any).
    """
    if args is None:
        args = sys.argv[1:]

    parser = RaisingOptionParser(
        usage=_('Usage: %prog [options] [file [args]]\n'
        'NOTE: If bpython sees an argument it does '
        'not know, execution falls back to the '
        'regular Python interpreter.'))
    # This is not sufficient if bpython gains its own -m support
    # (instead of falling back to Python itself for that).
    # That's probably fixable though, for example by having that
    # option swallow all remaining arguments in a callback.
    parser.disable_interspersed_args()
    parser.add_option('--config', default=default_config_path(),
                      help=_('Use CONFIG instead of default config file.'))
    parser.add_option('--interactive', '-i', action='store_true',
                      help=_('Drop to bpython shell after running file '
                           'instead of exiting.'))
    parser.add_option('--quiet', '-q', action='store_true',
                      help=_("Don't flush the output to stdout."))
    parser.add_option('--version', '-V', action='store_true',
                      help=_('Print version and exit.'))

    if extras is not None:
        extras_group = OptionGroup(parser, extras[0], extras[1])
        for option in extras[2]:
            extras_group.add_option(option)
        parser.add_option_group(extras_group)

    try:
        options, args = parser.parse_args(args)
    except OptionParserFailed:
        # Just let Python handle this
        os.execv(sys.executable, [sys.executable] + args)

    if options.version:
        print 'bpython version', __version__,
        print 'on top of Python', sys.version.split()[0]
        print ('(C) 2008-2012 Bob Farrell, Andreas Stuehrk et al. '
               'See AUTHORS for detail.')
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
    with open(args[0], 'r') as sourcefile:
        code_obj = compile(sourcefile.read(), args[0], 'exec')
    old_argv, sys.argv = sys.argv, args
    sys.path.insert(0, os.path.abspath(os.path.dirname(args[0])))
    interpreter.runcode(code_obj)
    sys.argv = old_argv
