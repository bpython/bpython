.. image:: https://img.shields.io/pypi/v/bpython
    :target: https://pypi.org/project/bpython

.. image:: https://readthedocs.org/projects/bpython/badge/?version=latest
    :target: https://docs.bpython-interpreter.org/en/latest/

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/ambv/black


****************************************************************
bpython: A fancy interface to the Python interactive interpreter
****************************************************************

**Introduction:**
bpython is a lightweight Python interpreter with added features commonly found in integrated development environments (IDEs). These features include syntax highlighting, auto-indentation, autocompletion, and displaying expected parameter lists for functions.

**Features:**
- Autocomplete suggestions as you type (similar to Readline).
- In-line syntax highlighting using Pygments.
- Display of expected parameter lists for functions.
- Rewind function to re-evaluate and edit previous code.
- Open current session in an external text editor.
- Paste code to pastebin or write to a file.
- Reload imported Python modules to test changes.
  
**Usage:**
bpython is not a full IDE but a practical and lightweight solution. It's ideal for testing code, helping others on IRC, or quick experimentation.

.. image:: https://bpython-interpreter.org/images/math.gif
  :alt: bpython
  :width: 566
  :height: 348
  :align: center

bpython does **not** aim to be a complete IDE - the focus is on implementing a
few ideas in a practical, useful, and lightweight manner.

bpython is a great replacement to any occasion where you would normally use the
vanilla Python interpreter - testing out solutions to people's problems on IRC,
quickly testing a method of doing something without creating a temporary file,
etc.

You can find more about bpython - including `full documentation`_ - at our
`homepage`_.

==========================
Installation & Basic Usage
==========================

**Installation:**
Using Pip: 
If you have pip installed, run: `$ pip install bpython`
Start bpython by typing `bpython` in the terminal. Exit with `exit()` or `ctrl-D`.

**Dependencies:**
- Pygments
- curtsies >= 0.4.0
- greenlet
- pyxdg
- requests
- Sphinx >= 1.5 (optional, for documentation)
- babel (optional, for internationalization)
- jedi (optional, for multiline completion)
- watchdog (optional, for monitoring module changes)
- pyperclip (optional, for clipboard copying)
===================
Features & Examples
===================
* Readline-like autocomplete, with suggestions displayed as you type.

* In-line syntax highlighting.  This uses Pygments for lexing the code as you
  type, and colours appropriately.

* Expected parameter list.  As in a lot of modern IDEs, bpython will attempt to
  display a list of parameters for any function you call. The inspect module (which
  works with any Python function) is tried first, and then pydoc if that fails.

* Rewind.  This isn't called "Undo" because it would be misleading, but "Rewind"
  is probably as bad. The idea is that the code entered is kept in memory and
  when the Rewind function is called, the last line is popped and the entire
  session is re-evaluated.  Use <control-R> to rewind.

* Edit the current line or your entire session in an editor. F7 opens the current
  session in a text editor, and if modifications are made, the session is rerun
  with these changes.

* Pastebin code/write to file.  Use the <F8> key to upload the screen's contents
  to pastebin, with a URL returned.

* Reload imported Python modules.  Use <F6> to clear sys.modules and rerun your
  session to test changes to code in a module you're working on.



=============
Configuration
=============
See the sample-config file for a list of available options.  You should save
your config file as **~/.config/bpython/config** (i.e.
``$XDG_CONFIG_HOME/bpython/config``) or specify at the command line::

  bpython --config /path/to/bpython/config



bpython-urwid
-------------
``bpython-urwid`` requires the following additional packages:

* urwid


===================================
Installation via OS Package Manager
===================================

The majority of desktop computer operating systems come with package management
systems. If you use one of these OSes, you can install ``bpython`` using the
package manager.

Ubuntu/Debian
-------------
Ubuntu/Debian family Linux users can install ``bpython`` using the ``apt``
package manager, using the command with ``sudo`` privileges:

.. code-block:: bash

    $ apt install bpython

In case you are using an older version, run

.. code-block:: bash

    $ apt-get install bpython

Arch Linux
----------
Arch Linux uses ``pacman`` as the default package manager; you can use it to install ``bpython``:

.. code-block:: bash

    $ pacman -S bpython

Fedora
------
Fedora users can install ``bpython`` directly from the command line using ``dnf``.

.. code-block:: bash

    $ dnf install bpython
    
GNU Guix
----------
Guix users can install ``bpython`` on any GNU/Linux distribution directly from the command line:

.. code-block:: bash

    $ guix install bpython

macOS
-----
macOS does not include a package manager by default. If you have installed any
third-party package manager like MacPorts, you can install it via

.. code-block:: bash

    $ sudo port install py-bpython


==========
Known Bugs
==========
For known bugs please see bpython's `known issues and FAQ`_ page.

======================
Contact & Contributing
======================
I hope you find it useful and please feel free to submit any bugs/patches
suggestions to `Robert`_ or place them on the GitHub
`issues tracker`_.

For any other ways of communicating with bpython users and devs you can find us
at the community page on the `project homepage`_, or in the `community`_.

Hope to see you there!

.. _homepage: http://www.bpython-interpreter.org
.. _full documentation: http://docs.bpython-interpreter.org/
.. _issues tracker: http://github.com/bpython/bpython/issues/
.. _pip: https://pip.pypa.io/en/latest/index.html
.. _project homepage: http://bpython-interpreter.org
.. _community: http://docs.bpython-interpreter.org/community.html
.. _Robert: robertanthonyfarrell@gmail.com
.. _bpython: http://www.bpython-interpreter.org/
.. _Curses: http://www.lfd.uci.edu/~gohlke/pythonlibs/
.. _pyreadline: http://pypi.python.org/pypi/pyreadline/
.. _known issues and FAQ: http://bpython-interpreter.org/known-issues-and-faq.html
