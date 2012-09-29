from __future__ import with_statement
import os
import sys
from ConfigParser import ConfigParser
from itertools import chain
from bpython.keys import cli_key_dispatch as key_dispatch
from bpython.autocomplete import SIMPLE as default_completion

MAGIC_METHODS = ", ".join("__%s__" % s for s in [
    "init", "repr", "str", "lt", "le", "eq", "ne", "gt", "ge", "cmp", "hash",
    "nonzero", "unicode", "getattr", "setattr", "get", "set","call", "len",
    "getitem", "setitem", "iter", "reversed", "contains", "add", "sub", "mul",
    "floordiv", "mod", "divmod", "pow", "lshift", "rshift", "and", "xor", "or",
    "div", "truediv", "neg", "pos", "abs", "invert", "complex", "int", "float",
    "oct", "hex", "index", "coerce", "enter", "exit"]
)

class Struct(object):
    """Simple class for instantiating objects we can add arbitrary attributes
    to and use for various arbitrary things."""

def get_config_home():
    """Returns the base directory for bpython's configuration files."""
    xdg_config_home = os.environ.get('XDG_CONFIG_HOME', '~/.config')
    return os.path.join(xdg_config_home, 'bpython')

def default_config_path():
    """Returns bpython's default configuration file path."""
    return os.path.join(get_config_home(), 'config')

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
    if not os.path.isfile(config_path) and configfile == default_config_path():
        # We decided that '~/.bpython/config' still was a crappy
        # place, use XDG Base Directory Specification instead.  Fall
        # back to old config, though.
        config_path = os.path.expanduser('~/.bpython/config')

    config = ConfigParser()
    fill_config_with_default_values(config, {
        'general': {
            'arg_spec': True,
            'auto_display_list': True,
            'color_scheme': 'default',
            'complete_magic_methods' : True,
            'magic_methods' : MAGIC_METHODS,
            'autocomplete_mode': default_completion,
            'dedent_after': 1,
            'flush_output': True,
            'highlight_show_source': True,
            'hist_file': '~/.pythonhist',
            'hist_length': 100,
            'hist_duplicates': True,
            'paste_time': 0.02,
            'syntax': True,
            'tab_length': 4,
            'pastebin_confirm': True,
            'pastebin_private': False,
            'pastebin_url': 'http://bpaste.net/xmlrpc/',
            'pastebin_private': True,
            'pastebin_show_url': 'http://bpaste.net/show/$paste_id/',
            'pastebin_helper': '',
        },
        'keyboard': {
            'clear_line': 'C-u',
            'clear_screen': 'C-l',
            'clear_word': 'C-w',
            'cut_to_buffer': 'C-k',
            'delete': 'C-d',
            'down_one_line': 'C-n',
            'exit': '',
            'last_output': 'F9',
            'pastebin': 'F8',
            'save': 'C-s',
            'show_source': 'F2',
            'suspend': 'C-z',
            'undo': 'C-r',
            'search': 'C-o',
            'up_one_line': 'C-p',
            'yank_from_buffer': 'C-y'},
        'cli': {
            'suggestion_width': 0.8,
            'trim_prompts': False,
        },
        'gtk': {
            'font': 'monospace 10',
            'color_scheme': 'default'}})
    if not config.read(config_path):
        # No config file. If the user has it in the old place then complain
        if os.path.isfile(os.path.expanduser('~/.bpython.ini')):
            sys.stderr.write("Error: It seems that you have a config file at "
                             "~/.bpython.ini. Please move your config file to "
                             "%s\n" % default_config_path())
            sys.exit(1)

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
    struct.hist_duplicates = config.getboolean('general', 'hist_duplicates')
    struct.flush_output = config.getboolean('general', 'flush_output')
    struct.pastebin_key = config.get('keyboard', 'pastebin')
    struct.save_key = config.get('keyboard', 'save')
    struct.search_key = config.get('keyboard', 'search')
    struct.show_source_key = config.get('keyboard', 'show_source')
    struct.suspend_key = config.get('keyboard', 'suspend')
    struct.undo_key = config.get('keyboard', 'undo')
    struct.up_one_line_key = config.get('keyboard', 'up_one_line')
    struct.down_one_line_key = config.get('keyboard', 'down_one_line')
    struct.cut_to_buffer_key = config.get('keyboard', 'cut_to_buffer')
    struct.yank_from_buffer_key = config.get('keyboard', 'yank_from_buffer')
    struct.clear_word_key = config.get('keyboard', 'clear_word')
    struct.clear_line_key = config.get('keyboard', 'clear_line')
    struct.clear_screen_key = config.get('keyboard', 'clear_screen')
    struct.delete_key = config.get('keyboard', 'delete')
    struct.exit_key = config.get('keyboard', 'exit')
    struct.last_output_key = config.get('keyboard', 'last_output')

    struct.pastebin_confirm = config.getboolean('general', 'pastebin_confirm')
    struct.pastebin_private = config.getboolean('general', 'pastebin_private')
    struct.pastebin_url = config.get('general', 'pastebin_url')
    struct.pastebin_private = config.get('general', 'pastebin_private')
    struct.pastebin_show_url = config.get('general', 'pastebin_show_url')
    struct.pastebin_helper = config.get('general', 'pastebin_helper')

    struct.cli_suggestion_width = config.getfloat('cli',
                                                  'suggestion_width')
    struct.cli_trim_prompts = config.getboolean('cli',
                                                  'trim_prompts')

    struct.complete_magic_methods = config.getboolean('general',
                                                      'complete_magic_methods')
    methods = config.get('general', 'magic_methods')
    struct.magic_methods = [meth.strip() for meth in methods.split(",")]
    struct.autocomplete_mode = config.get('general', 'autocomplete_mode')

    struct.gtk_font = config.get('gtk', 'font')

    color_scheme_name = config.get('general', 'color_scheme')
    color_gtk_scheme_name = config.get('gtk', 'color_scheme')

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

    default_gtk_colors = {
            'keyword': 'b',
            'name': 'k',
            'comment': 'b',
            'string': 'm',
            'error': 'r',
            'number': 'G',
            'operator': 'B',
            'punctuation': 'g',
            'token': 'C',
            'background': 'w',
            'output': 'k',
            'main': 'c',
            'paren': 'R',
            'prompt': 'b',
            'prompt_more': 'g',
        }

    if color_scheme_name == 'default':
        struct.color_scheme = default_colors
    else:
        struct.color_scheme = dict()

        theme_filename = color_scheme_name + '.theme'
        path = os.path.expanduser(os.path.join(get_config_home(),
                                               theme_filename))
        old_path = os.path.expanduser(os.path.join('~/.bpython',
                                                   theme_filename))

        for path in [path, old_path]:
            try:
                load_theme(struct, path, struct.color_scheme, default_colors)
            except EnvironmentError:
                continue
            else:
                break
        else:
            sys.stderr.write("Could not load theme '%s'.\n" %
                                                         (color_scheme_name, ))
            sys.exit(1)

    if color_gtk_scheme_name == 'default':
        struct.color_gtk_scheme = default_gtk_colors
    else:
        struct.color_gtk_scheme = dict()
        # Note: This is a new config option, hence we don't have a
        # fallback directory.
        path = os.path.expanduser(os.path.join(get_config_home(),
                                               color_gtk_scheme_name + '.theme'))

        try:
            load_theme(struct, path, struct.color_gtk_scheme, default_colors)
        except EnvironmentError:
            sys.stderr.write("Could not load gtk theme '%s'.\n" %
                                                    (color_gtk_scheme_name, ))
            sys.exit(1)

    # checks for valid key configuration this part still sucks
    for key in (struct.pastebin_key, struct.save_key):
        key_dispatch[key]

def load_theme(struct, path, colors, default_colors):
    theme = ConfigParser()
    with open(path, 'r') as f:
        theme.readfp(f)
    for k, v in chain(theme.items('syntax'), theme.items('interface')):
        if theme.has_option('syntax', k):
            colors[k] = theme.get('syntax', k)
        else:
            colors[k] = theme.get('interface', k)

    # Check against default theme to see if all values are defined
    for k, v in default_colors.iteritems():
        if k not in colors:
            colors[k] = v
    f.close()
