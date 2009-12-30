"""
Module to handle command line argument parsing, for all front-ends.
"""

from __future__ import with_statement
import os
import sys
import code
from optparse import OptionParser, OptionGroup
from itertools import takewhile

from bpython import __version__
from bpython.config import loadini, Struct, migrate_rc

def parse(args, extras=None):
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

    parser = OptionParser(usage='Usage: %prog [options] [file [args]]\n'
                                'NOTE: If bpython sees an argument it does '
                                 'not know, execution falls back to the '
                                 'regular Python interpreter.')
    parser.add_option('--config', '-c', default='~/.bpython/config',
                      help='use CONFIG instead of default config file')
    parser.add_option('--interactive', '-i', action='store_true',
                      help='Drop to bpython shell after running file '
                           'instead of exiting')
    parser.add_option('--quiet', '-q', action='store_true',
                      help="Don't flush the output to stdout.")
    parser.add_option('--version', '-V', action='store_true',
                      help='print version and exit')

    if extras is not None:
        extras_group = OptionGroup(parser, extras[0], extras[1])
        for option in extras[2]:
            extras_group.add_option(option)
        parser.add_option_group(extras_group)

    all_args = set(parser._short_opt.keys() + parser._long_opt.keys())
    if args and not all_args.intersection(arg.split('=')[0] for arg in args):
        # Just let Python handle this
        os.execv(sys.executable, [sys.executable] + args)
    else:
        # Split args in bpython args and args for the executed file
        real_args = list(takewhile(lambda arg: arg.split('=')[0] in all_args,
                                   args))
        exec_args = args[len(real_args):]

    options, args = parser.parse_args(real_args)

    if options.version:
        print 'bpython version', __version__,
        print 'on top of Python', sys.version.split()[0]
        print ('(C) 2008-2009 Bob Farrell, Andreas Stuehrk et al. '
               'See AUTHORS for detail.')
        raise SystemExit

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        interpreter = code.InteractiveInterpreter()
        interpreter.runsource(sys.stdin.read())
        raise SystemExit

    path = os.path.expanduser('~/.bpythonrc')
    # migrating old configuration file
    if os.path.isfile(path):
        migrate_rc(path)
    config = Struct()

    loadini(config, options.config)

    return config, options, exec_args

def exec_code(interpreter, args):
    """
    Helper to execute code in a given interpreter. args should be a [faked]
    sys.argv
    """
    with open(args[0], 'r') as sourcefile:
        code_obj = compile(sourcefile.read(), args[0], 'exec')
    old_argv, sys.argv = sys.argv, args
    interpreter.runcode(code_obj)
    sys.argv = old_argv
