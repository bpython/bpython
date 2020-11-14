.. image:: https://img.shields.io/pypi/v/bpython
    :target: https://pypi.org/project/bpython

.. image:: https://travis-ci.org/bpython/bpython.svg?branch=master
    :target: https://travis-ci.org/bpython/bpython

.. image:: https://readthedocs.org/projects/bpython/badge/?version=latest
    :target: https://docs.bpython-interpreter.org/en/latest/

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/ambv/black


***********************************************************************
bpython: A fancy curses interface to the Python interactive interpreter
***********************************************************************

`bpython`_ is a lightweight Python interpreter that adds several features common
to IDEs. These features include **syntax highlighting**, **expected parameter
list**, **auto-indentation**, and **autocompletion**. (See below for example
usage).

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
etc..

You can find more about bpython - including `full documentation`_ - at our
`homepage`_.

.. contents::
  :local:
    :depth: 1
    :backlinks: none

==========================
Installation & Basic Usage
==========================
If you have `pip`_ installed, you can simply run:

.. code-block:: bash

    $ pip install bpython

Start bpython by typing ``bpython`` in your terminal. You can exit bpython by
using the ``exit()`` command or by pressing control-D like regular interactive
Python.

===================
Features & Examples
===================
* Readline-like autocomplete, with suggestions displayed as you type.

* In-line syntax highlighting.  This uses Pygments for lexing the code as you
  type, and colours appropriately.

* Expected parameter list.  As in a lot of modern IDEs, bpython will attempt to
  display a list of parameters for any function you call. The inspect module is
  tried first, which works with any Python function, and then pydoc if that
  fails.

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

============
Dependencies
============
* Pygments
* requests
* curtsies >= 0.3.3
* greenlet
* Sphinx >= 1.5 (optional, for the documentation)
* babel (optional, for internationalization)
* watchdog (optional, for monitoring imported modules for changes)
* jedi (optional, for experimental multiline completion)

bpython-urwid
-------------
``bpython-urwid`` requires the following additional packages:

* urwid

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

===================
CLI Windows Support
===================

Dependencies
------------
`Curses`_ Use the appropriate version compiled by Christoph Gohlke.

`pyreadline`_ Use the version in the cheeseshop.

Recommended
-----------
Obtain the less program from GnuUtils. This makes the pager work as intended.
It can be obtained from cygwin or GnuWin32 or msys

Current version is tested with
------------------------------
* Curses 2.2
* pyreadline 1.7

Curses Notes
------------
The curses used has a bug where the colours are displayed incorrectly:

* red  is swapped with blue
* cyan is swapped with yellow

To correct this I have provided a windows.theme file.

This curses implementation has 16 colors (dark and light versions of the
colours)


============
Alternatives
============

`ptpython`_

`IPython`_

Feel free to get in touch if you know of any other alternatives that people
may be interested to try.

.. _ptpython: https://github.com/jonathanslenders/ptpython
.. _ipython: https://ipython.org/
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
