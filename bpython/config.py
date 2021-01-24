# The MIT License
#
# Copyright (c) 2009-2015 the bpython authors.
# Copyright (c) 2015-2020 Sebastian Ramacher
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


import os
import sys
import locale
from configparser import ConfigParser
from itertools import chain
from pathlib import Path
from xdg import BaseDirectory

from .autocomplete import AutocompleteModes

default_completion = AutocompleteModes.SIMPLE


class Struct:
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
    return all(map(can_encode, "│─└┘┌┐"))


def get_config_home():
    """Returns the base directory for bpython's configuration files."""
    return Path(BaseDirectory.xdg_config_home) / "bpython"


def default_config_path():
    """Returns bpython's default configuration file path."""
    return get_config_home() / "config"


def default_editor():
    """Returns the default editor."""
    return os.environ.get("VISUAL", os.environ.get("EDITOR", "vi"))


def fill_config_with_default_values(config, default_values):
    for section in default_values.keys():
        if not config.has_section(section):
            config.add_section(section)

        for (opt, val) in default_values[section].items():
            if not config.has_option(section, opt):
                config.set(section, opt, f"{val}")


def loadini(struct, config_path):
    """Loads .ini configuration file and stores its values in struct"""

    config = ConfigParser()
    defaults = {
        "general": {
            "arg_spec": True,
            "auto_display_list": True,
            "autocomplete_mode": default_completion,
            "color_scheme": "default",
            "complete_magic_methods": True,
            "dedent_after": 1,
            "default_autoreload": False,
            "editor": default_editor(),
            "flush_output": True,
            "import_completion_skiplist": ":".join(
                (
                    # version tracking
                    ".git",
                    ".svn",
                    ".hg"
                    # XDG
                    ".config",
                    ".local",
                    ".share",
                    # nodejs
                    "node_modules",
                    # PlayOnLinux
                    "PlayOnLinux's virtual drives",
                    # wine
                    "dosdevices",
                    # Python byte code cache
                    "__pycache__",
                )
            ),
            "highlight_show_source": True,
            "hist_duplicates": True,
            "hist_file": "~/.pythonhist",
            "hist_length": 1000,
            "paste_time": 0.02,
            "pastebin_confirm": True,
            "pastebin_expiry": "1week",
            "pastebin_helper": "",
            "pastebin_url": "https://bpaste.net",
            "save_append_py": False,
            "single_undo_time": 1.0,
            "syntax": True,
            "tab_length": 4,
            "unicode_box": True,
        },
        "keyboard": {
            "backspace": "C-h",
            "beginning_of_line": "C-a",
            "clear_line": "C-u",
            "clear_screen": "C-l",
            "clear_word": "C-w",
            "copy_clipboard": "F10",
            "cut_to_buffer": "C-k",
            "delete": "C-d",
            "down_one_line": "C-n",
            "edit_config": "F3",
            "edit_current_block": "C-x",
            "end_of_line": "C-e",
            "exit": "",
            "external_editor": "F7",
            "help": "F1",
            "incremental_search": "M-s",
            "last_output": "F9",
            "left": "C-b",
            "pastebin": "F8",
            "redo": "C-g",
            "reimport": "F6",
            "reverse_incremental_search": "M-r",
            "right": "C-f",
            "save": "C-s",
            "search": "C-o",
            "show_source": "F2",
            "suspend": "C-z",
            "toggle_file_watch": "F5",
            "transpose_chars": "C-t",
            "undo": "C-r",
            "up_one_line": "C-p",
            "yank_from_buffer": "C-y",
        },
        "cli": {
            "suggestion_width": 0.8,
            "trim_prompts": False,
        },
        "curtsies": {
            "list_above": False,
            "right_arrow_completion": True,
        },
    }

    default_keys_to_commands = {
        value: key for (key, value) in defaults["keyboard"].items()
    }

    fill_config_with_default_values(config, defaults)
    try:
        config.read(config_path)
    except UnicodeDecodeError as e:
        sys.stderr.write(
            "Error: Unable to parse config file at '{}' due to an "
            "encoding issue. Please make sure to fix the encoding "
            "of the file or remove it and then try again.\n".format(config_path)
        )
        sys.exit(1)

    def get_key_no_doublebind(command):
        default_commands_to_keys = defaults["keyboard"]
        requested_key = config.get("keyboard", command)

        try:
            default_command = default_keys_to_commands[requested_key]

            if default_commands_to_keys[default_command] == config.get(
                "keyboard", default_command
            ):
                setattr(struct, "%s_key" % default_command, "")
        except KeyError:
            pass

        return requested_key

    struct.config_path = Path(config_path).absolute()

    struct.dedent_after = config.getint("general", "dedent_after")
    struct.tab_length = config.getint("general", "tab_length")
    struct.auto_display_list = config.getboolean("general", "auto_display_list")
    struct.syntax = config.getboolean("general", "syntax")
    struct.arg_spec = config.getboolean("general", "arg_spec")
    struct.paste_time = config.getfloat("general", "paste_time")
    struct.single_undo_time = config.getfloat("general", "single_undo_time")
    struct.highlight_show_source = config.getboolean(
        "general", "highlight_show_source"
    )
    struct.hist_file = config.get("general", "hist_file")
    struct.editor = config.get("general", "editor")
    struct.hist_length = config.getint("general", "hist_length")
    struct.hist_duplicates = config.getboolean("general", "hist_duplicates")
    struct.flush_output = config.getboolean("general", "flush_output")
    struct.default_autoreload = config.getboolean(
        "general", "default_autoreload"
    )
    struct.import_completion_skiplist = config.get(
        "general", "import_completion_skiplist"
    ).split(":")

    struct.pastebin_key = get_key_no_doublebind("pastebin")
    struct.copy_clipboard_key = get_key_no_doublebind("copy_clipboard")
    struct.save_key = get_key_no_doublebind("save")
    struct.search_key = get_key_no_doublebind("search")
    struct.show_source_key = get_key_no_doublebind("show_source")
    struct.suspend_key = get_key_no_doublebind("suspend")
    struct.toggle_file_watch_key = get_key_no_doublebind("toggle_file_watch")
    struct.undo_key = get_key_no_doublebind("undo")
    struct.redo_key = get_key_no_doublebind("redo")
    struct.reimport_key = get_key_no_doublebind("reimport")
    struct.reverse_incremental_search_key = get_key_no_doublebind(
        "reverse_incremental_search"
    )
    struct.incremental_search_key = get_key_no_doublebind("incremental_search")
    struct.up_one_line_key = get_key_no_doublebind("up_one_line")
    struct.down_one_line_key = get_key_no_doublebind("down_one_line")
    struct.cut_to_buffer_key = get_key_no_doublebind("cut_to_buffer")
    struct.yank_from_buffer_key = get_key_no_doublebind("yank_from_buffer")
    struct.clear_word_key = get_key_no_doublebind("clear_word")
    struct.backspace_key = get_key_no_doublebind("backspace")
    struct.clear_line_key = get_key_no_doublebind("clear_line")
    struct.clear_screen_key = get_key_no_doublebind("clear_screen")
    struct.delete_key = get_key_no_doublebind("delete")

    struct.left_key = get_key_no_doublebind("left")
    struct.right_key = get_key_no_doublebind("right")
    struct.end_of_line_key = get_key_no_doublebind("end_of_line")
    struct.beginning_of_line_key = get_key_no_doublebind("beginning_of_line")
    struct.transpose_chars_key = get_key_no_doublebind("transpose_chars")
    struct.exit_key = get_key_no_doublebind("exit")
    struct.last_output_key = get_key_no_doublebind("last_output")
    struct.edit_config_key = get_key_no_doublebind("edit_config")
    struct.edit_current_block_key = get_key_no_doublebind("edit_current_block")
    struct.external_editor_key = get_key_no_doublebind("external_editor")
    struct.help_key = get_key_no_doublebind("help")

    struct.pastebin_confirm = config.getboolean("general", "pastebin_confirm")
    struct.pastebin_url = config.get("general", "pastebin_url")
    struct.pastebin_expiry = config.get("general", "pastebin_expiry")
    struct.pastebin_helper = config.get("general", "pastebin_helper")

    struct.cli_suggestion_width = config.getfloat("cli", "suggestion_width")
    struct.cli_trim_prompts = config.getboolean("cli", "trim_prompts")

    struct.complete_magic_methods = config.getboolean(
        "general", "complete_magic_methods"
    )
    struct.autocomplete_mode = AutocompleteModes.from_string(
        config.get("general", "autocomplete_mode")
    )
    struct.save_append_py = config.getboolean("general", "save_append_py")

    struct.curtsies_list_above = config.getboolean("curtsies", "list_above")
    struct.curtsies_right_arrow_completion = config.getboolean(
        "curtsies", "right_arrow_completion"
    )
    struct.unicode_box = config.getboolean("general", "unicode_box")

    color_scheme_name = config.get("general", "color_scheme")

    default_colors = {
        "keyword": "y",
        "name": "c",
        "comment": "b",
        "string": "m",
        "error": "r",
        "number": "G",
        "operator": "Y",
        "punctuation": "y",
        "token": "C",
        "background": "d",
        "output": "w",
        "main": "c",
        "paren": "R",
        "prompt": "c",
        "prompt_more": "g",
        "right_arrow_suggestion": "K",
    }

    if color_scheme_name == "default":
        struct.color_scheme = default_colors
    else:
        struct.color_scheme = dict()

        path = get_config_home() / f"{color_scheme_name}.theme"
        try:
            load_theme(struct, path, struct.color_scheme, default_colors)
        except OSError:
            sys.stderr.write(
                f"Could not load theme '{color_scheme_name}' from {path}.\n"
            )
            sys.exit(1)

    # expand path of history file
    struct.hist_file = Path(struct.hist_file).expanduser()

    # verify completion mode
    if struct.autocomplete_mode is None:
        struct.autocomplete_mode = default_completion

    # set box drawing characters
    if struct.unicode_box and supports_box_chars():
        struct.left_border = "│"
        struct.right_border = "│"
        struct.top_border = "─"
        struct.bottom_border = "─"
        struct.left_bottom_corner = "└"
        struct.right_bottom_corner = "┘"
        struct.left_top_corner = "┌"
        struct.right_top_corner = "┐"
    else:
        struct.left_border = "|"
        struct.right_border = "|"
        struct.top_border = "-"
        struct.bottom_border = "-"
        struct.left_bottom_corner = "+"
        struct.right_bottom_corner = "+"
        struct.left_top_corner = "+"
        struct.right_top_corner = "+"


def load_theme(struct, path, colors, default_colors):
    theme = ConfigParser()
    with open(path) as f:
        theme.read_file(f)
    for k, v in chain(theme.items("syntax"), theme.items("interface")):
        if theme.has_option("syntax", k):
            colors[k] = theme.get("syntax", k)
        else:
            colors[k] = theme.get("interface", k)

    # Check against default theme to see if all values are defined
    for k, v in default_colors.items():
        if k not in colors:
            colors[k] = v
