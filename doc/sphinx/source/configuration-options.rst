General
-------
This refers to the ``[general]`` section in your `$XDG_CONFIG_HOME/bpython/config` file.

auto_display_list
^^^^^^^^^^^^^^^^^
Display the autocomplete list as you type (default: True).
When this is off, you can hit tab to see the suggestions.

autocomplete_mode
^^^^^^^^^^^^^^^^^
There are three modes for autocomplete. simple, substring, and fuzzy.
Simple matches methods with a common prefix, substring matches methods with a common
subsequence, and fuzzy matches methods with common characters (default:
simple).

.. versionadded:: 0.12

syntax
^^^^^^
Syntax highlighting as you type (default: True).

arg_spec
^^^^^^^^
Display the arg spec (list of arguments) for callables, when possible (default: True).

hist_file
^^^^^^^^^
History file (default: ``~/.pythonhist``).

paste_time
^^^^^^^^^^
The time between lines before pastemode is activated in seconds (default: 0.02).

hist_length
^^^^^^^^^^^
Number of lines to store in history (set to 0 to disable) (default: 100)

tab_length
^^^^^^^^^^
Soft tab size (default 4, see pep-8)

pastebin_url
^^^^^^^^^^^^
The pastebin url to post to (without a trailing slash). This pastebin has
to be a pastebin which uses LodgeIt. Examples are: http://paste.pocoo.org/xmlrpc/ and
http://bpaste.net/xmlrpc/ (default: http://bpaste.net/xmlrpc/)

pastebin_private
^^^^^^^^^^^^^^^^
If the pastebin supports a private option to make a random paste id, use it.
Default: True).

.. versionadded:: 0.12

pastebin_show_url
^^^^^^^^^^^^^^^^^
The url under which the new paste can be reached. ``$paste_id`` will be
replaced by the ID of the new paste. Examples are: http://bpaste.net/show/$paste_id/
and http://paste.pocoo.org/show/$paste_id/ (default: http://bpaste.net/show/$paste_id/)

pastebin_helper
^^^^^^^^^^^^^^^

The name of a helper executable that should perform pastebin upload on bpython's
behalf. If set, this overrides `pastebin_url`. It also overrides `pastebin_show_url`,
as the helper is expected to return the full URL to the pastebin as the first word of
its output. The data is supplied to the helper via STDIN.

An example helper program is ``pastebinit``, available for most systems. The
following helper program can be used to create `gists <http://gist.github.com>`_:

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

.. _configuration_color_scheme:

color_scheme
^^^^^^^^^^^^
See :ref:`themes` for more information.

Color schemes should be put in ``$XDG_CONFIG_HOME/bpython/``

e.g to use the theme ``$XDG_CONFIG_HOME/bpython/foo.theme`` set ``color_scheme = foo``

If you set the colorscheme to `foo` this will be translated to 
``$XDG_CONFIG_HOME/bpython/foo.theme`` so be sure to put the file in that directory.

Leave blank or set to "default" to use the default (builtin) theme.

flush_output
^^^^^^^^^^^^
Whether to flush all output to stdout on exit (default: True).

Keyboard
--------
This section refers to the ``[keyboard]`` section in your ``$XDG_CONFIG_HOME/bpython/config``.

You can set various keyboard shortcuts to be used by bpython. However, we have yet to map all keys
to their respective control codes. If you configure a key combination which is not yet supported
by bpython it will raise an exception telling you the key does not exist in bpython.keys.

Valid keys are:

* Control + any alphanumeric character (C-a through A-z, also a few others).
* Any function key ranging from F1 to F12.

pastebin
^^^^^^^^
Default: <F8>

last_output
^^^^^^^^^^^
Default: F9

Shows the last output in the systems $PAGER.

save
^^^^
Default: C-s

Saves the current session to a file (prompts for filename)

undo
^^^^
Default: C-r

Rewinds the last action.

up_one_line
^^^^^^^^^^^
Default: C-p

Move the cursor up, by one line.

down_one_line
^^^^^^^^^^^^^
Default: C-n

Move the cursor down, by one line.

cut_to_buffer
^^^^^^^^^^^^^
Default: C-k

Cuts the current line to the buffer.

search
^^^^^^
Default: C-o

Search up for any lines containing what is on the current line.

yank_from_buffer
^^^^^^^^^^^^^^^^
Default: C-y

Pastes the current line from the buffer (the one you previously cutted)

clear_word
^^^^^^^^^^
Default: C-w

Clear the word the cursor is currently on.

clear_line
^^^^^^^^^^
Default: C-u

Clears to the beginning of the line.

clear_screen
^^^^^^^^^^^^
Default: C-l

Clears the screen to the top.

show_source
^^^^^^^^^^^
Default: F2

Shows the source of the currently being completed (python) function.

exit
^^^^
Default: C-d

Exits bpython (use on empty line)

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

GTK
---
This refers to the ``[gtk]`` section in your `$XDG_CONFIG_HOME/bpython/config` file.

font
^^^^
Default: Monospace 10

The font to be used by the GTK version.

