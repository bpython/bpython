.. _sourcecode:

Sourcecode
==========

Warning, large parts of source code are still undocumented till we include
the automatic generation of this documentation by adding in restructed text
comments.

bpython.cli
-----------

.. module:: cli
   :platform: POSIX
   :synopsis: Basic interpreter.

.. function:: log(x)

   Function to log anything in x to /tmp/bpython.log

.. function:: parsekeywordpairs(signature)

   Not documented yet.

   :param signature: string
   :rtype: dictionary

.. function:: fixlongargs(f, argspec)

    Functions taking default arguments that are references to other objects
    whose str() is too big will cause breakage, so we swap out the object
    itself with the name it was referenced with in the source by parsing the
    source itself !

.. class:: FakeStdin

.. method:: FakeStdin.__init__(self, interface)

      Take the curses Repl on init and assume it provides a get_key method
      which, fortunately, it does."""

.. method:: FakeStdin.isatty(self)

   Spoof into thinking this is a tty

   :rtype: Boolean
   :returns: True


.. method:: FakeStdin.readline(self)

   I can't think of any reason why anything other than readline would
   be useful in the context of an interactive interpreter so this is the
   only one I've done anything with. The others are just there in case
   someone does something weird to stop it from blowing up."""

   :rtype: string

bpython.keys
------------

.. module:: keys
   :platform: POSIX
   :synopsis: Keyboard mappings
