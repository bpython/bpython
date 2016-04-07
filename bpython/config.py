# encoding: utf-8

from __future__ import unicode_literals

import os
import sys
import locale
from itertools import chain
from six import iterkeys, iteritems
from six.moves.configparser import ConfigParser

from bpython.keys import cli_key_dispatch as key_dispatch
from bpython.autocomplete import SIMPLE as default_completion
import bpython.autocomplete


class Struct(object):
    """Simple class for instantiating objects we can add arbitrary attributes
    to and use for various arbitrary things."""


def getpreferredencoding():
    """Get the user's preferred encoding."""
    return locale.getpreferredencoding() or sys.getdefaultencoding()


def can_encode(c):
    try:
        c.encode(getpreferredencoding())
        return True
    except UnicodeEncodeError:
        return False


def supports_box_chars():
    """Check if the encoding supports Unicode box characters."""
    return all(map(can_encode, u'│─└┘┌┐'))


def get_config_home():
    """Returns the base directory for bpython's configuration files."""
    xdg_config_home = os.environ.get('XDG_CONFIG_HOME', '~/.config')
    return os.path.join(xdg_config_home, 'bpython')


def default_config_path():
    """Returns bpython's default configuration file path."""
    return os.path.join(get_config_home(), 'config')


def fill_config_with_default_values(config, default_values):
    for section in iterkeys(default_values):
        if not config.has_section(section):
            config.add_section(section)

        for (opt, val) in iteritems(default_values[section]):
            if not config.has_option(section, opt):
                config.set(section, opt, '%s' % (val, ))


