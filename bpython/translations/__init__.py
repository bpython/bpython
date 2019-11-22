# encoding: utf-8

from __future__ import absolute_import

import gettext
import locale
import os.path
import sys

from .. import package_dir
from .._py3compat import py3

translator = None

if py3:

    def _(message):
        return translator.gettext(message)

    def ngettext(singular, plural, n):
        return translator.ngettext(singular, plural, n)


else:

    def _(message):
        return translator.ugettext(message)

    def ngettext(singular, plural, n):
        return translator.ungettext(singular, plural, n)


def init(locale_dir=None, languages=None):
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        # This means that the user's environment is broken. Let's just continue
        # with the default C locale.
        sys.stderr.write(
            "Error: Your locale settings are not supported by "
            "the system. Using the fallback 'C' locale instead. "
            "Please fix your locale settings.\n"
        )

    global translator
    if locale_dir is None:
        locale_dir = os.path.join(package_dir, "translations")

    translator = gettext.translation(
        "bpython", locale_dir, languages, fallback=True
    )
