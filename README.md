[<img src="https://img.shields.io/pypi/v/bpython">](https://pypi.org/project/bpython)
[<img src="https://readthedocs.org/projects/bpython/badge/?version=latest">](https://docs.bpython-interpreter.org/en/latest/)
[<img src="https://img.shields.io/badge/code%20style-black-000000.svg">](https://github.com/ambv/black)

# bpython: A fancy interface to the Python interactive interpreter

``bpython`` is a lightweight Python interpreter that adds several features common
to IDEs. These features include **syntax highlighting**, **expected parameter
list**, **auto-indentation**, and **autocompletion**. (See below for example
usage).

![](https://bpython-interpreter.org/images/math.gif)

bpython does **not** aim to be a complete IDE - the focus is on implementing a
few ideas in a practical, useful, and lightweight manner.

bpython is a great replacement to any occasion where you would normally use the
vanilla Python interpreter - testing out solutions to people's problems on IRC,
quickly testing a method of doing something without creating a temporary file,
etc.

You can find more about bpython - including [full documentation](https://docs.bpython-interpreter.org) - at our
[homepage](https://bpython-interpreter.org).

## Installation using Pip

If you have [pip](https://pip.pypa.io/en/latest/index.html) installed, you can simply run:

```bash
$ pip install bpython
```

Start bpython by typing ``bpython`` in your terminal. You can exit bpython by
using the ``exit()`` command or by pressing control-D like regular interactive
Python.

## Features & Examples

- Readline-like autocomplete, with suggestions displayed as you type.
- In-line syntax highlighting.  This uses Pygments for lexing the code as you
  type, and colours appropriately.
- Expected parameter list.  As in a lot of modern IDEs, bpython will attempt to
  display a list of parameters for any function you call. The inspect module (which
  works with any Python function) is tried first, and then pydoc if that fails.
- Rewind.  This isn't called "Undo" because it would be misleading, but "Rewind"
  is probably as bad. The idea is that the code entered is kept in memory and
  when the Rewind function is called, the last line is popped and the entire
  session is re-evaluated.  Use <control-R> to rewind.
- Edit the current line or your entire session in an editor. F7 opens the current
  session in a text editor, and if modifications are made, the session is rerun
  with these changes.
- Pastebin code/write to file.  Use the <F8> key to upload the screen's contents
- to pastebin, with a URL returned.
- Reload imported Python modules.  Use <F6> to clear sys.modules and rerun your
  session to test changes to code in a module you're working on.

## Configuration

See the sample-config file for a list of available options.  You should save
your config file as **~/.config/bpython/config** (i.e.
``$XDG_CONFIG_HOME/bpython/config``) or specify at the command line:

```
bpython --config /path/to/bpython/config
```

## Dependencies

- Pygments
- curtsies >= 0.3.5
- greenlet
- pyxdg
- requests
- Sphinx >= 1.5 (optional, for the documentation)
- babel (optional, for internationalization)
- jedi (optional, for experimental multiline completion)
- watchdog (optional, for monitoring imported modules for changes)
- pyperclip (optional, for copying to the clipboard)

### bpython-urwid

``bpython-urwid`` requires the following additional packages:

- urwid


## Installation via OS Package Manager

The majority of desktop computer operating systems come with package management
systems. If you use one of these OSes, you can install ``bpython`` using the
package manager.

### Ubuntu/Debian

Ubuntu/Debian family Linux users can install ``bpython`` using the ``apt``
package manager, using the command with ``sudo`` privileges:

```bash
$ apt install bpython
```

In case you are using an older version, run

```bash
$ apt-get install bpython
```

### Arch Linux

Arch Linux uses ``pacman`` as the default package manager; you can use it to install ``bpython``:

```bash
$ pacman -S bpython
```

### Fedora

Fedora users can install ``bpython`` directly from the command line using ``dnf``.

```bash
$ dnf install bpython
```

### macOS

macOS does not include a package manager by default. If you have installed any
third-party package manager like MacPorts, you can install it via

```bash
$ sudo port install py-bpython
```

## Known Bugs

For known bugs please see bpython's [known issues and FAQ](http://bpython-interpreter.org/known-issues-and-faq.html)
page.

## Contact & Contributing
I hope you find it useful and please feel free to submit any bugs/patches
on the GitHub [issue tracker](http://github.com/bpython/bpython/issues/).

For any other ways of communicating with bpython users and devs you can find us
at the community page on the [project homepage](https://bpython-interpreter.org),
or in the [community](https://docs.bpython-interpreter.org/community.html).

Hope to see you there!
