.. _tips:

Tips and tricks
===============
There are various tricks and tips to bpython. We currently list one of
them on this page. If you know any more. Don't hesitate to let us know
(:ref:`community`)!

bpython and multiple python versions
------------------------------------
To use bpython with multiple version items this trick has been relayed
to us by Simon Liedtke.

Do a source checkout of bpython and add the following to your `.profile`
equivalent file.

  alias bpython2.6='PYTHONPATH=~/python/bpython python2.6 -m bpython.cli'

Where the `~/python/bpython`-path is the path to where your bpython source code
resides.

You can offcourse add multiple aliasses (make sure you have pygments installed
on all python versions though), so you can run bpython with 2.4, 2.5, 2.6, 2.7
and the 3 series.
