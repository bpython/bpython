.. _configuration:

Configuration
=============
You can copy the supplied sample-config to your home directory and move it to
``$XDG_CONFIG_HOME/bpython/config`` [#f1]_. bpython tries to find
``$XDG_CONFIG_HOME/bpython/config`` and use it as its configuration, if the
file does not exist bpython will use its documented defaults.

.. :: Footnotes

.. [#f1] ``$XDG_CONFIG_HOME`` defaults to ``~/.config`` if not set.

.. include:: configuration-options.rst

