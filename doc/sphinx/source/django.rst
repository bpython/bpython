.. _django:

Django / Pinax
==============
Django is a web framework for professionals with deadlines. People like to
interactively talk to their Django models. Currently Django comes with two
hardcoded options. Either you use the standard Python REPL, or you use IPython.

Pinax is an integrated collection of Django applications, a sort of Django with
out of the box models and views for a lot of stuff.

For those people wanting to use bpython with their Django installation you can
follow the following steps. Written by Chanita Siridechkun. The following
instructions make bpython try to import a setting module in the current folder
and let django set up its enviroment with the settings module (if found) if
bpython can't find the settings module nothing happens and no enviroment gets
set up.

The addition also checks if settings contains a PINAX_ROOT (if you use Pinax),
if it finds this key it will do some additional Pinax setup. The Pinax addition
was written by Skylar Saveland.

bpython uses something called the PYTHONSTARTUP enviroment variable. This is
also used by the vanilla Python REPL.

Add the following lines to your ``.profile`` or equivalent file on your operating
system (``.bash_profile`` on Mac OS X if you use the default shell):

  .. code-block:: text

     export PYTHONSTARTUP=~/.pythonrc

This sets the environment variable PYTHONSTARTUP to the contents of the
``~/.pythonrc`` file when you log in.

To this ``~/.pythonrc`` file you add the following lines:

  .. code-block:: python

    try:
        from django.core.management import setup_environ
        import settings
        setup_environ(settings)

        if settings.PINAX_ROOT:
            import sys
            from os.path import join
            sys.path.insert(0, join(settings.PINAX_ROOT, "apps"))
            sys.path.insert(0, join(settings.PROJECT_ROOT, "apps"))

    except:
        pass


And add an empty line at the end. You need one or it will raise an error.

Login again, or execute the ``source ~/.profile`` equivalent for your shell
and you should be set to go if
you run bpython in a django folder (where the settings.py resides).
