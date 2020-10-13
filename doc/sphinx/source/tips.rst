.. _tips:

Tips and tricks
===============
There are various tricks and tips to bpython. We currently list one of them on
this page. If you know any more, don't hesitate to let us know
(:ref:`community`)!

bpython and multiple python versions
------------------------------------
To use bpython with multiple version items this trick has been relayed
to us by Simon Liedtke.

Do a source checkout of bpython and add the following to your `.profile`
equivalent file.

.. code-block:: bash

  alias bpython3.5='PYTHONPATH=~/python/bpython python3.5 -m bpython.cli'

Where the `~/python/bpython`-path is the path to where your bpython source code
resides.

You can of course add multiple aliases.

.. note::

    Make sure you have the dependencies installed on all Python versions.
