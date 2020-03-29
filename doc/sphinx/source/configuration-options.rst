General
-------
This refers to the ``[general]`` section in your
`$XDG_CONFIG_HOME/bpython/config` file.

arg_spec
^^^^^^^^
Display the arg spec (list of arguments) for callables, when possible (default:
True).

auto_display_list
^^^^^^^^^^^^^^^^^
Display the autocomplete list as you type (default: True).
When this is off, you can hit tab to see the suggestions.

autocomplete_mode
^^^^^^^^^^^^^^^^^
There are three modes for autocomplete. simple, substring, and fuzzy.  Simple
matches methods with a common prefix, substring matches methods with a common
subsequence, and fuzzy matches methods with common characters (default: simple).

As of version 0.14 this option has no effect, but is reserved for later use.

.. versionadded:: 0.12

.. _configuration_color_scheme:

color_scheme
^^^^^^^^^^^^
See :ref:`themes` for more information.

Color schemes should be put in ``$XDG_CONFIG_HOME/bpython/``. For example, to
use the theme ``$XDG_CONFIG_HOME/bpython/foo.theme`` set ``color_scheme = foo``

Leave blank or set to "default" to use the default (builtin) theme.

complete_magic_methods
^^^^^^^^^^^^^^^^^^^^^^
Whether magic methods should be auto completed (default: True).

dedent_after
^^^^^^^^^^^^
Number of blank lines required before next line will be dedented (default: 1).
If set to 0, automatic dedenting never occurs.

editor
^^^^^^
Editor for externally editing the current line, session, or config file.

.. versionadded:: 0.13

flush_output
^^^^^^^^^^^^
Whether to flush all output to stdout on exit (default: True).

Only relevant to bpython-curses and bpython-urwid.

highlight_show_source
^^^^^^^^^^^^^^^^^^^^^
Whether the source code of an object should be syntax highlighted (default: True).

hist_duplicates
^^^^^^^^^^^^^^^
Whether to store duplicate entries in the history (default: True).

hist_file
^^^^^^^^^
History file (default: ``~/.pythonhist``).

hist_length
^^^^^^^^^^^
Number of lines to store in history (set to 0 to disable) (default: 100).

paste_time
^^^^^^^^^^
The time between keypresses before pastemode is deactivated in bpython-curses (default: 0.02).

pastebin_confirm
^^^^^^^^^^^^^^^^
Whether pasting to a pastebin needs to be confirmed before sending the data
(default: True).

pastebin_expiry
^^^^^^^^^^^^^^^
Time duration after which a paste should expire. Valid values are ``1day``,
``1week`` and ``1month`` (default: ``1week``).

.. versionadded:: 0.14

pastebin_helper
^^^^^^^^^^^^^^^

The name of a helper executable that should perform pastebin upload on bpython's
behalf. If set, this overrides `pastebin_url`. The helper is expected to return
the full URL to the pastebin as the first word of its output. The data is
supplied to the helper via STDIN.

An example helper program is ``pastebinit``, available for most systems. The
following helper program can be used to create `gists
<http://gist.github.com>`_:

.. code-block:: python

  #!/usr/bin/env python

  import sys
  import urllib2
  import json

  def do_gist_json(s):
      """ Use json to post to github. """
      gist_public = False
      gist_url = 'https://api.github.com/gists'

      data = {'description': None,
              'public': None,
              'files' : {
                  'sample': { 'content': None }
              }}
      data['description'] = 'Gist from BPython'
      data['public'] = gist_public
      data['files']['sample']['content'] = s

      req = urllib2.Request(gist_url, json.dumps(data), {'Content-Type': 'application/json'})
      try:
          res = urllib2.urlopen(req)
      except HTTPError, e:
          return e

      try:
          json_res = json.loads(res.read())
          return json_res['html_url']
      except HTTPError, e:
          return e

  if __name__ == "__main__":
    s = sys.stdin.read()
    print do_gist_json(s)


.. versionadded:: 0.12

