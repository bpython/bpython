.. _contributing:

Contributing to bpython
=======================

Thanks for working on bpython!

On the `GitHub issue tracker`_ some issues are labeled bite-size_ -
these are particularly good ones to start out with.

See our section about the :ref:`community` for a list of resources.

`#bpython <irc://irc.freenode.net/bpython>`_ on Freenode is particularly useful,
but you might have to wait for a while to get a question answered depending on
the time of day.

Getting your development environment set up
-------------------------------------------

bpython supports Python 2.7, 3.3 and newer. The code is compatible with all
supported versions without the need to run post processing like `2to3`.

Using a virtual environment is probably a good idea. Create a virtual
environment with

.. code-block:: bash

    # determines Python version used
    $ virtualenv bpython-dev
    # necessary every time you work on bpython
    $ source bpython-dev/bin/activate

Fork bpython in the GitHub web interface, then clone the repo:

.. code-block:: bash

    $ git clone git@github.com:YOUR_GITHUB_USERNAME/bpython.git
    # or "git clone https://github.com/YOUR_GITHUB_USERNAME/bpython.git"

Next install the install your development copy of bpython and its dependencies:

.. code-block:: bash

    $ cd bpython
    # install bpython and required dependencies
    $ pip install -e .
    # install optional dependencies
    $ pip install watchdog urwid
    # development dependencies
    $ pip install sphinx mock nose
    <modify a file in some way>
    # this runs your modified copy of bpython!
    $ bpython

.. note::

    Many requirements are also available from your distribution's package
    manager. On Debian/Ubuntu based systems, the following packages can be
    used:

    .. code-block:: bash

        $ sudp apt-get install python-greenlet python-pygments python-requests
        $ sudo apt-get install python-watchdog python-urwid
        $ sudo apt-get install python-sphinx python-mock python-nose

    Remember to replace ``python`` with ``python3`` in every package name if
    you intend to develop with Python 3. You also need to run `virtualenv` with
    `--system-site-packages` packages, if you want to use the packages provided
    by your distribution.

.. note::

    Installation of some dependencies with ``pip`` requires Python headers and
    a C compiler. These are also available from your package manager.

    .. code-block:: bash

        $ sudo apt-get install gcc python-dev

As a first dev task, I recommend getting `bpython` to print your name every
time you hit a specific key.

To run tests from the bpython directory:

.. code-block:: bash

    $ nosetests

If you want to skip test cases that are known to be slow, run `nosetests` in
the following way:

.. code-block:: bash

    $ nosetests -A "speed != 'slow'"

Building the documentation
--------------------------

The documentation is included in the bpython repository. After
checking out the bpython repository and installing `sphinx` as described in
the previous step, you can run the following command in your checkout of the
repository to build the documentation:

.. code-block:: bash

    $ make -C doc/sphinx html

Afterwards you can point your browser to `doc/sphinx/build/html/index.html`.
Don't forget to recreate the HTML after you make changes.

Hacking on the site or theme
----------------------------

The site (and its theme as well) is stored in a separate repository and built
using pelican. To start hacking on the site you need to start out with a
checkout and probably a virtual environment:

.. code-block:: bash

    $ virtualenv bpython-site-dev
    $ source bpython-site-dev/bin/activate
    $ pip install pelican

Fork bsite and bsite-theme in the GitHub web interface, then clone the
repositories:

.. code-block:: bash

    $ git clone git@github.com:YOUR_GITHUB_USERNAME/bsite.git
    $ git clone git@github.com:YOUR_GITHUB_USERNAME/bsite-theme.git

Next you can fiddle around in the source files. If you want to build the site
you activate your virtualenv and tell pelican to generate the site with the
included configuration file.

.. code-block:: bash

    $ source bpython-site-dev/bin/activate
    # if you want to fiddle on the text of the site otherwise go into
    # bsite-theme
    $ cd bsite
    # if you checked out the theme in a different place, use that path
    $ pelican -t ../bsite-theme -s pelicanconf.py

After this you can open the `output/index.html` in your favourite browser and
see if your changes had an effect.

.. _GitHub issue tracker: https://github.com/bpython/bpython/issues
.. _bite-size: https://github.com/bpython/bpython/labels/bitesize
