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

    $ virtualenv bpython-dev
    $ source bpython-dev/bin/activate   # this step is necssary every time you work on bpython
    <hack on bpython>
    $ deactivate                        # back to normal system environment

Fork bpython in the GitHub web interace, then clone the repo:

    $ git clone git@github.com:YOUR_GITHUB_USERNAME/bpython.git

Next install this development version of bpython:

    $ pip install pygments curtsies greenlet watchdog urwid  # install all the dependencies
    $ pip install sphinx mock                                # development dependencies
    $ cd bpython
    $ python setup.py develop
    <modify a file in some way>
    $ bpython-curtsies      # this runs your modified copy of bpython!

As a first dev task, I recommend getting bpython to print your name every time you hit a specific key.

To run tests:

    $ python -m unittest discover bpython

To build the docs:
------------------

TODO

To hack on the site:
--------------------

TODO

..  _GitHub issue tracker: https://github.com/bpython/bpython/issues
.. _bite-size: https://github.com/bpython/bpython/labels/bitesize
