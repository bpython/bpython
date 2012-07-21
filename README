bpython - A fancy curses interface to the Python interactive interpreter
=======

Dependencies
============
Pygments
(apt-get install python-pygments)

Introduction
============
A few people asked for stuff like syntax highlighting
and autocomplete for the Python interactive interpreter.
IPython seems to offer this (plus you can get readline
behaviour in the vanilla interpreter) but I tried
IPython a couple of times. Perhaps I didn't really get
it, but I get the feeling that the ideas behind IPython
are pretty different to bpython. I didn't want to create
a whole development environment; I simply wanted to
provide a couple of neat features that already exist
and turn them into something a little more interactive.

The idea is to provide the user with all the features
in-line, much like modern IDEs, but in a simple,
lightweight package that can be run in a terminal
window, so curses seemed like the best choice.
Sorry if you use Windows.

bpython doesn't attempt to create anything new or
groundbreaking, it simply brings together a few neat
ideas and focuses on practicality and usefulness.
For this reason, the "Rewind" function should be
taken with a pinch of salt, but personally I have
found it to be very useful. I use bpython now
whenever I would normally use the vanilla interpreter,
e.g. for testing out solutions to people's problems
on IRC, quickly testing a method of doing something
without creating a temporary file, etc..

I hope you find it useful and please feel free to
submit any bugs/patches (yeah right)/suggestions
to:
robertanthonyfarrell@gmail.com
or place them at the bitbucket issue page for this
project at:
http://bitbucket.org/bobf/bpython/issues/

For any other ways of communicating with bpython
users and devs you can find us at the communication
page on the projects homepage:
http://bpython-interpreter.org/community

Hope to see you there!

Features
========

* In-line syntax highlighting.
	This uses Pygments for lexing the code as you type,
	and colours appropriately. Pygments does a great job
	of doing all of the tricky stuff and really leaving
	me with very little to do except format the tokens
	in all my favourite colours.

* Readline-like autocomplete with suggestions displayed
as you type.
	Thanks to Python's readline interface to libreadline
	and a ready-made class for using a Python interpreter's
	scope as the dataset, the only work here was displaying
	the readline matches as you type in a separate curses
	window below/above the cursor.

* Expected parameter list.
	As in a lot of modern IDEs, bpython will attempt to
	display a list of parameters for any function you
	call. The inspect module is tried first, which works
	with any Python function, and then pydoc if that fails,
	which seems to be pretty adequate, but obviously
	in some cases it's simply not possible. I used pyparsing
	to cure my nested parentheses woes; again, it was
	nice and easy.

* Rewind.
	I didn't call this "Undo" because I thought that would
	be misleading, but "Rewind" is probably as bad. The
	idea is that the code entered is kept in memory and
	when the Rewind function is called, the last line is
	popped and the entire code is re-evaluated. As you can
	imagine, this has a lot of potential problems, but for
	defining classes and functions, I've found it to be
	nothing but useful.

* Pastebin code/write to file.
	I don't really use the save thing much, but the pastebin
	thing's great. Hit a key and what you see on the screen
	will be sent to a pastebin and a URL is returned for you
	to do what you like with. I've hardcoded paste.pocoo.org
	in for now, that needs to be fixed so it's configurable.
	Next release, I promise.

* Flush curses screen to stdout.
	A featurette, perhaps, but I thought it was worth noting.
	I can't personally recall a curses app that does this,
	perhaps it's often not useful, but when you quit bpython,
	the screen data will be flushed to stdout, so it basically
	looks the same as if you had quit the vanilla interpreter.

Configuration
=============
See the sample-config file for a list of available options.
You should save your config file as ~/.config/bpython/config
(i.e $XDG_CONFIG_HOME/bpython/config) or specify at the
command line:

bpython --config /path/to/bpython/config

Known Bugs
==========
For known bugs please see bpython's issue tracker at
bitbucket:

http://bitbucket.org/bobf/bpython/issues/

CLI Windows Support
===================

Dependencies
------------
Curses
    Use the appropriate version compiled by Christoph Gohlke
    http://www.lfd.uci.edu/~gohlke/pythonlibs/

pyreadline
    Use the version in the cheeseshop
    http://pypi.python.org/pypi/pyreadline/

Recommended
-----------
Obtain the less program from GnuUtils. This makes the pager work as intended.
It can be obtained from cygwin or GnuWin32 or msys

Current version is tested with
------------------------------
Curses 2.2
pyreadline 1.7

Curses Notes
------------
The curses used has a bug where the colours are displayed incorrectly:
    red  is swapped with blue
    cyan is swapped with yellow

To correct this I have provided my windows.theme file.

This curses implementation has 16 colors (dark and light versions of the colours)


