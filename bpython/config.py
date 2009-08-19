import os
import sys
from ConfigParser import ConfigParser, NoSectionError, NoOptionError
from itertools import chain
from bpython.keys import key_dispatch
import errno

class Struct(object):
    """Simple class for instantiating objects we can add arbitrary attributes
    to and use for various arbitrary things."""



class CP(ConfigParser):
    def safeget(self, section, option, default):
        """safet get method using default values"""
        bools_t = ['true', 'yes', 'y', 'on']
        bools_f = ['false', 'no', 'n', 'off']

        try:
            v = self.get(section, option)
        except NoSectionError:
            v = default
        except NoOptionError:
            v = default
        if isinstance(v, bool):
            return v
        try:
            if v.lower() in bools_t:
                return True
            if v.lower() in bools_f:
                return False
        except AttributeError:
            pass
        try:
            return int(v)
        except ValueError:
            return v


def loadini(struct, configfile):
    """Loads .ini configuration file and stores its values in struct"""

    config_path = os.path.expanduser(configfile)
    if not os.path.isfile(config_path) and configfile == '~/.bpython/config':
        # FIXME: I decided ~/.bpython.ini was a crappy place for a config file,
        # so this is just a fallback if the default is passed - remove this
        # eventually please.
        config_path = os.path.expanduser('~/.bpython.ini')

    config = CP()
    config.read(config_path)

    struct.tab_length = config.safeget('general', 'tab_length', 4)
    struct.auto_display_list = config.safeget('general', 'auto_display_list',
                                              True)
    struct.syntax = config.safeget('general', 'syntax', True)
    struct.arg_spec = config.safeget('general', 'arg_spec', True)
    struct.hist_file = config.safeget('general', 'hist_file', '~/.pythonhist')
    struct.hist_length = config.safeget('general', 'hist_length', 100)
    struct.flush_output = config.safeget('general', 'flush_output', True)
    struct.pastebin_key = config.safeget('keyboard', 'pastebin', 'F8')
    struct.save_key = config.safeget('keyboard', 'save', 'C-s')
    struct.undo_key = config.safeget('keyboard', 'undo', 'C-r')
    struct.up_one_line_key = config.safeget('keyboard', 'up_one_line', 'C-p')
    struct.down_one_line_key = config.safeget('keyboard', 'down_one_line', 'C-n')
    struct.cut_to_buffer_key = config.safeget('keyboard', 'cut_to_buffer', 'C-k')
    struct.yank_from_buffer_key = config.safeget('keybard', 'yank_from_buffer', 'C-y')
    struct.clear_word_key = config.safeget('keyboard', 'clear_word', 'C-w')
    struct.clear_line_key = config.safeget('keyboard', 'clear_line', 'C-u')
    struct.clear_screen_key = config.safeget('keyboard', 'clear_screen', 'C-l')
    struct.exit_key = config.safeget('keyboard', 'exit', 'C-d')
    struct.last_output_key = config.safeget('keyboard', 'last_output', 'F9')
 
    color_scheme_name = config.safeget('general', 'color_scheme', 'default')

    if color_scheme_name == 'default':
        struct.color_scheme = {
            'keyword': 'y',
            'name': 'c',
            'comment': 'b',
            'string': 'm',
            'error': 'r',
            'number': 'G',
            'operator': 'Y',
            'punctuation': 'y',
            'token': 'C',
            'background': 'd',
            'output': 'w',
            'main': 'c',
            'prompt': 'c',
            'prompt_more': 'g',
        }
    else:
        path = os.path.expanduser('~/.bpython/%s.theme' % (color_scheme_name,))
        load_theme(struct, path, config_path)


    # checks for valid key configuration this part still sucks
    for key in (struct.pastebin_key, struct.save_key):
        key_dispatch[key]

def load_theme(struct, path, inipath):
    theme = CP()
    try:
        f = open(path, 'r')
    except (IOError, OSError), e:
        sys.stdout.write("Error loading theme file specified in '%s':\n%s\n" %
                         (inipath, e))
        sys.exit(1)
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
    try:
        os.makedirs(os.path.expanduser('~/.bpython'))
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise
    f = open(os.path.expanduser('~/.bpython/config'), 'w')
    config.write(f)
    f.close()
    os.rename(path, os.path.expanduser('~/.bpythonrc.bak'))
    print ("The configuration file for bpython has been changed. A new "
           "config file has been created as ~/.bpython/config")
    print ("The existing .bpythonrc file has been renamed to .bpythonrc.bak "
           "and it can be removed.")
    print "Press enter to continue."
    raw_input()
