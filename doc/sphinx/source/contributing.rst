.. _contributing:

Contributing to bpython
=======================

Thanks for working on bpython!

On the `GitHub issue tracker`_ some issues are labeled bite-size_
these are particularly good ones to start out with.

See our section about the :ref:`community` for a list of resources.

`#bpython` on freenode is particularly useful, but you might have to wait for a while
to get a question answered depending on the time of day.

Getting your development environment set up
-------------------------------------------

Using a virtual environment is probably a good idea. Create a virtual environment with

.. code-block:: bash

    $ virtualenv bpython-dev
    $ source bpython-dev/bin/activate   # this step is necssary every time you work on bpython
    <hack on bpython>
    $ deactivate                        # back to normal system environment

Fork `bpython` in the GitHub web interface, then clone the repo:

.. code-block:: bash

    $ git clone git@github.com:YOUR_GITHUB_USERNAME/bpython.git

Next install this development version of `bpython`:

.. code-block:: bash

    $ pip install pygments curtsies greenlet watchdog urwid  # install all the dependencies
    $ pip install sphinx mock                                # development dependencies
    $ cd bpython
    $ python setup.py develop
    <modify a file in some way>
    $ bpython-curtsies      # this runs your modified copy of bpython!

As a first dev task, I recommend getting `bpython` to print your name every time you hit a specific key.

To run tests:

    $ python -m unittest discover bpython

To build the docs:
------------------

The documentation is included in the regular `bpython` repository so if you did the
previous step your install can support generating and working on the documentation.

Install `sphinx` (or in your current `virtualenv`). And go to the following directory:

.. code-block:: bash

    $ pip install sphinx
    $ cd bpython/doc/sphinx/ # assuming you are in the root dir of the bpython project
    $ make html

Afterwards you can point your browser to `bpython/doc/source/index.html`. Don't forget
to recreate the HTML after you make changes.


To hack on the site or theme
----------------------------

The site (and it's theme as well) is stored in a separate repository and built using
pelican. To start hacking on the site you need to start out with a checkout and
probably a virtual environment:

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
    $ cd bsite # if you want to fiddle on the text of the site otherwise go into bsite-theme
    $ pelican -t ../bsite-theme -s pelicanconf.py # if you checked out the theme in a different place, use that path

After this you can open the `output/index.html` in your favourite browser and see
if your changes had an effect.

..  _GitHub issue tracker: https://github.com/bpython/bpython/issues
.. _bite-size: https://github.com/bpython/bpython/labels/bitesize
