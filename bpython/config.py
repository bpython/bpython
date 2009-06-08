import os
from ConfigParser import ConfigParser, NoSectionError, NoOptionError


class Struct(object):
    """Simple class for instantiating objects we can add arbitrary attributes
    to and use for various arbitrary things."""



class CP(ConfigParser):
    def safeget(self, section, option, default):
        """safet get method using default values"""
        try:
            v = self.get(section, option)
        except NoSectionError:
            v = default
        except NoOptionError:
            v = default
        if isinstance(v, bool):
            return v
        try:
            return int(v)
        except ValueError:
            return v


def loadini(struct, configfile):
    """Loads .ini configuration file and stores its values in struct"""

    configfile = os.path.expanduser(configfile)

    config = CP()
    config.read(configfile)

    struct.tab_length = config.safeget('general', 'tab_length', 4)
    struct.auto_display_list = config.safeget('general', 'auto_display_list',
                                              True)
    struct.syntax = config.safeget('general', 'syntax', True)
    struct.arg_spec = config.safeget('general', 'arg_spec', True)
    struct.hist_file = config.safeget('general', 'hist_file', '~/.pythonhist')
    struct.hist_length = config.safeget('general', 'hist_length', 100)
    struct.flush_output = config.safeget('general', 'flush_output', True)
    color_scheme_name = config.safeget('general', 'color_scheme', 'default')

    if color_scheme_name == 'default':
        struct.color_scheme = {
            'keyword': 'Y',
            'name': 'B',
            'comment': 'b',
            'string': 'g',
            'error': 'r',
            'number': 'g',
            'operator': 'c',
            'punctuation': 'y',
            'token': 'g',
            'background': 'k',
            'output': 'w',
            'main': 'c',
            'prompt': 'r',
            'prompt_more': 'g',
        }
    else:
        path = os.path.expanduser('~/.bpython/%s.theme' % (color_scheme_name,))
        # XXX ConfigParser doesn't raise an IOError if it tries to read a file
        # that doesn't exist which isn't helpful to us:
        if not os.path.isfile(path):
            raise IOError("'%s' is not a readable file" % (path,))
        load_theme(struct, color_scheme_name)


def load_theme(struct, path):
    theme = CP()
    f = open(path, 'r')
    theme.readfp(f)
    struct.color_scheme = {}
    for k, v in chain(theme.items('syntax'), theme.items('interface')):
        if theme.has_option('syntax', k):
            struct.color_scheme[k] = theme.get('syntax', k)
        else:
            struct.color_scheme[k] = theme.get('interface', k)
    f.close()


def migrate_rc(path):
    """Use the shlex module to convert the old configuration file to the new format.
    The old configuration file is renamed but not removed by now."""
    import shlex
    f = open(path)
    parser = shlex.shlex(f)

    bools = {
        'true': True,
        'yes': True,
        'on': True,
        'false': False,
        'no': False,
        'off': False
    }

    config = ConfigParser()
    config.add_section('general')

    while True:
        k = parser.get_token()
        v = None

        if not k:
            break

        k = k.lower()

        if parser.get_token() == '=':
            v = parser.get_token() or None

        if v is not None:
            try:
                v = int(v)
            except ValueError:
                if v.lower() in bools:
                    v = bools[v.lower()]
                config.set('general', k, v)
    f.close()
    f = open(os.path.expanduser('~/.bpython.ini'), 'w')
    config.write(f)
    f.close()
    os.rename(path, os.path.expanduser('~/.bpythonrc.bak'))
    print ("The configuration file for bpython has been changed. A new "
           ".bpython.ini file has been created in your home directory.")
    print ("The existing .bpythonrc file has been renamed to .bpythonrc.bak "
           "and it can be removed.")
    print "Press enter to continue."
    raw_input()