pastebin_url
^^^^^^^^^^^^
The pastebin url to post to (without a trailing slash). This pastebin has to be
a pastebin which provides a similar interface to ``bpaste.net``'s JSON
interface (default: https://bpaste.net).

save_append_py
^^^^^^^^^^^^^^
Whether to append ``.py`` to the filename while saving the input to a file.

.. versionadded:: 0.13

single_undo_time
^^^^^^^^^^^^^^^^
Time duration an undo must be predicted to take before prompting
to undo multiple lines at once. Use -1 to never prompt, or 0 to always prompt.
(default: 1.0)

.. versionadded:: 0.14

syntax
^^^^^^
Syntax highlighting as you type (default: True).

tab_length
^^^^^^^^^^
Soft tab size (default 4, see PEP-8).

unicode_box
^^^^^^^^^^^
Whether to use Unicode characters to draw boxes.

.. versionadded:: 0.14

Keyboard
--------
This section refers to the ``[keyboard]`` section in your
``$XDG_CONFIG_HOME/bpython/config``.

You can set various keyboard shortcuts to be used by bpython. However, we have
yet to map all keys to their respective control codes. If you configure a key
combination which is not yet supported by bpython it will raise an exception
telling you the key does not exist in bpython.keys.

Valid keys are:

* Control + any alphanumeric character (C-a through C-z, also a few others).
* Any function key ranging from F1 to F12.

backspace
^^^^^^^^^
Default: C-h

Delete character in front of the cursor.

.. versionadded:: 0.14

beginning_of_line
^^^^^^^^^^^^^^^^^
Default: C-a

Move to the beginning of the line.

.. versionadded:: 0.14

clear_line
^^^^^^^^^^
Default: C-u

Clears to the beginning of the line.

clear_screen
^^^^^^^^^^^^
Default: C-l

Clears the screen to the top.

clear_word
^^^^^^^^^^
Default: C-w

Clear the word the cursor is currently on.

copy_clipboard
^^^^^^^^^^^^^^
Default: F10

Copy the entire session to clipboard.

.. versionadded:: 0.14

cut_to_buffer
^^^^^^^^^^^^^
Default: C-k

Cuts the current line to the buffer.

delete
^^^^^^
Default: C-d

Delete character under the cursor.

down_one_line
^^^^^^^^^^^^^
Default: C-n

Move the cursor down, by one line.

edit_config
^^^^^^^^^^^
Default: F3

Edit bpython configuration in external editor.

.. versionadded:: 0.14

edit_current_block
^^^^^^^^^^^^^^^^^^
Default: C-x

Edit current block in external editor.

.. versionadded:: 0.14

end_of_line
^^^^^^^^^^^
Default: C-e

Move to the of the line.

.. versionadded:: 0.14

exit
^^^^
Default: C-d

Exits bpython (use on empty line)

external_editor
^^^^^^^^^^^^^^^
Default: F7

Edit the entire session in an external editor.

.. versionadded:: 0.13

help
^^^^
Default: F1

Brings up sincerely cheerful description of bpython features and current key bindings.

.. versionadded:: 0.14

incremental_search
^^^^^^^^^^^^^^^^^^^^^^^^^^
Default: M-s

Perform incremental search on all stored lines in the history.

.. versionadded:: 0.15

last_output
^^^^^^^^^^^
Default: F9

Shows the last output in the systems $PAGER. Only works in bpython-curses.

left
^^^^
Default: C-b

Move a character to the left.

.. versionadded:: 0.14

pastebin
^^^^^^^^
Default: F8

reimport
^^^^^^^^
Default: F6

Reruns entire session, reloading all modules by clearing the sys.modules cache.

.. versionadded:: 0.14

reverse_incremental_search
^^^^^^^^^^^^^^^^^^^^^^^^^^
Default: M-r

Perform reverse incremental search on all stored lines in the history.

.. versionadded:: 0.15

right
^^^^^
Default: C-f

Move a character to the right.

.. versionadded:: 0.14

save
^^^^
Default: C-s

Saves the current session to a file (prompts for filename)

search
^^^^^^
Default: C-o

Search up for any lines containing what is on the current line.

show_source
^^^^^^^^^^^
Default: F2

Shows the source of the currently being completed (python) function.

toggle_file_watch
^^^^^^^^^^^^^^^^^
Default: F5

Toggles file watching behaviour; re-runs entire bpython session whenever an imported
module is modified.

.. versionadded:: 0.14

transpose_chars
^^^^^^^^^^^^^^^
Default: C-t

Transpose current character with the one left of it.

.. versionadded:: 0.14

undo
^^^^
Default: C-r

Rewinds the last action.

up_one_line
^^^^^^^^^^^
Default: C-p

Move the cursor up, by one line.

yank_from_buffer
^^^^^^^^^^^^^^^^
Default: C-y

Pastes the current line from the buffer (the one you previously cutted)

CLI
---
This refers to the ``[cli]`` section in your config file.

suggestion_width
^^^^^^^^^^^^^^^^
Default: 0.8

The width of the suggestion window in percent of the terminal width.

.. versionadded:: 0.9.8

trim_prompts
^^^^^^^^^^^^
Default: False

Trims lines starting with '>>> ' when set to True.

curtsies
--------
This refers to the ``[curtsies]`` section in your config file.

.. versionadded:: 0.13

list_above
^^^^^^^^^^
Default: False

When there is space above the current line, whether the suggestions list will be
displayed there instead of below the current line.

right_arrow_completion
^^^^^^^^^^^^^^^^^^^^^^
Default: True

Full line suggestion and completion (like fish shell and many web browsers).

Full line completions are displayed under the cursor in gray.
When the cursor is at the end of a line, pressing right arrow or ctrl-f will
complete the full line.
This option also turns on substring history search, highlighting the matching
section in previous result.

Sample config
-------------

.. include:: ../../../bpython/sample-config
   :literal:
