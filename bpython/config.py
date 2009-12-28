import os
import sys
from ConfigParser import ConfigParser
from itertools import chain
from bpython.keys import key_dispatch
import errno


class Struct(object):
    """Simple class for instantiating objects we can add arbitrary attributes
    to and use for various arbitrary things."""


def fill_config_with_default_values(config, default_values):
    for section in default_values.iterkeys():
        if not config.has_section(section):
            config.add_section(section)

        for (opt, val) in default_values[section].iteritems():
            if not config.has_option(section, opt):
                config.set(section, opt, str(val))


def loadini(struct, configfile):
    """Loads .ini configuration file and stores its values in struct"""

    config_path = os.path.expanduser(configfile)
    if not os.path.isfile(config_path) and configfile == '~/.bpython/config':
        # FIXME: I decided ~/.bpython.ini was a crappy place for a config file,
        # so this is just a fallback if the default is passed - remove this
        # eventually please.
        config_path = os.path.expanduser('~/.bpython.ini')

    config = ConfigParser()
    fill_config_with_default_values(config, {
        'general': {
            'arg_spec': True,
            'auto_display_list': True,
            'color_scheme': 'default',
            'dedent_after': 1,
            'flush_output': True,
            'highlight_show_source': True,
            'hist_file': '~/.pythonhist',
            'hist_length': 100,
            'paste_time': 0.02,
            'syntax': True,
            'tab_length': 4,
            'pastebin_url': 'http://bpaste.net/xmlrpc/',
            'pastebin_show_url': 'http://bpaste.net/show/$paste_id/',
        },
        'keyboard': {
            'clear_line': 'C-u',
            'clear_screen': 'C-l',
            'clear_word': 'C-w',
            'cut_to_buffer': 'C-k',
            'down_one_line': 'C-n',
            'exit': 'C-d',
            'last_output': 'F9',
            'pastebin': 'F8',
            'save': 'C-s',
            'show_source': 'F2',
            'undo': 'C-r',
            'up_one_line': 'C-p',
            'yank_from_buffer': 'C-y'}})
    config.read(config_path)

    struct.dedent_after = config.getint('general', 'dedent_after')
    struct.tab_length = config.getint('general', 'tab_length')
    struct.auto_display_list = config.getboolean('general',
                                                 'auto_display_list')
    struct.syntax = config.getboolean('general', 'syntax')
    struct.arg_spec = config.getboolean('general', 'arg_spec')
    struct.paste_time = config.getfloat('general', 'paste_time')
    struct.highlight_show_source = config.getboolean('general',
                                                     'highlight_show_source')
    struct.hist_file = config.get('general', 'hist_file')
    struct.hist_length = config.getint('general', 'hist_length')
    struct.flush_output = config.getboolean('general', 'flush_output')
    struct.pastebin_key = config.get('keyboard', 'pastebin')
    struct.save_key = config.get('keyboard', 'save')
    struct.show_source_key = config.get('keyboard', 'show_source')
    struct.undo_key = config.get('keyboard', 'undo')
    struct.up_one_line_key = config.get('keyboard', 'up_one_line')
    struct.down_one_line_key = config.get('keyboard', 'down_one_line')
    struct.cut_to_buffer_key = config.get('keyboard', 'cut_to_buffer')
    struct.yank_from_buffer_key = config.get('keyboard', 'yank_from_buffer')
    struct.clear_word_key = config.get('keyboard', 'clear_word')
    struct.clear_line_key = config.get('keyboard', 'clear_line')
    struct.clear_screen_key = config.get('keyboard', 'clear_screen')
    struct.exit_key = config.get('keyboard', 'exit')
    struct.last_output_key = config.get('keyboard', 'last_output')

    struct.pastebin_url = config.get('general', 'pastebin_url')
    struct.pastebin_show_url = config.get('general', 'pastebin_show_url')

    color_scheme_name = config.get('general', 'color_scheme')

    default_colors = {
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
            'paren': 'R',
            'prompt': 'c',
            'prompt_more': 'g',
        }
 
    if color_scheme_name == 'default':
        struct.color_scheme = default_colors
    else:
        path = os.path.expanduser('~/.bpython/%s.theme' % (color_scheme_name,))
        load_theme(struct, path, config_path, default_colors)

    # checks for valid key configuration this part still sucks
    for key in (struct.pastebin_key, struct.save_key):
        key_dispatch[key]


def load_theme(struct, path, inipath, default_colors):
    theme = ConfigParser()
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

    # Check against default theme to see if all values are defined
    for k, v in default_colors.iteritems():
        if k not in struct.color_scheme:
            struct.color_scheme[k] = v
    f.close()


def migrate_rc(path):
    """Use the shlex module to convert the old configuration file to the new
    format.
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
        'off': False}

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