def loadini(struct, configfile):
    """Loads .ini configuration file and stores its values in struct"""

    config_path = os.path.expanduser(configfile)

    config = ConfigParser()
    defaults = {
        'general': {
            'arg_spec': True,
            'auto_display_list': True,
            'autocomplete_mode': default_completion,
            'color_scheme': 'default',
            'complete_magic_methods': True,
            'dedent_after': 1,
            'editor': os.environ.get('VISUAL', os.environ.get('EDITOR', 'vi')),
            'flush_output': True,
            'highlight_show_source': True,
            'hist_duplicates': True,
            'hist_file': '~/.pythonhist',
            'hist_length': 100,
            'paste_time': 0.02,
            'pastebin_confirm': True,
            'pastebin_expiry': '1week',
            'pastebin_helper': '',
            'pastebin_removal_url': 'https://bpaste.net/remove/$removal_id',
            'pastebin_show_url': 'https://bpaste.net/show/$paste_id',
            'pastebin_url': 'https://bpaste.net/json/new',
            'save_append_py': False,
            'single_undo_time': 1.0,
            'syntax': True,
            'tab_length': 4,
            'unicode_box': True
        },
        'keyboard': {
            'backspace': 'C-h',
            'beginning_of_line': 'C-a',
            'clear_line': 'C-u',
            'clear_screen': 'C-l',
            'clear_word': 'C-w',
            'copy_clipboard': 'F10',
            'cut_to_buffer': 'C-k',
            'delete': 'C-d',
            'down_one_line': 'C-n',
            'edit_config': 'F3',
            'edit_current_block': 'C-x',
            'end_of_line': 'C-e',
            'exit': '',
            'external_editor': 'F7',
            'help': 'F1',
            'incremental_search': 'M-s',
            'last_output': 'F9',
            'left': 'C-b',
            'pastebin': 'F8',
            'reimport': 'F6',
            'reverse_incremental_search': 'M-r',
            'right': 'C-f',
            'save': 'C-s',
            'search': 'C-o',
            'show_source': 'F2',
            'suspend': 'C-z',
            'toggle_file_watch': 'F5',
            'transpose_chars': 'C-t',
            'undo': 'C-r',
            'up_one_line': 'C-p',
            'yank_from_buffer': 'C-y'
        },
        'cli': {
            'suggestion_width': 0.8,
            'trim_prompts': False,
        },
        'curtsies': {
            'list_above': False,
            'right_arrow_completion': True,
        }}

    default_keys_to_commands = dict((value, key) for (key, value)
                                    in iteritems(defaults['keyboard']))

    fill_config_with_default_values(config, defaults)
    if not config.read(config_path):
        # No config file. If the user has it in the old place then complain
        if os.path.isfile(os.path.expanduser('~/.bpython.ini')):
            sys.stderr.write("Error: It seems that you have a config file at "
                             "~/.bpython.ini. Please move your config file to "
                             "%s\n" % default_config_path())
            sys.exit(1)

    def get_key_no_doublebind(command):
        default_commands_to_keys = defaults['keyboard']
        requested_key = config.get('keyboard', command)

        try:
            default_command = default_keys_to_commands[requested_key]

            if (default_commands_to_keys[default_command] ==
                    config.get('keyboard', default_command)):
                setattr(struct, '%s_key' % default_command, '')
        except KeyError:
            pass

        return requested_key

    struct.config_path = config_path

    struct.dedent_after = config.getint('general', 'dedent_after')
    struct.tab_length = config.getint('general', 'tab_length')
    struct.auto_display_list = config.getboolean('general',
                                                 'auto_display_list')
    struct.syntax = config.getboolean('general', 'syntax')
    struct.arg_spec = config.getboolean('general', 'arg_spec')
    struct.paste_time = config.getfloat('general', 'paste_time')
    struct.single_undo_time = config.getfloat('general', 'single_undo_time')
    struct.highlight_show_source = config.getboolean('general',
                                                     'highlight_show_source')
    struct.hist_file = config.get('general', 'hist_file')
    struct.editor = config.get('general', 'editor')
    struct.hist_length = config.getint('general', 'hist_length')
    struct.hist_duplicates = config.getboolean('general', 'hist_duplicates')
    struct.flush_output = config.getboolean('general', 'flush_output')

    struct.pastebin_key = get_key_no_doublebind('pastebin')
    struct.copy_clipboard_key = get_key_no_doublebind('copy_clipboard')
    struct.save_key = get_key_no_doublebind('save')
    struct.search_key = get_key_no_doublebind('search')
    struct.show_source_key = get_key_no_doublebind('show_source')
    struct.suspend_key = get_key_no_doublebind('suspend')
    struct.toggle_file_watch_key = get_key_no_doublebind('toggle_file_watch')
    struct.undo_key = get_key_no_doublebind('undo')
    struct.reimport_key = get_key_no_doublebind('reimport')
    struct.reverse_incremental_search_key = get_key_no_doublebind(
        'reverse_incremental_search')
    struct.incremental_search_key = get_key_no_doublebind('incremental_search')
    struct.up_one_line_key = get_key_no_doublebind('up_one_line')
    struct.down_one_line_key = get_key_no_doublebind('down_one_line')
    struct.cut_to_buffer_key = get_key_no_doublebind('cut_to_buffer')
    struct.yank_from_buffer_key = get_key_no_doublebind('yank_from_buffer')
    struct.clear_word_key = get_key_no_doublebind('clear_word')
    struct.backspace_key = get_key_no_doublebind('backspace')
    struct.clear_line_key = get_key_no_doublebind('clear_line')
    struct.clear_screen_key = get_key_no_doublebind('clear_screen')
    struct.delete_key = get_key_no_doublebind('delete')

    struct.left_key = get_key_no_doublebind('left')
    struct.right_key = get_key_no_doublebind('right')
    struct.end_of_line_key = get_key_no_doublebind('end_of_line')
    struct.beginning_of_line_key = get_key_no_doublebind('beginning_of_line')
    struct.transpose_chars_key = get_key_no_doublebind('transpose_chars')
    struct.exit_key = get_key_no_doublebind('exit')
    struct.last_output_key = get_key_no_doublebind('last_output')
    struct.edit_config_key = get_key_no_doublebind('edit_config')
    struct.edit_current_block_key = get_key_no_doublebind('edit_current_block')
    struct.external_editor_key = get_key_no_doublebind('external_editor')
    struct.help_key = get_key_no_doublebind('help')

    struct.pastebin_confirm = config.getboolean('general', 'pastebin_confirm')
    struct.pastebin_url = config.get('general', 'pastebin_url')
    struct.pastebin_show_url = config.get('general', 'pastebin_show_url')
    struct.pastebin_removal_url = config.get('general', 'pastebin_removal_url')
    struct.pastebin_expiry = config.get('general', 'pastebin_expiry')
    struct.pastebin_helper = config.get('general', 'pastebin_helper')

    struct.cli_suggestion_width = config.getfloat('cli',
                                                  'suggestion_width')
    struct.cli_trim_prompts = config.getboolean('cli',
                                                'trim_prompts')

    struct.complete_magic_methods = config.getboolean('general',
                                                      'complete_magic_methods')
    struct.autocomplete_mode = config.get('general', 'autocomplete_mode')
    struct.save_append_py = config.getboolean('general', 'save_append_py')

    struct.curtsies_list_above = config.getboolean('curtsies', 'list_above')
    struct.curtsies_right_arrow_completion = \
        config.getboolean('curtsies', 'right_arrow_completion')

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
        'right_arrow_suggestion': 'K',
    }

    if color_scheme_name == 'default':
        struct.color_scheme = default_colors
    else:
        struct.color_scheme = dict()

        theme_filename = color_scheme_name + '.theme'
        path = os.path.expanduser(os.path.join(get_config_home(),
                                               theme_filename))
        try:
            load_theme(struct, path, struct.color_scheme, default_colors)
        except EnvironmentError:
            sys.stderr.write("Could not load theme '%s'.\n" %
                             (color_scheme_name, ))
            sys.exit(1)

    # expand path of history file
    struct.hist_file = os.path.expanduser(struct.hist_file)

    # verify completion mode
    if struct.autocomplete_mode not in bpython.autocomplete.ALL_MODES:
        struct.autocomplete_mode = default_completion

    # set box drawing characters
    if config.getboolean('general', 'unicode_box') and supports_box_chars():
        struct.left_border = '│'
        struct.right_border = '│'
        struct.top_border = '─'
        struct.bottom_border = '─'
        struct.left_bottom_corner = '└'
        struct.right_bottom_corner = '┘'
        struct.left_top_corner = '┌'
        struct.right_top_corner = '┐'
    else:
        struct.left_border = '|'
        struct.right_border = '|'
        struct.top_border = '-'
        struct.bottom_border = '-'
        struct.left_bottom_corner = '+'
        struct.right_bottom_corner = '+'
        struct.left_top_corner = '+'
        struct.right_top_corner = '+'


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
    for k, v in iteritems(default_colors):
        if k not in colors:
            colors[k] = v
