.. _themes:

Themes
======
This chapter is about bpython's theming capabilities.

bpython uses .theme files placed in your ``$XDG_CONFIG_HOME/bpython`` directory
[#f1]_.  You can set the theme in the :ref:`configuration_color_scheme` option
in your ``$XDG_CONFIG_HOME/bpython/config`` file (:ref:`configuration`).

Available Colors
----------------
* k = black
* r = red
* g = green
* y = yellow
* b = blue
* m = magenta
* c = cyan
* w = white
* d = default, this will make the switch default to the bpython default theme

Any letter writing uppercase will make the switch bold.

Available Switches
------------------
* keyword
* name
* comment
* string
* error
* number
* operator
* punctuation
* token
* background
* output
* main
* prompt
* prompt_more
* right_arrow_suggestion

Default Theme
-------------
The default theme included in bpython is as follows:

.. code-block:: python
  :linenos:

  # Each letter represents a colour marker:
  #   k, r, g, y, b, m, c, w, d
  # which stands for:
  #   blacK, Red, Green, Yellow, Blue, Magenta, Cyan, White, Default
  # Capital letters represent bold
  # Copy to $XDG_CONFIG_HOME/bpython/foo.theme and set "color_scheme = foo" in
  # $XDG_CONFIG_HOME/bpython/config ($XDG_CONFIG_HOME defaults to ~/.config)

  [syntax]
  keyword = y
  name = c
  comment = b
  string = m
  error = r
  number = G
  operator = Y
  punctuation = y
  token = C
  paren = R

  [interface]
  # XXX: gnome-terminal appears to be braindead. The cursor will disappear unless
  # you set the background colour to "d".
  background = k
  output = w
  main = c
  prompt = c
  prompt_more = g
  right_arrow_suggestion = K

.. :: Footnotes

.. [#f1] ``$XDG_CONFIG_HOME`` defaults to ``~/.config`` if not set.

